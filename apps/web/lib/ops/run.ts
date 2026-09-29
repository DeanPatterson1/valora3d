import type { SupabaseClient } from "@supabase/supabase-js";
import type { ServerConfig } from "@/lib/env";
import { ALERT_INTERVAL_SECONDS, alertsFrom, digestEmail, sendOwnerMail, type AlertSignals, type Digest, type OwnerMailConfig } from "./alerts";

type Rpc = Pick<SupabaseClient, "rpc">;
export type Send = (mail: { subject: string; text: string }, idempotencyKey: string) => Promise<void>;

/** Where owner mail goes, or null when OWNER_ALERT_EMAIL or RESEND_API_KEY is missing (then nothing is sent). */
export function ownerMail(config: ServerConfig): OwnerMailConfig | null {
  if (!config.ownerAlertEmail || !config.email) return null;
  return { resendApiKey: config.email.resendApiKey, from: config.email.from, to: config.ownerAlertEmail };
}

export function resendSender(cfg: OwnerMailConfig): Send {
  return (mail, key) => sendOwnerMail(cfg, mail, key);
}

/**
 * One alert check: read the signals, and for each alert whose kind has not been mailed in the last hour, claim it and
 * mail it. Without a mail config the alerts are only reported (and not claimed, so they go out once mail is set up).
 */
export async function runAlerts(admin: Rpc, send: Send | null, now = new Date()): Promise<{ alerts: string[]; sent: string[] }> {
  const { data, error } = await admin.rpc("ops_alert_signals");
  if (error) throw new Error(`ops_alert_signals failed: ${error.message}`);
  const alerts = alertsFrom(data as AlertSignals);
  const sent: string[] = [];
  if (send) {
    for (const alert of alerts) {
      const claimed = await admin.rpc("claim_owner_alert", { p_kind: alert.kind, p_min_interval_seconds: ALERT_INTERVAL_SECONDS });
      if (claimed.error || claimed.data !== true) continue;
      await send(alert, `alert-${alert.kind}-${now.toISOString().slice(0, 13)}`);
      sent.push(alert.kind);
    }
  }
  return { alerts: alerts.map((a) => a.kind), sent };
}

/** The daily digest: once per ~day (claimed), covering the last 24 hours. */
export async function runDigest(admin: Rpc, send: Send | null, now = new Date()): Promise<{ sent: boolean; reason?: string }> {
  if (!send) return { sent: false, reason: "mail not configured" };
  const claimed = await admin.rpc("claim_owner_alert", { p_kind: "daily_digest", p_min_interval_seconds: 20 * 3600 });
  if (claimed.error) throw new Error(`claim_owner_alert failed: ${claimed.error.message}`);
  if (claimed.data !== true) return { sent: false, reason: "already sent today" };
  const { data, error } = await admin.rpc("ops_daily_digest", { p_since: new Date(now.getTime() - 24 * 3600_000).toISOString() });
  if (error) throw new Error(`ops_daily_digest failed: ${error.message}`);
  const day = now.toISOString().slice(0, 10);
  await send(digestEmail(data as Digest, day), `digest-${day}`);
  return { sent: true };
}
