import { z } from "zod";
import { JOB_STATUSES } from "@/lib/admin/types";
import { json, requireAdmin } from "@/lib/server/admin";
import { listJobs } from "@/lib/server/adminQueries";
import { apiError } from "@/lib/supabase/server";

const Query = z.object({
  status: z.enum(JOB_STATUSES).optional(),
  user: z.uuid().optional(),
  before: z.iso.datetime({ offset: true }).optional(),
  limit: z.coerce.number().int().min(1).max(200).default(50),
});

/** GET /api/admin/renders?status=&user=&before=&limit= — recent render jobs, newest first. Admins only. */
export async function GET(request: Request) {
  const ctx = await requireAdmin();
  if (ctx instanceof Response) return ctx;
  const params = Object.fromEntries([...new URL(request.url).searchParams].filter(([, v]) => v !== ""));
  const q = Query.safeParse(params);
  if (!q.success) return apiError(400, "invalid_request", "Unknown filter.");
  try {
    const jobs = await listJobs(ctx.admin, { status: q.data.status, userId: q.data.user, before: q.data.before, limit: q.data.limit });
    return json({ jobs });
  } catch {
    return apiError(500, "server", "Could not load renders.");
  }
}
