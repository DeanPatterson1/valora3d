import { getCloudflareContext } from "@opennextjs/cloudflare";
import { apiError } from "@/lib/supabase/server";

type Limiter = { limit: (options: { key: string }) => Promise<{ success: boolean }> };
// Only used by next dev / next start outside Workers. A fixed global bucket avoids unbounded maps.
let localWindow = 0;
let localCount = 0;

export async function limitHygieneRequest(request: Request): Promise<Response | null> {
  let limiter: Limiter | undefined;
  try {
    limiter = (getCloudflareContext().env as unknown as { HYGIENE_RATE_LIMITER?: Limiter }).HYGIENE_RATE_LIMITER;
    if (!limiter) return apiError(503, "unavailable", "Please try again later.");
  } catch {
    // No Cloudflare context exists on the standalone Next server.
  }
  let allowed: boolean;
  if (limiter) {
    try {
      // Cloudflare supplies this header. Never persist it or accept forwarded headers as a substitute.
      const key = `${new URL(request.url).pathname}:${request.headers.get("cf-connecting-ip") ?? "unknown"}`;
      allowed = (await limiter.limit({ key })).success;
    } catch {
      return apiError(503, "unavailable", "Please try again later.");
    }
  } else {
    const window = Math.floor(Date.now() / 60_000);
    if (window !== localWindow) { localWindow = window; localCount = 0; }
    allowed = ++localCount <= 10;
  }
  return allowed ? null : new Response(null, { status: 429, headers: { "Retry-After": "60", "Cache-Control": "no-store" } });
}

/**
 * Caps actual streamed bytes as well as Content-Length, before JSON decoding. `textPlain` also accepts a
 * `text/plain` body (what navigator.sendBeacon can send without a CORS preflight).
 */
export async function readLimitedJson(request: Request, maxBytes: number, options: { textPlain?: boolean } = {}): Promise<unknown | Response> {
  const type = request.headers.get("content-type")?.toLowerCase() ?? "";
  if (!type.startsWith("application/json") && !(options.textPlain && type.startsWith("text/plain"))) {
    return apiError(415, "invalid_request", "Expected JSON.");
  }
  if (Number(request.headers.get("content-length")) > maxBytes) return apiError(413, "too_large", "Request too large.");
  const reader = request.body?.getReader();
  if (!reader) return apiError(400, "invalid_request", "Expected a body.");
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) {
        await reader.cancel();
        return apiError(413, "too_large", "Request too large.");
      }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    return apiError(400, "invalid_request", "Invalid JSON.");
  } finally {
    reader.releaseLock();
  }
}
