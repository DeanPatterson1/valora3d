import type { BillingConfig } from "@/lib/env";
import { buildCatalog, type Catalog } from "./catalog";
import { parseWebhookEvent, type BillingAction } from "./events";
import { verifyPaddleSignature } from "./signature";

/** Paddle payloads are a few KB; refuse anything absurd before hashing it. */
export const MAX_WEBHOOK_BYTES = 512 * 1024;

export type ApplyArgs = { p_event_id: string; p_event_type: string; p_occurred_at: string | null; p_action: BillingAction };
/** `public.billing_apply_event` via the service-role client (injected so tests need no database). */
export type ApplyEvent = (args: ApplyArgs) => PromiseLike<{ data: unknown; error: { code?: string; message: string } | null }>;

const reply = (status: number, body: Record<string, unknown>) =>
  Response.json(body, { status, headers: { "Cache-Control": "no-store" } });

/**
 * 1. Verify `Paddle-Signature` over the RAW body (HMAC-SHA256, timestamp within ±5 min).
 * 2. Map the event to one billing action (events.ts).
 * 3. `billing_apply_event` records the event id and applies the action in one transaction: a
 *    replay answers `duplicate`; a failure rolls back and returns 500 so Paddle retries.
 */
export async function handleWebhook(
  request: Request,
  billing: BillingConfig,
  apply: ApplyEvent,
  nowMs: number = Date.now(),
): Promise<Response> {
  const declared = Number(request.headers.get("content-length") ?? "0");
  if (declared > MAX_WEBHOOK_BYTES) return reply(413, { error: "too_large" });
  const raw = await request.text();
  if (raw.length > MAX_WEBHOOK_BYTES) return reply(413, { error: "too_large" });

  const verified = await verifyPaddleSignature(raw, request.headers.get("paddle-signature"), billing.webhookSecret, nowMs);
  if (!verified.ok) return reply(401, { error: "invalid_signature" });

  let catalog: Catalog;
  try {
    catalog = buildCatalog(billing.prices);
  } catch (e) {
    console.error("billing webhook: bad price configuration", (e as Error).message);
    return reply(500, { error: "misconfigured" });
  }
  const event = await parseWebhookEvent(raw, catalog, billing.webhookSecret);
  if (!event) return reply(400, { error: "invalid_event" });

  const { data, error } = await apply({
    p_event_id: event.eventId,
    p_event_type: event.eventType,
    p_occurred_at: event.occurredAt,
    p_action: event.action,
  });
  if (error) {
    console.error("billing webhook: apply failed", event.eventId, event.eventType, error.code, error.message);
    return reply(500, { error: "apply_failed" });
  }
  const outcome = (data as { outcome?: string } | null)?.outcome ?? "unknown";
  if (outcome === "unmatched") console.warn("billing webhook: no owner for", event.eventId, event.eventType);
  return reply(200, { received: true, outcome });
}
