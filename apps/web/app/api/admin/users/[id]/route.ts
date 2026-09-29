import { z } from "@/lib/zod";
import { json, requireAdmin } from "@/lib/server/admin";
import { userDetail } from "@/lib/server/adminQueries";
import { apiError } from "@/lib/supabase/server";

/** GET /api/admin/users/:id — plan, balance, ledger, jobs, uploads, billing and audit for one user. */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const ctx = await requireAdmin();
  if (ctx instanceof Response) return ctx;
  const { id } = await params;
  if (!z.uuid().safeParse(id).success) return apiError(404, "not_found", "User not found.");
  try {
    const detail = await userDetail(ctx.admin, id);
    if (!detail) return apiError(404, "not_found", "User not found.");
    return json(detail);
  } catch {
    return apiError(500, "server", "Could not load the user.");
  }
}
