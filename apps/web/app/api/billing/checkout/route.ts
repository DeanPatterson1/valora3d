import { z } from "zod";
import { billingConfig } from "@/lib/env";
import { CHECKOUT_ITEMS, PLAN_LIMITS, type PlanId } from "@/lib/pricing";
import { buildCatalog, type CatalogEntry } from "@/lib/billing/catalog";
import { createPaddleApi } from "@/lib/billing/paddle-api";
import { signUserId } from "@/lib/billing/signature";
import type { CheckoutResponse } from "@/lib/billing/types";
import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";
import { readBody } from "@/lib/server/api";

const Body = z.object({ item: z.enum(CHECKOUT_ITEMS) });

const json = (body: CheckoutResponse) => Response.json(body, { headers: { "Cache-Control": "no-store" } });

/**
 * POST /api/billing/checkout {item} — what Paddle.js needs to open the overlay checkout for one
 * catalog item. The browser sends only the item key; the price id comes from server env and the
 * custom data carries a signed user id, which the webhook checks before crediting anyone.
 *
 * The Paddle customer is looked up (or created) here from the account's own verified email and
 * linked server-side; webhooks never link customers, so checking out under someone else's email
 * cannot take over their billing portal.
 *
 * A plan purchase while a plan subscription is live changes that subscription instead (an upgrade
 * is charged pro rata, a downgrade is not billed), so nobody ends up paying for two plans.
 */
export async function POST(request: Request) {
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const body = await readBody(request, Body);
  if (body instanceof Response) return body;

  const billing = billingConfig();
  if (!billing) return apiError(503, "checkout_unavailable", "Checkout isn't open yet.");
  let entry: CatalogEntry | null;
  try {
    entry = buildCatalog(billing.prices).byItem(body.item);
  } catch {
    return apiError(503, "checkout_unavailable", "Checkout isn't open yet.");
  }
  if (!entry) return apiError(404, "not_on_sale", "That item isn't on sale right now.");
  const admin = createServiceSupabase(ctx.config);
  const paddle = billing.apiKey ? createPaddleApi(billing.apiKey, billing.environment) : null;

  if (entry.kind === "plan") {
    const { data, error } = await admin
      .from("billing_subscriptions")
      .select("id, plan, status")
      .eq("user_id", ctx.user.id)
      .neq("status", "canceled");
    if (error) return apiError(500, "server", "Something went wrong on our side.");
    const live = (data ?? []) as { id: string; plan: PlanId; status: string }[];
    if (live.some((s) => s.plan === entry.plan)) {
      return apiError(409, "already_subscribed", "You're already on this plan.");
    }
    const current = live.find((s) => s.status === "active");
    if (live.length > 0) {
      // trialing / past_due / paused: sort it out in the portal before changing plans.
      if (!current || !paddle) return apiError(409, "manage_billing", "Open Manage billing to change your plan.");
      const change = PLAN_LIMITS[entry.plan].rank > PLAN_LIMITS[current.plan].rank ? "upgrade" : "downgrade";
      const r = await paddle.changeSubscriptionPrice(current.id, entry.priceId, change);
      if ("error" in r) return apiError(502, "server", "Could not change your plan. Try again in a minute.");
      return json({ kind: "changed" });
    }
  }

  const email = ctx.user.email ?? null;
  let customerId: string | null = null;
  if (paddle && email && ctx.user.email_confirmed_at) {
    const c = await paddle.customerForEmail(email);
    if ("error" in c) return apiError(502, "server", "Checkout could not start. Try again in a minute.");
    customerId = c.id;
    const { error } = await admin.rpc("billing_link_customer", { p_user_id: ctx.user.id, p_customer_id: customerId });
    if (error) return apiError(500, "server", "Something went wrong on our side.");
  }

  return json({
    kind: "checkout",
    priceId: entry.priceId,
    customData: { user_id: ctx.user.id, user_sig: await signUserId(ctx.user.id, billing.checkoutSecrets[0]) },
    customerId,
    customerEmail: email,
  });
}
