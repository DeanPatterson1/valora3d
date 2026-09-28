import { serverConfig } from "@/lib/env";
import { createRenderPipeline } from "@/lib/server/renderContext";
import { timingSafeEqualStr } from "@/lib/server/webhookToken";

/**
 * POST /api/renders/sweep — re-polls render jobs nobody has heard from in a while and finalizes (or
 * refunds) them: the lost-webhook and dropped-submit backstop. Called by the Worker's cron trigger
 * (custom-worker.ts, wrangler.jsonc "triggers") with `Authorization: Bearer <CRON_SECRET>`.
 */
export async function POST(request: Request) {
  const config = serverConfig();
  if (!config?.cronSecret) return Response.json({ ok: false }, { status: 404 });
  const presented = request.headers.get("authorization")?.replace(/^Bearer\s+/i, "") ?? "";
  if (!timingSafeEqualStr(presented, config.cronSecret)) return Response.json({ ok: false }, { status: 404 });
  if (!config.runpod) return Response.json({ ok: true, checked: 0, finished: 0, note: "renderer not configured" });
  const result = await createRenderPipeline(config).sweep(new URL(request.url).origin);
  return Response.json({ ok: true, ...result }, { headers: { "Cache-Control": "no-store" } });
}
