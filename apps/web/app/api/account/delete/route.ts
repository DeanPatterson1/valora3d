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
