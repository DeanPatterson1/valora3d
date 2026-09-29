import { serverConfig } from "@/lib/env";
import { ownerMail, resendSender, runDigest } from "@/lib/ops/run";
import { cronAuthorized } from "@/lib/server/cronAuth";
import { createServiceSupabase } from "@/lib/supabase/server";

/**
 * POST /api/ops/digest — the Worker's daily cron (custom-worker.mjs, 07:00 UTC, Bearer CRON_SECRET): one plain-text
 * mail to OWNER_ALERT_EMAIL with the last 24 hours (signups, renders, failures by code, GPU time and cost, refunds,
 * revenue). Claimed once per day, so a retried cron never sends two.
 */
export async function POST(request: Request) {
  const config = serverConfig();
  if (!cronAuthorized(request, config)) return Response.json({ ok: false }, { status: 404 });
  const mail = ownerMail(config);
  try {
    const result = await runDigest(createServiceSupabase(config), mail ? resendSender(mail) : null);
    return Response.json({ ok: true, ...result }, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    console.error("[ops] digest failed", error instanceof Error ? error.message : String(error));
    return Response.json({ ok: false }, { status: 500, headers: { "Cache-Control": "no-store" } });
  }
}
