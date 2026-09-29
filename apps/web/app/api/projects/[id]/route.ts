import { z } from "zod";
import { log } from "@/lib/server/log";
import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";
import { sameOrigin } from "@/lib/server/api";
import { R2Storage } from "@/lib/server/r2";
import { SupabasePurgeStore, drainStoragePurges } from "@/lib/server/storagePurge";

/** R2 requests this route may spend deleting at once; whatever is left the cron sweep finishes. */
const PURGE_BUDGET = 150;

/**
 * DELETE /api/projects/:id — the ONLY way to delete a project (users have no DELETE on `projects`, so the files
 * cannot be orphaned by deleting through PostgREST). The service role deletes the row; uploads, versions, jobs
 * and shares cascade, and row triggers queue every model file and render output (`r/<uid>/<job>/`) they owned
 * in storage_purge_queue in the same transaction. The queue is then drained as far as the budget allows here;
 * the cron sweep finishes the rest. A project with a render still queued or running is refused: cancel it first.
 * Rows the caller does not own are invisible (RLS), so the route answers 404 for them.
 */
export async function DELETE(request: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!sameOrigin(request)) return apiError(403, "forbidden", "Cross-origin request refused.");
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const { id } = await params;
  if (!z.uuid().safeParse(id).success) return apiError(404, "not_found", "Project not found.");

  const { data: project } = await ctx.userClient.from("projects").select("id").eq("id", id).maybeSingle();
  if (!project) return apiError(404, "not_found", "Project not found.");

  const admin = createServiceSupabase(ctx.config);
  const { count: live, error: liveError } = await admin
    .from("render_jobs")
    .select("id", { count: "exact", head: true })
    .eq("project_id", id)
    .eq("user_id", ctx.user.id)
    .in("status", ["queued", "running"]);
  if (liveError) return apiError(500, "server", "Could not delete the project.");
  if ((live ?? 0) > 0) {
    return apiError(409, "render_in_progress", "A render in this project is still running. Cancel it or wait for it to finish, then delete the project.");
  }

  const { error } = await admin.from("projects").delete().eq("id", id).eq("user_id", ctx.user.id);
  if (error) return apiError(500, "server", "Could not delete the project.");

  if (ctx.config.r2) {
    await drainStoragePurges(
      { store: new SupabasePurgeStore(admin), r2: new R2Storage(ctx.config.r2) },
      { budget: PURGE_BUDGET, userId: ctx.user.id },
    ).catch(() => log("warn", "/api/projects/[id]", "files_delete_deferred", { userId: ctx.user.id }));
  }
  return new Response(null, { status: 204 });
}
