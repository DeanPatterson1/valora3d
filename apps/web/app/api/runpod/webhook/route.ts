import type { RunpodStatusResponse } from "@/lib/render/contract";
import { serverConfig } from "@/lib/env";
import { createRenderPipeline } from "@/lib/server/renderContext";

/** A status payload is a few KB; anything this large is not RunPod. */
const MAX_WEBHOOK_BODY_BYTES = 1_000_000;

/**
 * POST /api/runpod/webhook?job=<id>&t=<token> — RunPod's terminal callback. RunPod does not sign webhooks:
 * the per-job token is checked in constant time against its stored hash (before any other read), and the job's
 * state is then re-read from RunPod with the API key; the body only says which attempt called. Idempotent (one
 * terminal transition per RunPod id). A non-2xx answer makes RunPod retry; the sweeper covers a webhook that
 * never lands. The body is size-checked before it is read: a declared or actual size over the cap is refused.
 */
export async function POST(request: Request) {
  const config = serverConfig();
  if (!config?.runpod) return Response.json({ ok: false }, { status: 503 });
  const declared = Number(request.headers.get("content-length") ?? "0");
  if (!Number.isFinite(declared) || declared > MAX_WEBHOOK_BODY_BYTES) {
    return Response.json({ ok: false }, { status: 413, headers: { "Cache-Control": "no-store" } });
  }
  const url = new URL(request.url);
  const raw = await readCapped(request, MAX_WEBHOOK_BODY_BYTES);
  if (raw === null) return Response.json({ ok: false }, { status: 413, headers: { "Cache-Control": "no-store" } });
  let body: RunpodStatusResponse | null = null;
  try {
    body = raw ? (JSON.parse(raw) as RunpodStatusResponse) : null;
  } catch {
    body = null;
  }
  const outcome = await createRenderPipeline(config).webhook(url.searchParams.get("job"), url.searchParams.get("t"), body, url.origin);
  return Response.json({ ok: outcome.status < 300 }, { status: outcome.status, headers: { "Cache-Control": "no-store" } });
}

/** The body as text, or null once it passes `max` bytes (reading stops there; a chunked body can't lie its way past). */
async function readCapped(request: Request, max: number): Promise<string | null> {
  if (!request.body) return "";
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > max) {
      await reader.cancel().catch(() => {});
      return null;
    }
    chunks.push(value);
  }
  const all = new Uint8Array(total);
  let at = 0;
  for (const c of chunks) {
    all.set(c, at);
    at += c.byteLength;
  }
  return new TextDecoder().decode(all);
}
