import { z } from "@/lib/zod";
import { json, requireAdmin } from "@/lib/server/admin";
import { auditLog } from "@/lib/server/adminQueries";
import { apiError } from "@/lib/supabase/server";

const Limit = z.coerce.number().int().min(1).max(500).default(100);

/** GET /api/admin/audit?limit= — every admin action, newest first. Admins only. */
export async function GET(request: Request) {
  const ctx = await requireAdmin();
  if (ctx instanceof Response) return ctx;
  const limit = Limit.safeParse(new URL(request.url).searchParams.get("limit") ?? undefined);
  if (!limit.success) return apiError(400, "invalid_request", "Bad limit.");
  try {
    return json({ audit: await auditLog(ctx.admin, limit.data) });
  } catch {
    return apiError(500, "server", "Could not load the audit log.");
  }
}
