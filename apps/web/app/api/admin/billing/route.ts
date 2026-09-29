import { json, requireAdmin } from "@/lib/server/admin";
import { billingOverview } from "@/lib/server/adminQueries";
import { apiError } from "@/lib/supabase/server";

/** GET /api/admin/billing — recent Paddle events and transactions, problem events and webhook errors. */
export async function GET() {
  const ctx = await requireAdmin();
  if (ctx instanceof Response) return ctx;
  try {
    return json(await billingOverview(ctx.admin));
  } catch {
    return apiError(500, "server", "Could not load billing.");
  }
}
