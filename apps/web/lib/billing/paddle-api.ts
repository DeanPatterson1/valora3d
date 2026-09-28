import type { PaddleEnvironment } from "@/lib/env";

/**
 * The two Paddle Billing API calls the app makes (server-side, with the secret API key):
 * a customer portal session and a subscription plan change. Everything else arrives by webhook.
 */

export function paddleApiBase(env: PaddleEnvironment): string {
  return env === "production" ? "https://api.paddle.com" : "https://sandbox-api.paddle.com";
}

export type PaddleApi = {
  createPortalSession(customerId: string, subscriptionIds: string[]): Promise<{ url: string } | { error: string }>;
  changeSubscriptionPrice(subscriptionId: string, priceId: string): Promise<{ ok: true } | { error: string }>;
  cancelSubscriptionNow(subscriptionId: string): Promise<{ ok: true } | { error: string }>;
};

export function createPaddleApi(apiKey: string, env: PaddleEnvironment, fetchImpl: typeof fetch = fetch): PaddleApi {
  const base = paddleApiBase(env);
  const call = async (method: string, path: string, body: unknown): Promise<{ ok: boolean; json: unknown; status: number }> => {
    const res = await fetchImpl(`${base}${path}`, {
      method,
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json", "Paddle-Version": "1" },
      body: JSON.stringify(body),
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

  return {
    async createPortalSession(customerId, subscriptionIds) {
      const r = await call("POST", `/customers/${encodeURIComponent(customerId)}/portal-sessions`,
        subscriptionIds.length ? { subscription_ids: subscriptionIds.slice(0, 25) } : {});
      const url = (r.json as { data?: { urls?: { general?: { overview?: string } } } } | null)?.data?.urls?.general?.overview;
      if (!r.ok || typeof url !== "string" || !url.startsWith("https://")) return { error: errorOf(r.json, r.status) };
      return { url };
    },
    async changeSubscriptionPrice(subscriptionId, priceId) {
      // Upgrades and downgrades take effect now, charged or credited pro rata; the resulting
      // transaction.completed (origin subscription_update) tops up the credits via the webhook.
      const r = await call("PATCH", `/subscriptions/${encodeURIComponent(subscriptionId)}`, {
        items: [{ price_id: priceId, quantity: 1 }],
        proration_billing_mode: "prorated_immediately",
      });
      return r.ok ? { ok: true } : { error: errorOf(r.json, r.status) };
    },
    async cancelSubscriptionNow(subscriptionId) {
      const r = await call("POST", `/subscriptions/${encodeURIComponent(subscriptionId)}/cancel`, { effective_from: "immediately" });
      return r.ok ? { ok: true } : { error: errorOf(r.json, r.status) };
    },
  };
}
