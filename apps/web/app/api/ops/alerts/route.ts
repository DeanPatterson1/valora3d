import { serverConfig } from "@/lib/env";
import { ownerMail, resendSender, runAlerts } from "@/lib/ops/run";
import { cronAuthorized } from "@/lib/server/cronAuth";
import { createServiceSupabase } from "@/lib/supabase/server";

/**
 * POST /api/ops/alerts — the Worker's cron (custom-worker.mjs, every 5 min, Bearer CRON_SECRET): immediate owner
 * alerts for WORKER_MISCONFIGURED, a failure rate over 20% across the last 20 renders, Paddle webhook errors and the
 * daily GPU budget being reached. At most one mail per kind per hour (lib/ops/alerts.ts).
 */
export async function POST(request: Request) {
  const config = serverConfig();
  if (!cronAuthorized(request, config)) return Response.json({ ok: false }, { status: 404 });
  const mail = ownerMail(config);
  try {
    const result = await runAlerts(createServiceSupabase(config), mail ? resendSender(mail) : null);
    return Response.json({ ok: true, mail: Boolean(mail), ...result }, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    console.error("[ops] alerts failed", error instanceof Error ? error.message : String(error));
    return Response.json({ ok: false }, { status: 500, headers: { "Cache-Control": "no-store" } });
  }
}
