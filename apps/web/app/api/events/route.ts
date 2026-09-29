import { ATTRIBUTION_COOKIE } from "@/lib/analytics/attribution";
import { validateBatch } from "@/lib/analytics/events";
import { attributionFromCookie, saveSignupSource } from "@/lib/analytics/server";
import { serverConfig } from "@/lib/env";
import { sameOrigin } from "@/lib/server/api";
import { limitHygieneRequest, readLimitedJson } from "@/lib/server/hygieneRequest";
import { apiError, createRequestSupabase, createServiceSupabase } from "@/lib/supabase/server";

/** A batch is a few hundred bytes; 8 KiB leaves room for 25 small events and nothing else. */
const MAX_BYTES = 8 * 1024;

const accepted = () => new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });

/**
 * POST /api/events {session_id, events: [{event, props, path}]} — first-party product events from the browser
 * (lib/analytics/track.ts, sent with sendBeacon or fetch keepalive). Same-origin only, JSON only, 8 KiB, rate-limited
 * per IP (HYGIENE_RATE_LIMITER) and per session / user per hour (record_client_events). Only browser event names with
 * their allowlisted props are stored; a signed-in caller's account id is attached from the verified session. Always
 * 204 on a well-formed request, so a page never retries or reports analytics failures. Local mode drops the events.
 */
export async function POST(request: Request) {
  if (!sameOrigin(request)) return apiError(403, "forbidden", "Cross-origin request refused.");
  const config = serverConfig();
  // Local mode stores nothing, so it does not spend the dev server's shared hygiene bucket either.
  if (config) {
    const limited = await limitHygieneRequest(request);
    if (limited) return limited;
  }
  const raw = await readLimitedJson(request, MAX_BYTES, { textPlain: true });
  if (raw instanceof Response) return raw;
  const batch = validateBatch(raw);
  if (!batch) return apiError(400, "invalid_request", "Invalid events.");
  if (batch.events.length === 0 || !config) return accepted();

  let userId: string | null = null;
  const hasSession = /(?:^|;\s*)sb-[^=]+-auth-token/.test(request.headers.get("cookie") ?? "");
  if (hasSession) {
    try {
      const { data } = await (await createRequestSupabase(config)).auth.getUser();
      userId = data.user?.id ?? null;
    } catch {
      userId = null;
    }
  }

  const admin = createServiceSupabase(config);
  try {
    await admin.rpc("record_client_events", { p_session_id: batch.sessionId, p_user_id: userId, p_events: batch.events });
  } catch {
    // Best-effort by design.
  }
  // A new account whose confirm step was not seen by this browser still gets its first-touch source (SQL: once, and
  // only within a day of signing up).
  if (userId) {
    const cookie = request.headers.get("cookie")?.match(new RegExp(`(?:^|;\\s*)${ATTRIBUTION_COOKIE}=([^;]+)`))?.[1];
    if (cookie) await saveSignupSource(admin, userId, attributionFromCookie(cookie));
  }
  return accepted();
}
