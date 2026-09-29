import { json, requireAdmin } from "@/lib/server/admin";
import { apiError } from "@/lib/supabase/server";

const WINDOWS = new Set([1, 7, 30]);

/** GET /api/admin/errors?days=7 — client error reports grouped by (release, path, name): `admin_client_errors()`. */
export async function GET(request: Request) {
  const ctx = await requireAdmin();
  if (ctx instanceof Response) return ctx;
  const raw = Number(new URL(request.url).searchParams.get("days") ?? "7");
  const days = WINDOWS.has(raw) ? raw : 7;
  const { data, error } = await ctx.admin.rpc("admin_client_errors", { p_since: new Date(Date.now() - days * 86_400_000).toISOString() });
  if (error) return apiError(500, "server", "Could not load client errors.");
  return json({ errors: data ?? [], days });
}
