import { json, requireAdmin } from "@/lib/server/admin";
import { apiError } from "@/lib/supabase/server";

/** GET /api/admin/overview — signups, plans, credits, renders and revenue (admin_overview()). Admins only. */
export async function GET() {
  const ctx = await requireAdmin();
  if (ctx instanceof Response) return ctx;
  const { data, error } = await ctx.admin.rpc("admin_overview");
  if (error) return apiError(500, "server", "Could not load the overview.");
  return json({ overview: data });
}
