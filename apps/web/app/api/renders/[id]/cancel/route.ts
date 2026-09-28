import { z } from "zod";
import type { RenderJobRow } from "@/lib/render/jobRow";
import { sameOrigin } from "@/lib/server/api";
import { createRenderPipeline, toClientJob } from "@/lib/server/renderContext";
import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";

/** POST /api/renders/:id/cancel — cancel at RunPod; credits come back only if the GPU had not started. */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!sameOrigin(request)) return apiError(403, "forbidden", "Cross-origin request refused.");
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const { id } = await params;
  if (!z.uuid().safeParse(id).success) return apiError(404, "not_found", "Render not found.");
  const { data: owned } = await ctx.userClient.from("render_jobs").select("*").eq("id", id).maybeSingle<RenderJobRow>();
  if (!owned) return apiError(404, "not_found", "Render not found.");
  const admin = createServiceSupabase(ctx.config);
  const result = await createRenderPipeline(ctx.config, admin).cancel(owned, new URL(request.url).origin);
  const headers = { "Cache-Control": "no-store" };
  if (!result.ok) {
    const job = result.job ? await toClientJob(ctx.config, result.job) : undefined;
    return Response.json({ error: { code: result.code, message: result.message }, ...(job ? { job } : {}) }, { status: result.status, headers });
  }
  return Response.json({ job: await toClientJob(ctx.config, result.value) }, { headers });
}
