import { z } from "zod";
import { canRetry, retryKey, retryRequestId } from "@/lib/admin/types";
import { parseRenderParams } from "@/lib/render/params";
import type { RenderJobRow } from "@/lib/render/jobRow";
import { readBody } from "@/lib/server/api";
import { json, requireAdmin } from "@/lib/server/admin";
import { createRenderPipeline } from "@/lib/server/renderContext";
import { apiError } from "@/lib/supabase/server";

const Body = z.object({ reason: z.string().trim().max(500).optional() });

/**
 * POST /api/admin/renders/:id/retry — resubmits a failed, retryable job through the normal pipeline
 * (create_render_job -> RunPod) on the owner's behalf, as a NEW job with the same model and settings. The user
 * is charged the normal cost (the failed attempt was refunded) and the plan limits apply as for any render.
 * Idempotent: the new job's idempotency key is derived from the failed job (in the `admin:` namespace users cannot
 * create keys in), so a failed job is retried at most once however often this is called.
 *
 * Audited fail-closed: the audit row (request id `retry:<job>`, written once) is recorded BEFORE anything is
 * resubmitted, and if it cannot be written nothing is retried. It records the admin's request; the new job it led
 * to is the one under `detail.idempotency_key`.
 */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const ctx = await requireAdmin();
  if (ctx instanceof Response) return ctx;
  const body = await readBody(request, Body);
  if (body instanceof Response) return body;
  const { id } = await params;
  if (!z.uuid().safeParse(id).success) return apiError(404, "not_found", "Render not found.");

  const { data: row, error } = await ctx.admin.from("render_jobs").select("*").eq("id", id).maybeSingle<RenderJobRow>();
  if (error) return apiError(500, "server", "Could not load the render.");
  if (!row) return apiError(404, "not_found", "Render not found.");
  if (!canRetry(row)) return apiError(409, "not_retryable", "Only a failed render the worker marked retryable can be retried.");
  const parsed = parseRenderParams(row.params ?? {});
  if (!parsed.ok) return apiError(409, "not_retryable", "This render's stored settings are no longer valid.");

  const key = retryKey(row.id);
  const audit = await ctx.admin.rpc("admin_record_action", {
    p_admin_id: ctx.user.id,
    p_action: "render_retry",
    p_target_type: "render_job",
    p_target_id: row.id,
    p_reason: body.reason ?? null,
    p_detail: { idempotency_key: key },
    p_request_id: retryRequestId(row.id),
  });
  // `false` = already recorded by an earlier call for this job: fine, the create below is a replay then.
  if (audit.error || typeof audit.data !== "boolean") {
    console.error("admin retry: audit write failed", row.id, audit.error?.code);
    return apiError(500, "server", "Could not record the retry in the audit log, so nothing was retried.");
  }

  const result = await createRenderPipeline(ctx.config, ctx.admin).create(
    {
      userId: row.user_id,
      projectId: row.project_id,
      uploadId: row.upload_id as string,
      versionId: row.version_id,
      params: parsed.value,
      idempotencyKey: key,
    },
    new URL(request.url).origin,
  );
  if (!result.ok) {
    return json({ error: { code: result.code, message: result.message }, ...(result.job ? { job_id: result.job.id } : {}) }, result.status);
  }
  const newJob = result.value.row;
  return json({ result: { replay: result.value.replay, job_id: newJob.id, status: newJob.status } }, result.value.replay ? 200 : 201);
}
