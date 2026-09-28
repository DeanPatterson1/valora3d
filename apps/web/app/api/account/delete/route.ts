import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";
import { sameOrigin } from "@/lib/server/api";
import { R2Storage } from "@/lib/server/r2";
import { userPrefix } from "@/lib/uploads/validate";
import { billingConfig } from "@/lib/env";
import { createPaddleApi } from "@/lib/billing/paddle-api";

/**
 * POST /api/account/delete — deletes the caller's account server-side: every R2 object under
 * `u/<userId>/`, then the auth user, whose foreign keys cascade to profiles, projects, uploads,
 * versions, render jobs, ledger and billing rows. Live Paddle subscriptions are canceled first.
 */
export async function POST(request: Request) {
  if (!sameOrigin(request)) return apiError(403, "forbidden", "Cross-origin request refused.");
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;

  const admin = createServiceSupabase(ctx.config);

  // Stop billing first: a deleted account must never be charged again. If a live subscription
  // cannot be canceled, keep the account so the user can retry (or cancel in the portal).
  const { data: subs, error: subsError } = await admin
    .from("billing_subscriptions").select("id").eq("user_id", ctx.user.id).neq("status", "canceled");
  if (subsError) return apiError(500, "server", "Could not delete the account.");
  if (subs && subs.length > 0) {
    const billing = billingConfig();
    if (!billing?.apiKey) return apiError(409, "manage_billing", "Cancel your plan in Manage billing, then delete the account.");
    const paddle = createPaddleApi(billing.apiKey, billing.environment);
    for (const { id } of subs as { id: string }[]) {
      const r = await paddle.cancelSubscriptionNow(id);
      if ("error" in r) return apiError(502, "server", "Could not cancel your plan. Try again in a minute.");
    }
  }

  if (ctx.config.r2) {
    try {
      await new R2Storage(ctx.config.r2).deletePrefix(userPrefix(ctx.user.id));
    } catch {
      // Keep the account (and the user's ability to retry) rather than orphan files.
      return apiError(502, "server", "Could not delete your files. Try again in a minute.");
    }
  }

  const { error } = await admin.auth.admin.deleteUser(ctx.user.id);
  if (error) return apiError(500, "server", "Could not delete the account.");

  await ctx.userClient.auth.signOut().catch(() => undefined);
  return new Response(null, { status: 204 });
}
