import { z } from "@/lib/zod";
import type { RenderJobRow } from "@/lib/render/jobRow";
import { createRenderPipeline, toClientJob } from "@/lib/server/renderContext";
import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";

/**
 * GET /api/renders/:id — the job's state. When the row has not been refreshed recently this polls RunPod
 * (`/status`) and records the progress, so the studio sees stage and frame counts between webhooks.
 */
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const { id } = await params;
  if (!z.uuid().safeParse(id).success) return apiError(404, "not_found", "Render not found.");
  // RLS: nothing comes back for someone else's job.
  const { data: owned } = await ctx.userClient.from("render_jobs").select("*").eq("id", id).maybeSingle<RenderJobRow>();
  if (!owned) return apiError(404, "not_found", "Render not found.");
  const admin = createServiceSupabase(ctx.config);
  const row = await createRenderPipeline(ctx.config, admin).refresh(owned, new URL(request.url).origin);
  return Response.json({ job: await toClientJob(ctx.config, row) }, { headers: { "Cache-Control": "no-store" } });
}
