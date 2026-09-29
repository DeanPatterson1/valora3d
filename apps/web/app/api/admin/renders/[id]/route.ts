import { z } from "@/lib/zod";
import { json, requireAdmin } from "@/lib/server/admin";
import { jobDetail } from "@/lib/server/adminQueries";
import { apiError } from "@/lib/supabase/server";

/** GET /api/admin/renders/:id — one job with its operator detail, log tail, pin, ledger and audit rows. */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const ctx = await requireAdmin();
  if (ctx instanceof Response) return ctx;
  const { id } = await params;
  if (!z.uuid().safeParse(id).success) return apiError(404, "not_found", "Render not found.");
  try {
    const detail = await jobDetail(ctx.admin, id);
    if (!detail) return apiError(404, "not_found", "Render not found.");
    return json(detail);
  } catch {
    return apiError(500, "server", "Could not load the render.");
  }
}
