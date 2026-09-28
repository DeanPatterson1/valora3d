import { billingConfig } from "@/lib/env";
import { createPaddleApi } from "@/lib/billing/paddle-api";
import type { PortalResponse } from "@/lib/billing/types";
import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";
import { sameOrigin } from "@/lib/server/api";

/**
 * POST /api/billing/portal — a fresh Paddle customer portal link for the caller (invoices,
 * payment method, cancel). The browser navigates to the returned `url`; the links are
 * short-lived, so one is made per click.
 */
export async function POST(request: Request) {
  if (!sameOrigin(request)) return apiError(403, "forbidden", "Cross-origin request refused.");
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const billing = billingConfig();
  if (!billing?.apiKey) return apiError(503, "checkout_unavailable", "Billing isn't open yet.");

  const admin = createServiceSupabase(ctx.config);
  const [customer, subs] = await Promise.all([
    admin.from("billing_customers").select("paddle_customer_id").eq("user_id", ctx.user.id).maybeSingle<{ paddle_customer_id: string }>(),
    admin.from("billing_subscriptions").select("id").eq("user_id", ctx.user.id).neq("status", "canceled"),
  ]);
  if (customer.error || subs.error) return apiError(500, "server", "Something went wrong on our side.");
  if (!customer.data) return apiError(404, "no_billing", "There are no purchases on this account yet.");

  const ids = ((subs.data ?? []) as { id: string }[]).map((s) => s.id);
  const r = await createPaddleApi(billing.apiKey, billing.environment).createPortalSession(customer.data.paddle_customer_id, ids);
  if ("error" in r) return apiError(502, "server", "Could not open billing. Try again in a minute.");
  return Response.json({ url: r.url } satisfies PortalResponse, { headers: { "Cache-Control": "no-store" } });
}
