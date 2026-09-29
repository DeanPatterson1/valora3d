import type { SupabaseClient, User as AuthUser } from "@supabase/supabase-js";
import type { ServerConfig } from "@/lib/env";
import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";

/**
 * The one gate for every /api/admin route (the proxy checks too; this is the authoritative check).
 * Signed out, not an admin, or no backend configured: all answer the same 403, so the route reveals nothing.
 * The admin check reads `public.admins` with the service role, after the session was verified with Supabase Auth.
 */
export type AdminContext = { config: ServerConfig; user: AuthUser; admin: SupabaseClient };

export const NO_STORE = { "Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow" } as const;

export const forbidden = () => apiError(403, "forbidden", "Forbidden.");

export async function requireAdmin(): Promise<AdminContext | Response> {
  const ctx = await requireUser();
  if (ctx instanceof Response) return forbidden();
  const admin = createServiceSupabase(ctx.config);
  const { data, error } = await admin.from("admins").select("user_id").eq("user_id", ctx.user.id).maybeSingle();
  if (error || !data) return forbidden();
  return { config: ctx.config, user: ctx.user, admin };
}

export function json(body: unknown, status = 200): Response {
  return Response.json(body, { status, headers: NO_STORE });
}

/** SQL raise codes from the admin_* functions, as API errors. */
export function adminSqlError(error: { code?: string; message: string }): Response {
  if (error.code === "42501") return forbidden();
  if (error.code === "P0002") return apiError(404, "not_found", "Not found.");
  if (error.code === "23505") return apiError(409, "conflict", "That request id was already used for a different action.");
  if (error.code === "22023") return apiError(400, "invalid_request", safeSqlMessage(error.message));
  return apiError(500, "server", "Something went wrong on our side.");
}

/** Our own raise messages are fixed strings; pass them through only when they look like one of ours. */
function safeSqlMessage(message: string): string {
  return /^[a-z0-9 ,.%'-]{3,160}$/i.test(message) ? message : "The request is not valid.";
}

export const REQUEST_ID = /^[A-Za-z0-9_-]{8,100}$/;
