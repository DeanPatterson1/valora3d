import { billingConfig, serverConfig } from "@/lib/env";
import { handleWebhook } from "@/lib/billing/webhook";
import { createServiceSupabase } from "@/lib/supabase/server";

/**
 * POST /api/billing/webhook — the Paddle notification destination. Not cookie-authenticated (no
 * same-origin check): the HMAC signature is the authentication. See lib/billing/webhook.ts.
 */
export async function POST(request: Request) {
  const billing = billingConfig();
  const config = serverConfig();
  if (!billing || !config) {
    return Response.json({ error: "not_configured" }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
  const admin = createServiceSupabase(config);
  return handleWebhook(request, billing, (args) => admin.rpc("billing_apply_event", args), Date.now(), (e) =>
    admin.rpc("log_billing_webhook_error", {
      p_stage: e.stage,
      p_event_id: e.eventId ?? null,
      p_event_type: e.eventType ?? null,
      p_code: e.code ?? null,
      p_message: e.message,
    }),
  );
}
