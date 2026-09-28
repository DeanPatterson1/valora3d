import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";
import { readBody } from "@/lib/server/api";
import { R2Storage } from "@/lib/server/r2";
import { CreateUploadBody, isAllowedSampleUrl, uploadKey, validateDeclaredUpload } from "@/lib/uploads/validate";

/** Pending uploads one user may open per day before being told to slow down. */
const MAX_PENDING_PER_DAY = 30;

/**
 * POST /api/uploads
 * - `{ kind: "upload", projectId, fileName, sizeBytes, sha256? }` -> a pending upload row and a
 *   presigned PUT (size pinned in the signature) for `u/<userId>/<uuid>.glb`.
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

  const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
  const { count } = await admin
    .from("uploads")
    .select("id", { count: "exact", head: true })
    .eq("user_id", ctx.user.id)
    .gte("created_at", since);
  if ((count ?? 0) >= MAX_PENDING_PER_DAY) return apiError(429, "rate_limited", "Too many uploads today. Try again tomorrow.");

  const id = crypto.randomUUID();
  const key = uploadKey(ctx.user.id, id);
  const { data, error } = await admin
    .from("uploads")
    .insert({
      id,
      user_id: ctx.user.id,
      project_id: body.projectId,
      source: "upload",
      file_name: valid.value.fileName,
      format: "glb",
      r2_key: key,
      size_bytes: valid.value.sizeBytes,
      sha256: valid.value.sha256,
      status: "pending",
    })
    .select()
    .single();
  if (error) return apiError(500, "server", "Could not start the upload.");

  const putUrl = await new R2Storage(ctx.config.r2).presignPut(key, valid.value.sizeBytes);
  return Response.json({ upload: data, putUrl }, { status: 201, headers: { "Cache-Control": "no-store" } });
}
