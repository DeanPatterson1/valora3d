import { SITE_URL } from "@/lib/site";

/**
 * Owner alerts and the daily digest (mail to OWNER_ALERT_EMAIL through Resend). Pure parts here; the routes
 * app/api/ops/alerts (every 5 min) and app/api/ops/digest (daily) wire them to the database and Resend.
 * Content is aggregates only: counts, codes, seconds and money. No emails, names, prompts or ids of users.
 */

export type AlertSignals = {
  worker_misconfigured: number;
  recent: { finished: number; failed: number };
  webhook_errors: number;
  gpu_seconds_today: number | string;
  daily_gpu_budget_seconds: number | string | null;
  active_renders: number;
  global_max_active_renders: number | string | null;
};

export const ALERT_KINDS = ["worker_misconfigured", "failure_rate", "billing_webhook_errors", "budget_tripped"] as const;
export type AlertKind = (typeof ALERT_KINDS)[number];
export type Alert = { kind: AlertKind; subject: string; text: string };

/** Failure rate over the last 20 finished renders above which the owner hears about it (only once 5+ have finished). */
export const FAILURE_RATE_THRESHOLD = 0.2;
export const FAILURE_RATE_MIN_JOBS = 5;
/** At most one mail per kind per hour (claim_owner_alert). */
export const ALERT_INTERVAL_SECONDS = 3600;

const n = (v: number | string | null | undefined): number | null => {
  if (v === null || v === undefined) return null;
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
};

const footer = (path: string) => `\n\nOpen the console: ${SITE_URL}${path}\n\nValora3D owner alerts (at most one of this kind per hour).`;

export function alertsFrom(s: AlertSignals): Alert[] {
  const out: Alert[] = [];
  if (s.worker_misconfigured > 0) {
    out.push({
      kind: "worker_misconfigured",
      subject: `Valora3D alert: render worker misconfigured (${s.worker_misconfigured} in the last hour)`,
      text:
        `${s.worker_misconfigured} render(s) failed with WORKER_MISCONFIGURED in the last hour. The worker image or its ` +
        `environment is wrong, so every render will fail until it is fixed. Credits were refunded automatically.` +
        footer("/admin/renders?status=failed"),
    });
  }
  const { finished, failed } = s.recent;
  if (finished >= FAILURE_RATE_MIN_JOBS && failed / finished > FAILURE_RATE_THRESHOLD) {
    out.push({
      kind: "failure_rate",
      subject: `Valora3D alert: ${Math.round((failed / finished) * 100)}% of recent renders failed`,
      text: `${failed} of the last ${finished} finished renders failed (alert above ${FAILURE_RATE_THRESHOLD * 100}%).` + footer("/admin/renders?status=failed"),
    });
  }
  if (s.webhook_errors > 0) {
    out.push({
      kind: "billing_webhook_errors",
      subject: `Valora3D alert: ${s.webhook_errors} Paddle webhook error(s) in the last hour`,
      text:
        `${s.webhook_errors} Paddle webhook deliveries failed in the last hour. Paddle retries them, but a payment may not ` +
        `have been credited yet.` + footer("/admin/billing"),
    });
  }
  const used = n(s.gpu_seconds_today);
  const budget = n(s.daily_gpu_budget_seconds);
  if (budget !== null && used !== null && used >= budget) {
    out.push({
      kind: "budget_tripped",
      subject: "Valora3D alert: daily GPU budget reached, new renders are paused",
      text:
        `Today's GPU use is ${Math.round(used)} s against a budget of ${Math.round(budget)} s (daily_gpu_budget_seconds). ` +
        `New renders get a friendly "high demand" message until midnight UTC, or until you raise the budget.` + footer("/admin/flags"),
    });
  }
  return out;
}

export type Digest = {
  since: string;
  until: string;
  signups: number;
  renders: { total: number; succeeded: number; failed: number; cancelled: number; in_flight: number; gpu_seconds: number | string; cost_usd: number | string };
  failures_by_code: Record<string, number>;
  refunds: { render_credits: number; billing_adjustments: number };
  revenue: { currency: string; gross_minor: number; transactions: number }[];
  webhook_errors: number;
  client_errors: number;
  paused: string[];
};

const money = (minor: number, currency: string) => `${currency} ${(Number(minor) / 100).toFixed(2)}`;

/** Plain-text daily digest. */
export function digestEmail(d: Digest, day: string): { subject: string; text: string } {
  const gpu = Number(d.renders.gpu_seconds) || 0;
  const cost = Number(d.renders.cost_usd) || 0;
  const failures = Object.entries(d.failures_by_code);
  const lines = [
    `Valora3D, last 24 hours (to ${d.until.slice(0, 16).replace("T", " ")} UTC)`,
    "",
    `Signups: ${d.signups}`,
    `Renders: ${d.renders.total} (${d.renders.succeeded} delivered, ${d.renders.failed} failed, ${d.renders.cancelled} cancelled, ${d.renders.in_flight} in flight)`,
    `GPU time: ${(gpu / 3600).toFixed(2)} h${cost > 0 ? `, est. $${cost.toFixed(2)}` : ""}`,
    failures.length ? `Failures by code: ${failures.map(([code, count]) => `${code} ${count}`).join(", ")}` : "Failures by code: none",
    `Refunds: ${d.refunds.render_credits} render credits refunded, ${d.refunds.billing_adjustments} payment refunds/chargebacks`,
    d.revenue.length
      ? `Revenue: ${d.revenue.map((r) => `${money(r.gross_minor, r.currency)} (${r.transactions})`).join(", ")}`
      : "Revenue: none",
    `Paddle webhook errors: ${d.webhook_errors}`,
    `Client errors: ${d.client_errors}`,
    ...(d.paused.length ? ["", `Switched OFF: ${d.paused.join(", ")}`] : []),
    "",
    `Growth and funnel: ${SITE_URL}/admin/growth`,
    "",
    "Valora3D daily digest",
  ];
  return { subject: `Valora3D daily: ${d.signups} signups, ${d.renders.succeeded} renders, ${d.renders.failed} failed (${day})`, text: lines.join("\n") };
}

export type OwnerMailConfig = { resendApiKey: string; from: string; to: string };

/** Sends one plain-text owner mail through Resend. The idempotency key stops a retried send doubling up (24 h). */
export async function sendOwnerMail(
  cfg: OwnerMailConfig,
  mail: { subject: string; text: string },
  idempotencyKey: string,
  fetchImpl: typeof fetch = (...args) => fetch(...args),
): Promise<void> {
  const res = await fetchImpl("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${cfg.resendApiKey}`, "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
    body: JSON.stringify({ from: cfg.from, to: [cfg.to], subject: mail.subject, text: mail.text }),
  });
  if (!res.ok) throw new Error(`Resend failed: ${res.status}`);
}
