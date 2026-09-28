import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";
import { sameOrigin } from "@/lib/server/api";
import { R2Storage } from "@/lib/server/r2";
import { userPrefix } from "@/lib/uploads/validate";

/**
 * POST /api/account/delete — deletes the caller's account server-side: every R2 object under
 * `u/<userId>/`, then the auth user, whose foreign keys cascade to profiles, projects, uploads,
 * versions, render jobs and ledger rows.
 */
export async function POST(request: Request) {
  if (!sameOrigin(request)) return apiError(403, "forbidden", "Cross-origin request refused.");
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;

  if (ctx.config.r2) {
    try {
      await new R2Storage(ctx.config.r2).deletePrefix(userPrefix(ctx.user.id));
    } catch {
      // Keep the account (and the user's ability to retry) rather than orphan files.
      return apiError(502, "server", "Could not delete your files. Try again in a minute.");
    }
  }

  const admin = createServiceSupabase(ctx.config);
  const { error } = await admin.auth.admin.deleteUser(ctx.user.id);
  if (error) return apiError(500, "server", "Could not delete the account.");

  await ctx.userClient.auth.signOut().catch(() => undefined);
  return new Response(null, { status: 204 });
}
