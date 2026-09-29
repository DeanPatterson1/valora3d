import type { SupabaseClient } from "@supabase/supabase-js";
import { TIER_POLICY } from "@/lib/render/contract";

/**
 * The storage purge queue (20260929200000_storage_security.sql): R2 objects whose rows are gone or going.
 * Row triggers queue a deleted upload's key and a deleted job's `r/<uid>/<job>/` prefix in the same transaction
 * as the delete; the account route queues the owner's whole `u/<uid>/` and `r/<uid>/` prefixes (now, and again
 * once every presigned PUT they still held has expired). Routes drain their own entries at once when they can;
 * the cron sweep drains the rest, so a deletion is eventually complete even when R2 was down at the time.
 */

const UUID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";
/** The only shapes a purge may take (the table's CHECK is the same): never a bare or foreign prefix. */
const TARGET = new RegExp(`^(?:[ur]/${UUID}/|r/${UUID}/${UUID}/|u/${UUID}/${UUID}\\.glb)$`);

export function isPurgeTarget(target: string, userId: string): boolean {
  return TARGET.test(target) && target.split("/")[1] === userId;
}

export type PurgeEntry = { id: number; user_id: string; target: string };

export interface PurgeStore {
  enqueue(userId: string, target: string, reason: PurgeReason, notBefore?: Date): Promise<void>;
  claim(limit: number, userId?: string): Promise<PurgeEntry[]>;
  complete(ids: number[]): Promise<void>;
  release(ids: number[], error: string): Promise<void>;
}

export type PurgeReason = "account_deleted" | "project_deleted" | "upload_deleted" | "render_deleted";

export interface PurgeStorage {
  delete(key: string): Promise<void>;
  deletePrefixBounded(prefix: string, maxOps: number): Promise<{ removed: number; complete: boolean; ops: number }>;
}

export type DrainResult = { done: number; pending: number; failed: number; removed: number };

/**
 * Drains due entries with at most `budget` R2 requests. An entry is completed only when everything under it is
 * gone; an R2 error or a budget that ran out mid-prefix releases it to back off and continue later.
 */
export async function drainStoragePurges(
  deps: { store: PurgeStore; r2: PurgeStorage; log?: (message: string, extra?: Record<string, unknown>) => void },
  opts: { budget: number; limit?: number; userId?: string },
): Promise<DrainResult> {
  const log = deps.log ?? ((message, extra) => console.warn(`[purge] ${message}`, extra ?? ""));
  const result: DrainResult = { done: 0, pending: 0, failed: 0, removed: 0 };
  const entries = await deps.store.claim(opts.limit ?? 50, opts.userId);
  let left = opts.budget;
  const done: number[] = [];
  const pending: number[] = [];
  const failed: number[] = [];
  for (const e of entries) {
    if (!isPurgeTarget(e.target, e.user_id)) {
      // Never reached (the table refuses these shapes); if it ever is, keep it for an operator.
      failed.push(e.id);
      continue;
    }
    if (left <= 0) {
      pending.push(e.id);
      continue;
    }
    try {
      if (e.target.endsWith("/")) {
        const r = await deps.r2.deletePrefixBounded(e.target, left);
        left -= r.ops;
        result.removed += r.removed;
        (r.complete ? done : pending).push(e.id);
      } else {
        left -= 1;
        await deps.r2.delete(e.target);
        result.removed += 1;
        done.push(e.id);
      }
    } catch (error) {
      failed.push(e.id);
      log("purge failed", { detail: error instanceof Error ? error.message : String(error) });
    }
  }
  if (done.length) await deps.store.complete(done);
  if (pending.length) await deps.store.release(pending, "budget exhausted; continues next run");
  if (failed.length) await deps.store.release(failed, "R2 delete failed");
  result.done = done.length;
  result.pending = pending.length;
  result.failed = failed.length;
  return result;
}

/** How long after a submit a worker may still PUT outputs (presignLifetimes' PUT lifetime, the longest tier). */
export const RENDER_PUT_WINDOW_MS = Math.max(
  ...Object.values(TIER_POLICY).map((p) => p.ttl + p.executionTimeout + 30 * 60 * 1000),
);
/** An upload's presigned PUT lives 10 minutes (R2Storage.presignPut); the late sweep waits 15. */
export const UPLOAD_PUT_WINDOW_MS = 15 * 60 * 1000;

/** Queues every object an account owns: now, and once more after any presigned PUT it held has expired. */
export async function enqueueAccountPurge(store: PurgeStore, userId: string, now: number): Promise<void> {
  const u = `u/${userId}/`;
  const r = `r/${userId}/`;
  await store.enqueue(userId, u, "account_deleted");
  await store.enqueue(userId, r, "account_deleted");
  await store.enqueue(userId, u, "account_deleted", new Date(now + UPLOAD_PUT_WINDOW_MS));
  await store.enqueue(userId, r, "account_deleted", new Date(now + RENDER_PUT_WINDOW_MS));
}

/** PurgeStore over the SERVICE-ROLE client (server routes and the cron sweep only). */
export class SupabasePurgeStore implements PurgeStore {
  constructor(private readonly admin: SupabaseClient) {}

  async enqueue(userId: string, target: string, reason: PurgeReason, notBefore?: Date): Promise<void> {
    const { error } = await this.admin.rpc("enqueue_storage_purge", {
      p_user_id: userId,
      p_target: target,
      p_reason: reason,
      p_not_before: (notBefore ?? new Date()).toISOString(),
    });
    if (error) throw new Error(`enqueue_storage_purge failed: ${error.message}`);
  }

  async claim(limit: number, userId?: string): Promise<PurgeEntry[]> {
    const { data, error } = await this.admin.rpc("claim_storage_purges", { p_limit: limit, p_user_id: userId ?? null });
    if (error) throw new Error(`claim_storage_purges failed: ${error.message}`);
    return ((data ?? []) as PurgeEntry[]).map((e) => ({ ...e, id: Number(e.id) }));
  }

  async complete(ids: number[]): Promise<void> {
    const { error } = await this.admin.rpc("complete_storage_purges", { p_ids: ids });
    if (error) throw new Error(`complete_storage_purges failed: ${error.message}`);
  }

  async release(ids: number[], message: string): Promise<void> {
    const { error } = await this.admin.rpc("release_storage_purges", { p_ids: ids, p_error: message });
    if (error) throw new Error(`release_storage_purges failed: ${error.message}`);
  }
}

/** `prune_usage_events()`: counter rows older than any cap's window. */
export async function pruneUsageEvents(admin: SupabaseClient): Promise<number> {
  const { data, error } = await admin.rpc("prune_usage_events");
  if (error) throw new Error(`prune_usage_events failed: ${error.message}`);
  return typeof data === "number" ? data : 0;
}
