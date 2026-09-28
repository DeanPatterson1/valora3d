import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";
import { sameOrigin } from "@/lib/server/api";
import { R2Storage } from "@/lib/server/r2";

/**
 * DELETE /api/projects/:id — removes the project's model files from R2, then the project row
 * (uploads, versions and jobs cascade). Rows the caller does not own are invisible (RLS), so the
 * route answers 404 for them.
 */
export async function DELETE(request: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!sameOrigin(request)) return apiError(403, "forbidden", "Cross-origin request refused.");
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const { id } = await params;

  const { data: project } = await ctx.userClient.from("projects").select("id").eq("id", id).maybeSingle();
  if (!project) return apiError(404, "not_found", "Project not found.");

  const admin = createServiceSupabase(ctx.config);
  const { data: uploads } = await admin
    .from("uploads")
    .select("r2_key")
    .eq("project_id", id)
    .eq("user_id", ctx.user.id)
    .not("r2_key", "is", null);
  if (ctx.config.r2 && uploads?.length) {
    const r2 = new R2Storage(ctx.config.r2);
    try {
      for (const u of uploads as { r2_key: string }[]) await r2.delete(u.r2_key);
    } catch {
      return apiError(502, "server", "Could not delete the project's files. Try again in a minute.");
    }
  }

  const { error } = await ctx.userClient.from("projects").delete().eq("id", id);
  if (error) return apiError(500, "server", "Could not delete the project.");
  return new Response(null, { status: 204 });
}
