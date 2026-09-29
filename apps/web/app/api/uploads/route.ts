import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";
import { readBody } from "@/lib/server/api";
import { UPLOAD_DAILY_CAP } from "@/lib/usageLimits";
import { R2Storage } from "@/lib/server/r2";
import { CreateUploadBody, isAllowedSampleUrl, uploadKey, validateDeclaredUpload } from "@/lib/uploads/validate";

/**
 * POST /api/uploads
 * - `{ kind: "upload", projectId, fileName, sizeBytes, sha256? }` -> a pending upload row and a
 *   presigned PUT (size pinned in the signature) for `u/<userId>/<uuid>.glb`. The row, the daily cap
 *   (UPLOAD_DAILY_CAP, counted from the append-only usage_events so deleting a project resets nothing) and the
 *   ownership check are one locked transaction: `create_upload`.
 * - `{ kind: "sample", projectId, fileName, sizeBytes, sampleUrl }` -> a ready sample row.
 */
export async function POST(request: Request) {
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const body = await readBody(request, CreateUploadBody);
  if (body instanceof Response) return body;

  // Ownership through RLS: the user's own client only sees their projects.
  const { data: project } = await ctx.userClient.from("projects").select("id").eq("id", body.projectId).maybeSingle();
  if (!project) return apiError(404, "not_found", "Project not found.");

  const admin = createServiceSupabase(ctx.config);

  if (body.kind === "sample") {
    if (!isAllowedSampleUrl(body.sampleUrl)) return apiError(400, "invalid_request", "Unknown sample.");
    const { data, error } = await admin
      .from("uploads")
      .insert({
        user_id: ctx.user.id,
        project_id: body.projectId,
        source: "sample",
        file_name: body.fileName,
        format: "glb",
        sample_url: body.sampleUrl,
        size_bytes: body.sizeBytes,
        status: "ready",
        completed_at: new Date().toISOString(),
      })
      .select()
      .single();
    if (error) return apiError(500, "server", "Could not save the sample.");
    return Response.json({ upload: data }, { status: 201 });
  }

  const valid = validateDeclaredUpload(body);
  if (!valid.ok) return apiError(400, valid.error.code, valid.error.message);
  if (!ctx.config.r2) return apiError(503, "not_configured", "File storage is not configured.");

  const id = crypto.randomUUID();
  const key = uploadKey(ctx.user.id, id);
  const { data, error } = await admin
    .rpc("create_upload", {
      p_user_id: ctx.user.id,
      p_project_id: body.projectId,
      p_upload_id: id,
      p_r2_key: key,
      p_file_name: valid.value.fileName,
      p_size_bytes: valid.value.sizeBytes,
      p_sha256: valid.value.sha256 ?? null,
    })
    .single();
  if (error?.code === "P0001" && error.message.startsWith("rate_limited")) {
    return apiError(429, "rate_limited", `You've started ${UPLOAD_DAILY_CAP} uploads today. Try again tomorrow.`);
  }
  if (error?.code === "P0002") return apiError(404, "not_found", "Project not found.");
  if (error || !data) return apiError(500, "server", "Could not start the upload.");

  const put = await new R2Storage(ctx.config.r2).presignPut(key, valid.value.sizeBytes);
  return Response.json(
    { upload: data, putUrl: put.url, putHeaders: put.headers },
    { status: 201, headers: { "Cache-Control": "no-store" } },
  );
}
