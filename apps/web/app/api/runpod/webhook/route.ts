import type { RunpodStatusResponse } from "@/lib/render/contract";
import { serverConfig } from "@/lib/env";
import { createRenderPipeline } from "@/lib/server/renderContext";

/**
 * POST /api/runpod/webhook?job=<id>&t=<token> — RunPod's terminal callback. RunPod does not sign webhooks:
 * the per-job token is checked in constant time against its stored hash, and the job's state is then
 * re-read from RunPod with the API key; the body only says which attempt called. Idempotent (one terminal
 * transition per RunPod id). A non-2xx answer makes RunPod retry; the sweeper covers a webhook that never
 * lands.
 */
export async function POST(request: Request) {
  const config = serverConfig();
  if (!config?.runpod) return Response.json({ ok: false }, { status: 503 });
  const url = new URL(request.url);
  let body: RunpodStatusResponse | null = null;
  try {
    const raw = await request.text();
    if (raw.length <= 1_000_000) body = JSON.parse(raw) as RunpodStatusResponse;
  } catch {
    body = null;
  }
  const outcome = await createRenderPipeline(config).webhook(url.searchParams.get("job"), url.searchParams.get("t"), body, url.origin);
  return Response.json({ ok: outcome.status < 300 }, { status: outcome.status, headers: { "Cache-Control": "no-store" } });
}
