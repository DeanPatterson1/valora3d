import { z } from "zod";
import { outputKey } from "@/lib/render/contract";
import type { RenderJobRow } from "@/lib/render/jobRow";
import { R2Storage } from "@/lib/server/r2";
import { RESULT_URL_SECONDS } from "@/lib/server/renderContext";
import { apiError, requireUser } from "@/lib/supabase/server";

const FILES = {
  video: { name: "video", ext: "mp4", type: "video/mp4" },
  poster: { name: "poster", ext: "jpg", type: "image/jpeg" },
} as const;

/** GET /api/renders/:id/download?file=video|poster — a short-lived presigned GET (attachment), owner only. */
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const { id } = await params;
  const which = new URL(request.url).searchParams.get("file") ?? "video";
  if (!z.uuid().safeParse(id).success || !(which in FILES)) return apiError(404, "not_found", "Render not found.");
  if (!ctx.config.r2) return apiError(503, "not_configured", "File storage is not configured.");
  // RLS: the user's own client returns nothing for someone else's job.
  const { data: row } = await ctx.userClient.from("render_jobs").select("*").eq("id", id).maybeSingle<RenderJobRow>();
  if (!row || row.status !== "succeeded") return apiError(404, "not_found", "Render not found.");
  if (row.expired_at) return apiError(410, "expired", "This render has expired and its files were deleted.");
  const file = FILES[which as keyof typeof FILES];
  const url = await new R2Storage(ctx.config.r2).presignGet(outputKey(row.user_id, row.id, file.name), RESULT_URL_SECONDS, {
    contentType: file.type,
    disposition: `attachment; filename="valora3d-${row.id.slice(0, 8)}.${file.ext}"`,
  });
  return Response.json({ url }, { headers: { "Cache-Control": "no-store" } });
}
