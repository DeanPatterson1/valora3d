import { z } from "zod";
import { FEEDBACK_STATUSES } from "@/lib/feedback/shared";
import { readBody } from "@/lib/server/api";
import { json, requireAdmin } from "@/lib/server/admin";
import { apiError } from "@/lib/supabase/server";

const Body = z.object({ status: z.enum(FEEDBACK_STATUSES) }).strict();
const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** POST /api/admin/feedback/:id {status} — triage one report (new / triaged / done). Admins only, same-origin. */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const ctx = await requireAdmin();
  if (ctx instanceof Response) return ctx;
  const { id } = await params;
  if (!ID.test(id)) return apiError(404, "not_found", "Not found.");
  const body = await readBody(request, Body);
  if (body instanceof Response) return body;
  const { data, error } = await ctx.admin.from("feedback").update({ status: body.status }).eq("id", id).select("id, status").maybeSingle();
  if (error) return apiError(500, "server", "Could not update feedback.");
  if (!data) return apiError(404, "not_found", "Not found.");
  return json({ feedback: data });
}
