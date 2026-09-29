import { serverConfig } from "@/lib/env";
import { R2Storage } from "@/lib/server/r2";
import { createRenderPipeline } from "@/lib/server/renderContext";
import { SupabaseRetentionStore, sweepRetention, syncExpiredPlans } from "@/lib/server/retention";
import { SupabasePurgeStore, drainStoragePurges, pruneUsageEvents } from "@/lib/server/storagePurge";
import { timingSafeEqualStr } from "@/lib/server/webhookToken";
import { createServiceSupabase } from "@/lib/supabase/server";

/**
 * POST /api/renders/sweep — the Worker's cron (custom-worker.mjs `scheduled`, wrangler.jsonc "triggers", every
 * 5 min) with `Authorization: Bearer <CRON_SECRET>`. Three independent chores, each reported on its own so one
 * failing never skips the others:
 *   - renders: re-polls jobs nobody has heard from and finalizes (or refunds) them (lost webhooks, dropped submits);
 *   - plans: `sync_expired_plans()`, the profile's display plan after a paid period ends with no event (no pg_cron);
 *   - retention: deletes expired render outputs and models from R2 and marks the rows (lib/server/retention.ts);
 *   - purge: drains storage_purge_queue (files of deleted accounts, projects and jobs; lib/server/storagePurge.ts)
 *     within a request budget, and prunes old usage counter rows.
 * Answers 500 when any chore failed, so a failing cron shows in the Worker logs.
 */
/** R2 requests one cron run may spend on the purge queue (the retention chore uses up to ~400 of its own). */
const PURGE_BUDGET = 300;

export async function POST(request: Request) {
  const config = serverConfig();
  if (!config?.cronSecret) return Response.json({ ok: false }, { status: 404 });
  const presented = request.headers.get("authorization")?.replace(/^Bearer\s+/i, "") ?? "";
  if (!timingSafeEqualStr(presented, config.cronSecret)) return Response.json({ ok: false }, { status: 404 });

  const admin = createServiceSupabase(config);
  const failures: string[] = [];
  const run = async <T,>(name: string, fn: () => Promise<T>): Promise<T | { error: string }> => {
    try {
      return await fn();
    } catch (error) {
      failures.push(name);
      console.error(`[sweep] ${name} failed`, error instanceof Error ? error.message : String(error));
      return { error: "failed" };
    }
  };

  const renders = config.runpod
    ? await run("renders", () => createRenderPipeline(config, admin).sweep(new URL(request.url).origin))
    : { checked: 0, finished: 0, note: "renderer not configured" };
  const plans = await run("plans", async () => ({ synced: await syncExpiredPlans(admin) }));
  const r2 = config.r2;
  const retention = r2
    ? await run("retention", () => sweepRetention({ store: new SupabaseRetentionStore(admin), r2: new R2Storage(r2) }))
    : { note: "storage not configured" };
  const purge = r2
    ? await run("purge", async () => ({
        ...(await drainStoragePurges({ store: new SupabasePurgeStore(admin), r2: new R2Storage(r2) }, { budget: PURGE_BUDGET, limit: 100 })),
        pruned: await pruneUsageEvents(admin),
      }))
    : { note: "storage not configured" };

  return Response.json(
    { ok: failures.length === 0, renders, plans, retention, purge },
    { status: failures.length ? 500 : 200, headers: { "Cache-Control": "no-store" } },
  );
}
