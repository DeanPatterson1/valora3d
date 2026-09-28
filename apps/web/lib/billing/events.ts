import { z } from "zod";
import type { Catalog } from "./catalog";
import { verifyUserSig } from "./signature";

/**
 * Paddle webhook event -> one billing action for `public.billing_apply_event` (see
 * supabase/migrations/*_billing.sql for what each action does in the database).
 *
 * Pure apart from verifying the signed user id. Only the fields we use are parsed; anything we
 * cannot make sense of becomes an `ignore` action, which is recorded (so the event id is not
 * processed twice) and acknowledged.
 */

export type BillingAction =
  | {
      kind: "grant_pack";
      user_id: string | null;
      customer_id: string | null;
      transaction_id: string;
      credits: number;
      total_minor: number;
      currency_code: string | null;
    }
  | {
      kind: "grant_subscription";
      user_id: string | null;
      customer_id: string | null;
      transaction_id: string;
      subscription_id: string;
      plan: "creator" | "pro";
      credits: number;
      period_start: string | null;
      period_end: string;
      total_minor: number;
      currency_code: string | null;
    }
  | {
      kind: "subscription_state";
      user_id: string | null;
      customer_id: string | null;
      subscription_id: string;
      plan: "creator" | "pro";
      price_id: string;
      status: SubscriptionStatus;
      period_start: string | null;
      period_end: string | null;
      scheduled_change: unknown;
      canceled_at: string | null;
      updated_at: string | null;
    }
  | {
      kind: "reversal";
      adjustment_id: string;
      transaction_id: string;
      action: "refund" | "chargeback" | "chargeback_reverse";
      full: boolean;
      amount_minor: number;
    }
  | { kind: "ignore"; reason: string };

export type ParsedEvent = { eventId: string; eventType: string; occurredAt: string | null; action: BillingAction };

const SUBSCRIPTION_STATUSES = ["active", "trialing", "past_due", "paused", "canceled"] as const;
type SubscriptionStatus = (typeof SUBSCRIPTION_STATUSES)[number];

/** Transaction origins that pay for a plan period (first checkout, renewal, upgrade proration). */
const PLAN_GRANT_ORIGINS = new Set(["web", "api", "subscription_recurring", "subscription_update"]);

const Id = (prefix: string) => z.string().regex(new RegExp(`^${prefix}_[a-z0-9]+$`));
const Minor = z.union([z.string(), z.number()]).transform((v) => {
  const n = typeof v === "number" ? v : Number.parseInt(v, 10);
  return Number.isFinite(n) && n >= 0 ? Math.trunc(n) : 0;
});
const Period = z.object({ starts_at: z.string().nullish(), ends_at: z.string() }).nullish();
const CustomData = z.record(z.string(), z.unknown()).nullish();
const Item = z.object({
  price: z.object({ id: z.string() }).nullish(),
  price_id: z.string().nullish(),
  quantity: z.number().int().positive().nullish(),
});

const Envelope = z.object({
  event_id: Id("evt"),
  event_type: z.string().min(1).max(100),
  occurred_at: z.string().nullish(),
  data: z.record(z.string(), z.unknown()),
});

const Transaction = z.object({
  id: Id("txn"),
  status: z.string(),
  origin: z.string().nullish(),
  customer_id: Id("ctm").nullish(),
  subscription_id: Id("sub").nullish(),
  custom_data: CustomData,
  items: z.array(Item).default([]),
  billing_period: Period,
  currency_code: z.string().nullish(),
  details: z.object({ totals: z.object({ grand_total: Minor.nullish(), total: Minor.nullish() }).nullish() }).nullish(),
});

const Subscription = z.object({
  id: Id("sub"),
  status: z.string(),
  customer_id: Id("ctm").nullish(),
  custom_data: CustomData,
  items: z.array(Item).default([]),
  current_billing_period: Period,
  scheduled_change: z.unknown().optional(),
  canceled_at: z.string().nullish(),
  updated_at: z.string().nullish(),
});

const Adjustment = z.object({
  id: Id("adj"),
  action: z.string(),
  status: z.string(),
  type: z.string().nullish(),
  transaction_id: Id("txn"),
  totals: z.object({ total: Minor.nullish() }).nullish(),
});

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** The user id from custom data, only if its signature checks out. */
export async function signedUserId(customData: Record<string, unknown> | null | undefined, secret: string): Promise<string | null> {
  const userId = customData?.user_id;
  const sig = customData?.user_sig;
  if (typeof userId !== "string" || typeof sig !== "string" || !UUID.test(userId)) return null;
  return (await verifyUserSig(userId, sig, secret)) ? userId.toLowerCase() : null;
}

function priceIds(items: z.infer<typeof Item>[]): { priceId: string; quantity: number }[] {
  return items
    .map((i) => ({ priceId: i.price?.id ?? i.price_id ?? "", quantity: i.quantity ?? 1 }))
    .filter((i) => i.priceId);
}

async function transactionAction(data: unknown, catalog: Catalog, secret: string): Promise<BillingAction> {
  const parsed = Transaction.safeParse(data);
  if (!parsed.success) return { kind: "ignore", reason: "unreadable transaction" };
  const t = parsed.data;
  if (t.status !== "completed") return { kind: "ignore", reason: `transaction ${t.status}` };
  const lines = priceIds(t.items).map((l) => ({ ...l, entry: catalog.byPriceId(l.priceId) }));
  const userId = await signedUserId(t.custom_data, secret);
  const totals = t.details?.totals;
  const total = totals?.grand_total ?? totals?.total ?? 0;

  const planLine = lines.find((l) => l.entry?.kind === "plan");
  if (planLine?.entry?.kind === "plan") {
    if (!t.subscription_id) return { kind: "ignore", reason: "plan price without a subscription" };
    if (!PLAN_GRANT_ORIGINS.has(t.origin ?? "")) return { kind: "ignore", reason: `origin ${t.origin}` };
    if (!t.billing_period?.ends_at) return { kind: "ignore", reason: "subscription transaction without a period" };
    return {
      kind: "grant_subscription",
      user_id: userId,
      customer_id: t.customer_id ?? null,
      transaction_id: t.id,
      subscription_id: t.subscription_id,
      plan: planLine.entry.plan,
      credits: planLine.entry.credits,
      period_start: t.billing_period.starts_at ?? null,
      period_end: t.billing_period.ends_at,
      total_minor: total,
      currency_code: t.currency_code ?? null,
    };
  }

  const credits = lines.reduce((s, l) => s + (l.entry?.kind === "pack" ? l.entry.credits * l.quantity : 0), 0);
  if (credits <= 0) return { kind: "ignore", reason: "no catalog price in transaction" };
  return {
    kind: "grant_pack",
    user_id: userId,
    customer_id: t.customer_id ?? null,
    transaction_id: t.id,
    credits,
    total_minor: total,
    currency_code: t.currency_code ?? null,
  };
}

async function subscriptionAction(data: unknown, catalog: Catalog, secret: string): Promise<BillingAction> {
  const parsed = Subscription.safeParse(data);
  if (!parsed.success) return { kind: "ignore", reason: "unreadable subscription" };
  const s = parsed.data;
  const status = SUBSCRIPTION_STATUSES.find((x) => x === s.status);
  if (!status) return { kind: "ignore", reason: `subscription status ${s.status}` };
  const plan = priceIds(s.items)
    .map((l) => catalog.byPriceId(l.priceId))
    .find((e) => e?.kind === "plan");
  if (!plan || plan.kind !== "plan") return { kind: "ignore", reason: "subscription without a catalog plan" };
  return {
    kind: "subscription_state",
    user_id: await signedUserId(s.custom_data, secret),
    customer_id: s.customer_id ?? null,
    subscription_id: s.id,
    plan: plan.plan,
    price_id: plan.priceId,
    status,
    period_start: s.current_billing_period?.starts_at ?? null,
    period_end: s.current_billing_period?.ends_at ?? null,
    scheduled_change: s.scheduled_change ?? null,
    canceled_at: s.canceled_at ?? null,
    updated_at: s.updated_at ?? null,
  };
}

function adjustmentAction(data: unknown): BillingAction {
  const parsed = Adjustment.safeParse(data);
  if (!parsed.success) return { kind: "ignore", reason: "unreadable adjustment" };
  const a = parsed.data;
  // Refunds wait for Paddle's approval (adjustment.updated -> approved); chargebacks arrive approved.
  if (a.status !== "approved") return { kind: "ignore", reason: `adjustment ${a.status}` };
  if (a.action !== "refund" && a.action !== "chargeback" && a.action !== "chargeback_reverse") {
    return { kind: "ignore", reason: `adjustment action ${a.action}` };
  }
  return {
    kind: "reversal",
    adjustment_id: a.id,
    transaction_id: a.transaction_id,
    action: a.action,
    full: a.type === "full",
    amount_minor: a.totals?.total ?? 0,
  };
}

/** Parses a verified webhook body. Returns null when it is not a Paddle event at all. */
export async function parseWebhookEvent(rawBody: string, catalog: Catalog, secret: string): Promise<ParsedEvent | null> {
  let json: unknown;
  try {
    json = JSON.parse(rawBody);
  } catch {
    return null;
  }
  const env = Envelope.safeParse(json);
  if (!env.success) return null;
  const { event_id, event_type, occurred_at, data } = env.data;
  let action: BillingAction;
  if (event_type === "transaction.completed") action = await transactionAction(data, catalog, secret);
  else if (event_type.startsWith("subscription.")) action = await subscriptionAction(data, catalog, secret);
  else if (event_type === "adjustment.created" || event_type === "adjustment.updated") action = adjustmentAction(data);
  else action = { kind: "ignore", reason: `event ${event_type}` };
  return { eventId: event_id, eventType: event_type, occurredAt: occurred_at ?? null, action };
}
