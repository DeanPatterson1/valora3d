import { serverConfig } from "@/lib/env";
import { suppressionsFrom, verifySvix } from "@/lib/server/resendWebhook";
import { createServiceSupabase } from "@/lib/supabase/server";

/**
 * POST /api/resend/webhook — Resend's webhook destination for `email.bounced`, `email.complained` and
 * `email.suppressed`. Not cookie-authenticated: the Svix signature (RESEND_WEBHOOK_SECRET) is the authentication.
 * Each recipient goes on the suppression list (`record_email_suppression`), which stops product-tips and render mail
 * to it; account and billing mail still goes out. Answers 200 for events it ignores, 500 on a database error so
 * Resend retries. Needs a Cloudflare Access bypass like the Paddle webhook (README).
 */
const HEADERS = { "Cache-Control": "no-store" } as const;
const MAX_BYTES = 64 * 1024;

export async function POST(request: Request) {
  const config = serverConfig();
  if (!config?.resendWebhookSecret) return Response.json({ error: "not_configured" }, { status: 503, headers: HEADERS });
  if (Number(request.headers.get("content-length")) > MAX_BYTES) return Response.json({ error: "too_large" }, { status: 413, headers: HEADERS });
  const body = await request.text();
  if (body.length > MAX_BYTES) return Response.json({ error: "too_large" }, { status: 413, headers: HEADERS });

  const id = request.headers.get("svix-id");
  const ok = await verifySvix(config.resendWebhookSecret, {
    id,
    timestamp: request.headers.get("svix-timestamp"),
    signature: request.headers.get("svix-signature"),
  }, body);
  if (!ok) return Response.json({ error: "invalid_signature" }, { status: 401, headers: HEADERS });

  let event: unknown;
  try {
    event = JSON.parse(body);
  } catch {
    return Response.json({ ok: true, ignored: "not_json" }, { headers: HEADERS });
  }
  const list = suppressionsFrom(event);
  if (list.length === 0) return Response.json({ ok: true, suppressed: 0 }, { headers: HEADERS });

  const admin = createServiceSupabase(config);
  for (const s of list) {
    const { error } = await admin.rpc("record_email_suppression", { p_email: s.email, p_reason: s.reason, p_event_id: id });
    if (error) {
      console.error("[resend-webhook] suppression failed", error.code ?? "unknown");
      return Response.json({ error: "server" }, { status: 500, headers: HEADERS });
    }
  }
  return Response.json({ ok: true, suppressed: list.length }, { headers: HEADERS });
}
