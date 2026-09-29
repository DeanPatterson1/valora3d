import { json, requireAdmin } from "@/lib/server/admin";
import { planPricesMinor } from "@/lib/server/adminGrowth";
import { apiError } from "@/lib/supabase/server";

const WINDOWS = new Set([7, 30, 90]);

/**
 * GET /api/admin/growth?days=30 — the north star (weekly delivered renders), KPIs, funnel (over `days`: 7, 30 or 90)
 * and weekly cohorts: `admin_growth()` with the plan list prices from lib/pricing.ts for MRR. Admins only.
 */
export async function GET(request: Request) {
  const ctx = await requireAdmin();
  if (ctx instanceof Response) return ctx;
  const days = Number(new URL(request.url).searchParams.get("days") ?? "30");
  const { data, error } = await ctx.admin.rpc("admin_growth", {
    p_prices: planPricesMinor(),
    p_funnel_days: WINDOWS.has(days) ? days : 30,
  });
  if (error) return apiError(500, "server", "Could not load growth.");
  return json({ growth: data });
}
