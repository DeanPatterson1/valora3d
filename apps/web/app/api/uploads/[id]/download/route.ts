import { apiError, requireUser } from "@/lib/supabase/server";
import { R2Storage } from "@/lib/server/r2";
import type { UploadRow } from "@/lib/services/supabase/rows";

/** GET /api/uploads/:id/download — a short-lived presigned GET for the caller's own ready upload. */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const { id } = await params;
  if (!ctx.config.r2) return apiError(503, "not_configured", "File storage is not configured.");

  // The user's own client: RLS returns nothing for someone else's upload.
  const { data: row } = await ctx.userClient.from("uploads").select("*").eq("id", id).maybeSingle<UploadRow>();
  if (!row || row.status !== "ready" || !row.r2_key) return apiError(404, "not_found", "Upload not found.");

  const url = await new R2Storage(ctx.config.r2).presignGet(row.r2_key);
  return Response.json({ url }, { headers: { "Cache-Control": "no-store" } });
}
