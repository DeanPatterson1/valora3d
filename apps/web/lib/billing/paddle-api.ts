import type { PaddleEnvironment } from "@/lib/env";

/**
 * The Paddle Billing API calls the app makes (server-side, with the secret API key). Everything
 * that moves credits arrives by webhook instead.
 */

export function paddleApiBase(env: PaddleEnvironment): string {
  return env === "production" ? "https://api.paddle.com" : "https://sandbox-api.paddle.com";
}

/**
 * Upgrade: charge the prorated difference now (the webhook tops up credits by the same share).
 * Downgrade: switch without billing anything. A prorated downgrade would refund part of the
 * higher plan to the Paddle balance while its credits stay granted, i.e. credits for free.
 */
export type PlanChange = "upgrade" | "downgrade";
const PRORATION: Record<PlanChange, string> = { upgrade: "prorated_immediately", downgrade: "do_not_bill" };

/** Subscription statuses that can still charge the customer. */
const LIVE_STATUSES = "active,trialing,past_due,paused";

export type PaddleApi = {
  createPortalSession(customerId: string, subscriptionIds: string[]): Promise<{ url: string } | { error: string }>;
  changeSubscriptionPrice(subscriptionId: string, priceId: string, change: PlanChange): Promise<{ ok: true } | { error: string }>;
  cancelSubscriptionNow(subscriptionId: string): Promise<{ ok: true } | { error: string }>;
  /** Subscriptions Paddle can still bill for this customer, whether or not our webhook saw them. */
  listLiveSubscriptions(customerId: string): Promise<{ ids: string[] } | { error: string }>;
  /** The Paddle customer for an email, created if there is none. */
  customerForEmail(email: string): Promise<{ id: string } | { error: string }>;
};

export function createPaddleApi(apiKey: string, env: PaddleEnvironment, fetchImpl: typeof fetch = fetch): PaddleApi {
  const base = paddleApiBase(env);
  const call = async (method: string, path: string, body?: unknown): Promise<{ ok: boolean; json: unknown; status: number }> => {
    const res = await fetchImpl(`${base}${path}`, {
      method,
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json", "Paddle-Version": "1" },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    let json: unknown = null;
    try {
      json = await res.json();
    } catch {
      json = null;
    }
    return { ok: res.ok, json, status: res.status };
  };
  const errorOf = (json: unknown, status: number) =>
    ((json as { error?: { code?: string } } | null)?.error?.code ?? `http_${status}`);
  const ids = (json: unknown, prefix: string) =>
    (((json as { data?: unknown } | null)?.data ?? []) as { id?: unknown }[])
      .map((d) => d?.id)
      .filter((id): id is string => typeof id === "string" && id.startsWith(prefix));

  return {
    async createPortalSession(customerId, subscriptionIds) {
      const r = await call("POST", `/customers/${encodeURIComponent(customerId)}/portal-sessions`,
        subscriptionIds.length ? { subscription_ids: subscriptionIds.slice(0, 25) } : {});
      const url = (r.json as { data?: { urls?: { general?: { overview?: string } } } } | null)?.data?.urls?.general?.overview;
      if (!r.ok || typeof url !== "string" || !url.startsWith("https://")) return { error: errorOf(r.json, r.status) };
      return { url };
    },
    async changeSubscriptionPrice(subscriptionId, priceId, change) {
      const r = await call("PATCH", `/subscriptions/${encodeURIComponent(subscriptionId)}`, {
        items: [{ price_id: priceId, quantity: 1 }],
        proration_billing_mode: PRORATION[change],
      });
      return r.ok ? { ok: true } : { error: errorOf(r.json, r.status) };
    },
    async cancelSubscriptionNow(subscriptionId) {
      const r = await call("POST", `/subscriptions/${encodeURIComponent(subscriptionId)}/cancel`, { effective_from: "immediately" });
      return r.ok ? { ok: true } : { error: errorOf(r.json, r.status) };
    },
    async listLiveSubscriptions(customerId) {
      const r = await call("GET", `/subscriptions?customer_id=${encodeURIComponent(customerId)}&status=${LIVE_STATUSES}&per_page=50`);
      return r.ok ? { ids: ids(r.json, "sub_") } : { error: errorOf(r.json, r.status) };
    },
    async customerForEmail(email) {
      const found = await call("GET", `/customers?email=${encodeURIComponent(email)}`);
      if (!found.ok) return { error: errorOf(found.json, found.status) };
      const existing = ids(found.json, "ctm_")[0];
      if (existing) return { id: existing };
      const created = await call("POST", "/customers", { email });
      const id = (created.json as { data?: { id?: unknown } } | null)?.data?.id;
      if (!created.ok || typeof id !== "string" || !id.startsWith("ctm_")) return { error: errorOf(created.json, created.status) };
      return { id };
    },
  };
}
