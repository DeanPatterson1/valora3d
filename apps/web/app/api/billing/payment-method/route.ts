import { billingConfig } from "@/lib/env";
import { createPaddleApi } from "@/lib/billing/paddle-api";
import type { PortalResponse } from "@/lib/billing/types";
import { sameOrigin } from "@/lib/server/api";
import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";

/**
 * POST /api/billing/payment-method — a fresh Paddle portal link straight to "update payment method" for the caller's
 * overdue (or else live) subscription; the past-due banner and the "payment didn't go through" mail lead here.
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
    admin.from("billing_subscriptions").select("id, status").eq("user_id", ctx.user.id).neq("status", "canceled"),
  ]);
  if (customer.error || subs.error) return apiError(500, "server", "Something went wrong on our side.");
  const list = (subs.data ?? []) as { id: string; status: string }[];
  const sub = list.find((s) => s.status === "past_due") ?? list[0];
  if (!customer.data || !sub) return apiError(404, "no_billing", "There's no plan on this account.");

  const r = await createPaddleApi(billing.apiKey, billing.environment).paymentMethodUrl(customer.data.paddle_customer_id, sub.id);
  if ("error" in r) return apiError(502, "server", "Could not open billing. Try again in a minute.");
  return Response.json({ url: r.url } satisfies PortalResponse, { headers: { "Cache-Control": "no-store" } });
}
