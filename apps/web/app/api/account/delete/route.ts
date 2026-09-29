import { log } from "@/lib/server/log";
import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";
import { sameOrigin } from "@/lib/server/api";
import { R2Storage } from "@/lib/server/r2";
import { RunpodClient } from "@/lib/server/runpod";
import { SupabasePurgeStore, drainStoragePurges, enqueueAccountPurge } from "@/lib/server/storagePurge";
import { billingConfig } from "@/lib/env";
import { createPaddleApi } from "@/lib/billing/paddle-api";

/** R2 requests this route may spend deleting at once; whatever is left the cron sweep finishes. */
const PURGE_BUDGET = 400;

/**
 * POST /api/account/delete — deletes the caller's account server-side. Live Paddle subscriptions are canceled
 * first, then live renders at RunPod. Every R2 object the user owns (`u/<uid>/` models, `r/<uid>/` render
 * outputs, which shares only point at) is queued in storage_purge_queue, now and once more after every presigned
 * PUT they held has expired, and deleted here as far as the budget allows; the cron sweep finishes the rest, so
 * the erasure completes even if R2 is down now. Then the auth user is deleted, whose foreign keys cascade to
 * profiles, projects, uploads, versions, render jobs, shares, ledger and billing rows.
 */
export async function POST(request: Request) {
  if (!sameOrigin(request)) return apiError(403, "forbidden", "Cross-origin request refused.");
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;

  const admin = createServiceSupabase(ctx.config);

  // Stop billing first: a deleted account must never be charged again. If a live subscription
  // cannot be canceled, keep the account so the user can retry (or cancel in the portal).
  // Ask Paddle too: a subscription whose first webhook has not landed yet is not in our table.
  const [subs, customer] = await Promise.all([
    admin.from("billing_subscriptions").select("id").eq("user_id", ctx.user.id).neq("status", "canceled"),
    admin.from("billing_customers").select("paddle_customer_id").eq("user_id", ctx.user.id).maybeSingle<{ paddle_customer_id: string }>(),
  ]);
  if (subs.error || customer.error) return apiError(500, "server", "Could not delete the account.");
  const toCancel = new Set(((subs.data ?? []) as { id: string }[]).map((s) => s.id));
  const billing = billingConfig();
  if (toCancel.size > 0 || customer.data) {
    if (!billing?.apiKey) {
      if (toCancel.size > 0) return apiError(409, "manage_billing", "Cancel your plan in Manage billing, then delete the account.");
    } else {
      const paddle = createPaddleApi(billing.apiKey, billing.environment);
      if (customer.data) {
        const listed = await paddle.listLiveSubscriptions(customer.data.paddle_customer_id);
        if ("error" in listed) return apiError(502, "server", "Could not check your plan. Try again in a minute.");
        listed.ids.forEach((id) => toCancel.add(id));
      }
      for (const id of toCancel) {
        const r = await paddle.cancelSubscriptionNow(id);
        if ("error" in r) return apiError(502, "server", "Could not cancel your plan. Try again in a minute.");
      }
    }
  }

  // Stop the GPUs: a render still running would write outputs after the rows are gone (the late purge covers it
  // anyway). Best effort; RunPod's own time limit bounds a job this misses.
  const runpod = ctx.config.runpod ? new RunpodClient(ctx.config.runpod) : null;
  if (runpod) {
    const { data: live } = await admin
      .from("render_jobs")
      .select("runpod_id")
      .eq("user_id", ctx.user.id)
      .in("status", ["queued", "running"])
      .not("runpod_id", "is", null);
    for (const j of (live ?? []) as { runpod_id: string }[]) {
      await runpod.cancel(j.runpod_id).catch(() => log("warn", "/api/account/delete", "render_cancel_failed", { userId: ctx.user.id }));
    }
  }

  // Queued in the database first: from here on the files are deleted eventually, whatever happens below.
  const purge = new SupabasePurgeStore(admin);
  try {
    await enqueueAccountPurge(purge, ctx.user.id, Date.now());
  } catch {
    log("error", "/api/account/delete", "files_delete_failed", { userId: ctx.user.id });
    // Keep the account (and the user's ability to retry) rather than orphan files.
    return apiError(502, "server", "Could not delete your files. Try again in a minute.");
  }
  if (ctx.config.r2) {
    await drainStoragePurges({ store: purge, r2: new R2Storage(ctx.config.r2) }, { budget: PURGE_BUDGET, userId: ctx.user.id }).catch(() =>
      log("warn", "/api/account/delete", "files_delete_deferred", { userId: ctx.user.id }),
    );
  }

  const { error } = await admin.auth.admin.deleteUser(ctx.user.id);
  if (error) return apiError(500, "server", "Could not delete the account.");

  await ctx.userClient.auth.signOut().catch(() => {
    log("warn", "/api/account/delete", "signout_failed", { userId: ctx.user.id });
  });
  return new Response(null, { status: 204 });
}
