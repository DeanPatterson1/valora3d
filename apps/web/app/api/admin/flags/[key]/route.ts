import { z } from "zod";
import { invalidateFlags } from "@/lib/flags/flags";
import { readBody } from "@/lib/server/api";
import { adminSqlError, json, REQUEST_ID, requireAdmin } from "@/lib/server/admin";
import { apiError } from "@/lib/supabase/server";

const Body = z
  .object({
    enabled: z.boolean().optional(),
    rollout_percent: z.number().int().min(0).max(100).optional(),
    allowlist: z.array(z.uuid()).max(200).optional(),
    value: z.number().min(0).max(1_000_000_000).nullable().optional(),
    reason: z.string().trim().min(3).max(500),
    request_id: z.string().regex(REQUEST_ID),
  })
  .strict();

/**
 * POST /api/admin/flags/:key {enabled?, rollout_percent?, allowlist?, value?, reason, request_id} — one audited change
 * (admin_set_flag: the row and an admin_audit_log entry with before/after, in one transaction; a replayed request id
 * changes nothing). Other isolates pick it up within the 30 s flag cache.
 */
export async function POST(request: Request, { params }: { params: Promise<{ key: string }> }) {
  const ctx = await requireAdmin();
  if (ctx instanceof Response) return ctx;
  const body = await readBody(request, Body);
  if (body instanceof Response) return body;
  const { key } = await params;
  if (!/^[a-z][a-z0-9_]{1,47}$/.test(key)) return apiError(404, "not_found", "Flag not found.");
  // A setting's value is replaced as sent (null = no limit); when the form leaves it out, keep the current one.
  let value = body.value;
  if (value === undefined) {
    const { data } = await ctx.admin.from("feature_flags").select("value").eq("key", key).maybeSingle<{ value: number | string | null }>();
    value = data?.value === null || data?.value === undefined ? null : Number(data.value);
  }
  const { data, error } = await ctx.admin.rpc("admin_set_flag", {
    p_admin_id: ctx.user.id,
    p_key: key,
    p_enabled: body.enabled ?? null,
    p_rollout: body.rollout_percent ?? null,
    p_allowlist: body.allowlist ?? null,
    p_value: value,
    p_reason: body.reason,
    p_request_id: `flag:${body.request_id}`,
  });
  if (error) return adminSqlError(error);
  invalidateFlags();
  return json({ result: data });
}
