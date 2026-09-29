import { z } from "zod";
import { readBody } from "@/lib/server/api";
import { adminSqlError, json, REQUEST_ID, requireAdmin } from "@/lib/server/admin";
import { apiError } from "@/lib/supabase/server";

const Body = z.object({
  reason: z.string().trim().min(3).max(500),
  request_id: z.string().regex(REQUEST_ID),
});

/**
 * POST /api/admin/renders/:id/refund {reason, request_id} — refunds a failed or cancelled job through
 * refund_render_job (a job is refunded at most once) and writes one audit row, in one transaction
 * (admin_refund_render_job). The same request_id is a replay.
 */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const ctx = await requireAdmin();
  if (ctx instanceof Response) return ctx;
  const body = await readBody(request, Body);
  if (body instanceof Response) return body;
  const { id } = await params;
  if (!z.uuid().safeParse(id).success) return apiError(404, "not_found", "Render not found.");
  const { data, error } = await ctx.admin.rpc("admin_refund_render_job", {
    p_admin_id: ctx.user.id,
    p_job_id: id,
    p_reason: body.reason,
    p_request_id: `refund:${body.request_id}`,
  });
  if (error) {
    if (error.code === "22023" && /only failed or cancelled/.test(error.message)) {
      return apiError(409, "not_refundable", "Only a failed or cancelled render can be refunded.");
    }
    return adminSqlError(error);
  }
  return json({ result: data });
}
