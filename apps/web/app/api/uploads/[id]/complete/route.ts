import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";
import { sameOrigin } from "@/lib/server/api";
import { R2Storage } from "@/lib/server/r2";
import { verifyUploadedObject } from "@/lib/uploads/complete";
import type { UploadRow } from "@/lib/services/supabase/rows";

/**
 * POST /api/uploads/:id/complete — after the browser's PUT. Verifies the object exists, its size
 * matches the declaration and the cap, and it starts with a glTF 2 binary header; then marks the
 * row ready (or rejected, deleting the object).
 */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!sameOrigin(request)) return apiError(403, "forbidden", "Cross-origin request refused.");
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const { id } = await params;
  if (!ctx.config.r2) return apiError(503, "not_configured", "File storage is not configured.");

  const admin = createServiceSupabase(ctx.config);
  const { data: row } = await admin
    .from("uploads")
    .select("*")
    .eq("id", id)
    .eq("user_id", ctx.user.id)
    .maybeSingle<UploadRow>();
  if (!row || row.source !== "upload" || !row.r2_key) return apiError(404, "not_found", "Upload not found.");
  if (row.status === "ready") return Response.json({ upload: row });
  if (row.status === "rejected") return apiError(422, "rejected", row.reject_reason ?? "The file was rejected.");

  const outcome = await verifyUploadedObject(new R2Storage(ctx.config.r2), row.r2_key, row.size_bytes);
  if (outcome.status === "missing") return apiError(409, "not_uploaded", "The file has not finished uploading.");

  const patch =
    outcome.status === "ready"
      ? { status: "ready", completed_at: new Date().toISOString() }
      : { status: "rejected", reject_reason: outcome.reason, completed_at: new Date().toISOString() };
  const { data: updated, error } = await admin
    .from("uploads")
    .update(patch)
    .eq("id", id)
    .eq("status", "pending")
    .select()
    .single();
  if (error) return apiError(500, "server", "Could not record the upload.");
  if (outcome.status === "rejected") return apiError(422, "rejected", outcome.reason);
  return Response.json({ upload: updated });
}
