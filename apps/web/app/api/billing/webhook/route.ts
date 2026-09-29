import { billingConfig, serverConfig } from "@/lib/env";
import { handleWebhook } from "@/lib/billing/webhook";
import { transactionSourceFromBody } from "@/lib/billing/source";
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
  // Read again only after the signature verified (apply runs after verification): the checkout's attribution.
  const copy = request.clone();
  return handleWebhook(
    request,
    billing,
    async (args) => {
      const result = await admin.rpc("billing_apply_event", args);
      // A granted payment takes the first-touch source that rode along in custom data (checkout route). Best-effort:
      // the grant is already committed, and the transaction keeps its signup source (a trigger) otherwise.
      if (!result.error && (result.data as { outcome?: string } | null)?.outcome === "granted"
          && (args.p_action.kind === "grant_pack" || args.p_action.kind === "grant_subscription")) {
        try {
          const source = transactionSourceFromBody(await copy.text());
          if (source) await admin.rpc("billing_set_transaction_source", { p_transaction_id: args.p_action.transaction_id, p_source: source });
        } catch {
          // Attribution is informational.
        }
      }
      return result;
    },
    Date.now(),
    (e) =>
      admin.rpc("log_billing_webhook_error", {
        p_stage: e.stage,
        p_event_id: e.eventId ?? null,
        p_event_type: e.eventType ?? null,
        p_code: e.code ?? null,
        p_message: e.message,
      }),
  );
}
