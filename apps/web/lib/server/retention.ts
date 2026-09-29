import type { SupabaseClient } from "@supabase/supabase-js";
import { outputKey } from "@/lib/render/contract";

/**
 * Retention enforcement, run by the cron sweep (POST /api/renders/sweep). The SQL side decides what is due
 * (20260928150000_plan_limits_v2.sql); this deletes the R2 objects in bounded batches and records the result:
 *   - render outputs: finished_at + the retention stamped on the job at creation (Free 7, Creator 30, Pro 90
 *     days). Objects are deleted first, then the row is marked expired (it stays as history, "Expired" in the UI).
 *   - uploaded models: the owner's current plan retention since last use. expire_uploads() claims them first
 *     (so no new render can start from a model being deleted), then the object is deleted and marked purged; a
 *     failed delete stays claimed and is retried on the next sweep.
 */

export type ExpiredOutput = { job_id: string; user_id: string };
export type ExpiredUpload = { upload_id: string; user_id: string; r2_key: string | null };

export interface RetentionStore {
  expiredRenderOutputs(limit: number): Promise<ExpiredOutput[]>;
  markRenderOutputsExpired(jobIds: string[]): Promise<number>;
  expireUploads(limit: number): Promise<ExpiredUpload[]>;
  markUploadsPurged(uploadIds: string[]): Promise<number>;
}

export interface R2Deleter {
  /** Deletes one object; a missing object is not an error. */
  delete(key: string): Promise<void>;
}

export type RetentionResult = {
  outputs: { expired: number; failed: number };
  uploads: { purged: number; failed: number };
};

export type RetentionDeps = {
  store: RetentionStore;
  r2: R2Deleter;
  /** Rows per SQL call (the SQL caps it at 500). */
  batch?: number;
  /** Batches per kind per sweep, to bound one cron run's work; the rest waits for the next run. */
  maxBatches?: number;
  /** Parallel R2 deletes. */
  concurrency?: number;
  log?: (message: string, extra?: Record<string, unknown>) => void;
};

/** Runs `fn` over `items` with at most `limit` in flight. Returns which items succeeded. */
async function eachLimited<T>(items: T[], limit: number, fn: (item: T) => Promise<void>): Promise<boolean[]> {
  const ok = new Array<boolean>(items.length).fill(false);
  let next = 0;
  const worker = async () => {
    while (next < items.length) {
      const i = next++;
      try {
        await fn(items[i]);
        ok[i] = true;
      } catch {
        ok[i] = false;
      }
    }
  };
  await Promise.all(Array.from({ length: Math.max(1, Math.min(limit, items.length)) }, worker));
  return ok;
}

export async function sweepRetention(deps: RetentionDeps): Promise<RetentionResult> {
  const batch = deps.batch ?? 100;
  // Kept small so one cron run stays well inside the Worker's subrequest budget; the rest waits 5 minutes.
  const maxBatches = deps.maxBatches ?? 2;
  const concurrency = deps.concurrency ?? 6;
  const log = deps.log ?? ((message, extra) => console.warn(`[retention] ${message}`, extra ?? ""));
  const result: RetentionResult = { outputs: { expired: 0, failed: 0 }, uploads: { purged: 0, failed: 0 } };

  // Render outputs: delete both files, then mark the job. A job whose delete failed is listed again next run.
  const seenJobs = new Set<string>();
  for (let b = 0; b < maxBatches; b++) {
    const due = (await deps.store.expiredRenderOutputs(batch)).filter((j) => !seenJobs.has(j.job_id));
    if (due.length === 0) break;
    due.forEach((j) => seenJobs.add(j.job_id));
    const ok = await eachLimited(due, concurrency, async (j) => {
      await deps.r2.delete(outputKey(j.user_id, j.job_id, "video"));
      await deps.r2.delete(outputKey(j.user_id, j.job_id, "poster"));
    });
    const done = due.filter((_, i) => ok[i]).map((j) => j.job_id);
    const failed = due.length - done.length;
    if (failed) log("output delete failed", { failed });
    if (done.length) result.outputs.expired += await deps.store.markRenderOutputsExpired(done);
    result.outputs.failed += failed;
    if (due.length < batch) break;
  }

  // Uploaded models: claimed by expire_uploads(), deleted, then marked purged.
  const seenUploads = new Set<string>();
  for (let b = 0; b < maxBatches; b++) {
    const due = (await deps.store.expireUploads(batch)).filter((u) => !seenUploads.has(u.upload_id));
    if (due.length === 0) break;
    due.forEach((u) => seenUploads.add(u.upload_id));
    const ok = await eachLimited(due, concurrency, async (u) => {
      // Defence in depth: only ever delete inside the owner's own upload prefix (the table enforces it too).
      if (u.r2_key && !u.r2_key.startsWith(`u/${u.user_id}/`)) throw new Error("key outside the owner prefix");
      if (u.r2_key) await deps.r2.delete(u.r2_key);
    });
    const done = due.filter((_, i) => ok[i]).map((u) => u.upload_id);
    const failed = due.length - done.length;
    if (failed) log("upload delete failed", { failed });
    if (done.length) result.uploads.purged += await deps.store.markUploadsPurged(done);
    result.uploads.failed += failed;
    if (due.length < batch) break;
  }
  return result;
}

/** RetentionStore over the SERVICE-ROLE client. Only constructed by the cron-secret-checked sweep route. */
export class SupabaseRetentionStore implements RetentionStore {
  constructor(private readonly admin: SupabaseClient) {}

  async expiredRenderOutputs(limit: number): Promise<ExpiredOutput[]> {
    const { data, error } = await this.admin.rpc("expired_render_outputs", { p_limit: limit });
    if (error) throw new Error(`expired_render_outputs failed: ${error.message}`);
    return (data ?? []) as ExpiredOutput[];
  }

  async markRenderOutputsExpired(jobIds: string[]): Promise<number> {
    const { data, error } = await this.admin.rpc("mark_render_outputs_expired", { p_job_ids: jobIds });
    if (error) throw new Error(`mark_render_outputs_expired failed: ${error.message}`);
    return typeof data === "number" ? data : 0;
  }

  async expireUploads(limit: number): Promise<ExpiredUpload[]> {
    const { data, error } = await this.admin.rpc("expire_uploads", { p_limit: limit });
    if (error) throw new Error(`expire_uploads failed: ${error.message}`);
    return (data ?? []) as ExpiredUpload[];
  }

  async markUploadsPurged(uploadIds: string[]): Promise<number> {
    const { data, error } = await this.admin.rpc("mark_uploads_purged", { p_upload_ids: uploadIds });
    if (error) throw new Error(`mark_uploads_purged failed: ${error.message}`);
    return typeof data === "number" ? data : 0;
  }
}

/** `sync_expired_plans()`: moves profiles.plan (the display copy) off paid periods that ended with no event. */
export async function syncExpiredPlans(admin: SupabaseClient): Promise<number> {
  const { data, error } = await admin.rpc("sync_expired_plans");
  if (error) throw new Error(`sync_expired_plans failed: ${error.message}`);
  return typeof data === "number" ? data : 0;
}

/**
 * `expire_plan_credits()`: writes a `credit_expiry` ledger row for what is left of each monthly plan grant whose
 * rollover window (PLAN_CREDIT_ROLLOVER_PERIODS) has ended. Idempotent; returns the credits expired.
 */
export async function expirePlanCredits(admin: SupabaseClient): Promise<number> {
  const { data, error } = await admin.rpc("expire_plan_credits", { p_limit: 200 });
  if (error) throw new Error(`expire_plan_credits failed: ${error.message}`);
  return typeof data === "number" ? data : 0;
}
