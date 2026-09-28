import { z } from "zod";
import { CREDIT_COSTS } from "@/lib/pricing";
import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";
import { readBody, sqlErrorResponse } from "@/lib/server/api";
import type { LedgerRow } from "@/lib/services/supabase/rows";

const Body = z.object({
  reason: z.enum(["scene_generation", "prompt_edit", "preview_render"]),
  /** What the client believes it costs (negative). Must match the server price. */
  amount: z.number().int().negative(),
  projectId: z.uuid().nullable(),
  /** Client idempotency key: a retried request is charged once. */
  ref: z.string().regex(/^[A-Za-z0-9_-]{8,64}$/),
});

/**
 * POST /api/credits/spend — debits a non-render action. The price comes from lib/pricing on the
 * server; the SQL function checks the balance and writes the debit under a per-user lock.
 */
export async function POST(request: Request) {
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const body = await readBody(request, Body);
  if (body instanceof Response) return body;

  const cost = CREDIT_COSTS[body.reason];
  if (-body.amount !== cost) return apiError(409, "price_changed", "Prices changed. Reload the page and try again.");

  const admin = createServiceSupabase(ctx.config);
  const { data, error } = await admin.rpc("spend_credits", {
    p_user_id: ctx.user.id,
    p_amount: cost,
    p_reason: body.reason,
    p_ref: `spend:${ctx.user.id}:${body.ref}`,
    p_project_id: body.projectId,
  });
  if (error) return sqlErrorResponse(error);
  return Response.json({ transaction: data as LedgerRow }, { status: 201 });
}
