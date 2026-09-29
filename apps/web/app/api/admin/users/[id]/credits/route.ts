import { z } from "zod";
import { readBody } from "@/lib/server/api";
import { adminSqlError, json, REQUEST_ID, requireAdmin } from "@/lib/server/admin";
import { apiError } from "@/lib/supabase/server";

const Body = z.object({
  amount: z.number().int().min(-100_000).max(100_000).refine((n) => n !== 0, "amount must not be zero"),
  reason: z.string().trim().min(3).max(500),
  request_id: z.string().regex(REQUEST_ID),
});

/**
 * POST /api/admin/users/:id/credits {amount, reason, request_id} — grant (+) or deduct (-) credits. One ledger
 * row (`admin_adjustment`) and one audit row naming the admin, in one transaction (admin_adjust_credits). The
 * same request_id is a replay and changes nothing.
 */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const ctx = await requireAdmin();
  if (ctx instanceof Response) return ctx;
  const body = await readBody(request, Body);
  if (body instanceof Response) return body;
  const { id } = await params;
  if (!z.uuid().safeParse(id).success) return apiError(404, "not_found", "User not found.");
  const { data, error } = await ctx.admin.rpc("admin_adjust_credits", {
    p_admin_id: ctx.user.id,
    p_user_id: id,
    p_amount: body.amount,
    p_reason: body.reason,
    p_request_id: `credits:${body.request_id}`,
  });
  if (error) return adminSqlError(error);
  return json({ result: data });
}
