import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";
import { createClient, type SupabaseClient, type User as AuthUser } from "@supabase/supabase-js";
import { serverConfig, type ServerConfig } from "@/lib/env";

/**
 * Server-side Supabase clients for route handlers and server components.
 *
 * - `createRequestSupabase()` acts as the signed-in user (anon key + session cookie, RLS applies).
 * - `createServiceSupabase()` is the service role: it bypasses RLS and is used only inside API
 *   routes, after the route has resolved the caller with `requireUser()`.
 */

export async function createRequestSupabase(config: ServerConfig): Promise<SupabaseClient> {
  const store = await cookies();
  return createServerClient(config.supabase.url, config.supabase.anonKey, {
    cookies: {
      getAll: () => store.getAll(),
      setAll: (list) => {
        try {
          list.forEach(({ name, value, options }) => store.set(name, value, options));
        } catch {
          // Called from a server component, where cookies are read-only; the proxy refreshes them.
        }
      },
    },
  });
}

export function createServiceSupabase(config: ServerConfig): SupabaseClient {
  return createClient(config.supabase.url, config.supabase.serviceRoleKey, {
    auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
  });
}

export type AuthedContext = { config: ServerConfig; user: AuthUser; userClient: SupabaseClient };

/** JSON error body shared by every API route: `{ error: { code, message } }`. */
export function apiError(status: number, code: string, message: string): Response {
  return Response.json({ error: { code, message } }, { status, headers: { "Cache-Control": "no-store" } });
}

/**
 * Resolves the caller from the session cookie, verified against Supabase Auth (`getUser`, not the
 * unverified cookie payload). Returns a Response to send back when there is no usable session.
 */
export async function requireUser(): Promise<AuthedContext | Response> {
  const config = serverConfig();
  if (!config) return apiError(503, "not_configured", "The account service is not configured.");
  const userClient = await createRequestSupabase(config);
  const { data, error } = await userClient.auth.getUser();
  if (error || !data.user) return apiError(401, "unauthorized", "Sign in to continue.");
  return { config, user: data.user, userClient };
}
