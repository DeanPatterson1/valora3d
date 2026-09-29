import { z } from "@/lib/zod";
import { parseRenderParams } from "@/lib/render/params";
import type { RenderJobRow } from "@/lib/render/jobRow";
import { readBody } from "@/lib/server/api";
import { createRenderPipeline, toClientJob } from "@/lib/server/renderContext";
import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";

const CreateBody = z.object({
  project_id: z.uuid(),
  upload_id: z.uuid(),
  version_id: z.uuid().nullable().optional(),
  /** Checked against the worker contract below, with a field-level message. */
  params: z.unknown(),
  /** Client idempotency key: a retried "Render" click returns the same job, charged once. */
  idempotency_key: z.string().regex(/^[A-Za-z0-9_-]{8,128}$/),
});

const NO_STORE = { "Cache-Control": "no-store" };

/**
 * POST /api/renders — validate, debit (create_render_job), presign R2, submit to RunPod.
 * A failed submission is refunded before this answers.
 */
export async function POST(request: Request) {
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const body = await readBody(request, CreateBody);
  if (body instanceof Response) return body;
  const params = parseRenderParams(body.params ?? {});
  if (!params.ok) return apiError(400, "invalid_params", `The render settings are not valid (${params.message}).`);

  // Ownership through RLS: the user's own client only sees their projects.
  const { data: project } = await ctx.userClient.from("projects").select("id").eq("id", body.project_id).maybeSingle();
  if (!project) return apiError(404, "not_found", "Project not found.");

  const admin = createServiceSupabase(ctx.config);
  const pipeline = createRenderPipeline(ctx.config, admin);
  const result = await pipeline.create(
    {
      userId: ctx.user.id,
      projectId: body.project_id,
      uploadId: body.upload_id,
      versionId: body.version_id ?? null,
      params: params.value,
      idempotencyKey: body.idempotency_key,
    },
    new URL(request.url).origin,
  );
  if (!result.ok) {
    const job = result.job ? await toClientJob(ctx.config, result.job) : undefined;
    return Response.json({ error: { code: result.code, message: result.message }, ...(job ? { job } : {}) }, { status: result.status, headers: NO_STORE });
  }
  const job = await toClientJob(ctx.config, result.value.row);
  return Response.json({ job }, { status: result.value.replay ? 200 : 201, headers: NO_STORE });
}

/** GET /api/renders?project_id=<uuid> — the project's recent jobs, newest first (RLS: own rows only). */
export async function GET(request: Request) {
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const projectId = new URL(request.url).searchParams.get("project_id");
  if (!projectId || !z.uuid().safeParse(projectId).success) return apiError(400, "invalid_request", "project_id is required.");
  const { data, error } = await ctx.userClient
    .from("render_jobs")
    .select("*")
    .eq("project_id", projectId)
    .order("created_at", { ascending: false })
    .limit(20);
  if (error) return apiError(500, "server", "Could not load renders.");
  const jobs = await Promise.all(((data ?? []) as RenderJobRow[]).map((row) => toClientJob(ctx.config, row)));
  return Response.json({ jobs }, { headers: NO_STORE });
}
