import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { PublicSupabaseConfig } from "@/lib/env";
import { safeNextPath } from "@/lib/nav/safePath";

/** App routes that need a signed-in user. Everything else (landing, auth pages, API) is public at the proxy; API routes check the session themselves. */
const PROTECTED_PREFIXES = ["/projects", "/profile", "/settings", "/dev"] as const;

/** Auth pages a signed-in user is bounced away from. */
const SIGNED_OUT_ONLY = ["/login", "/signup"] as const;

const matches = (pathname: string, prefix: string) => pathname === prefix || pathname.startsWith(`${prefix}/`);

export function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PREFIXES.some((p) => matches(pathname, p));
}

export function isSignedOutOnlyPath(pathname: string): boolean {
  return SIGNED_OUT_ONLY.some((p) => matches(pathname, p));
}

/** The owner console and its API. Admins only; everyone else gets a 404 page or a 403, never a login redirect. */
export function isAdminPath(pathname: string): boolean {
  return matches(pathname, "/admin") || matches(pathname, "/api/admin");
}

/** Headers on every admin response: never indexed, never cached. */
export const ADMIN_HEADERS = { "X-Robots-Tag": "noindex, nofollow", "Cache-Control": "private, no-store" } as const;

/**
 * Whether a signed-in user may use /admin. Reads `public.admins` with the USER's session: RLS lets a user see
 * only their own row, so this answers "am I an admin?" and nothing else. Any error is a no (fail closed).
 * The API routes check again with the service role (lib/server/admin.ts).
 */
export async function isAdminUser(
  supabase: Pick<SupabaseClient, "from">,
  userId: string,
): Promise<boolean> {
  try {
    const { data, error } = await supabase.from("admins").select("user_id").eq("user_id", userId).maybeSingle();
    return !error && Boolean(data);
  } catch {
    return false;
  }
}

export { safeNextPath };

/**
 * Refreshes the Supabase session cookie on every matched request and enforces sign-in on app
 * routes server-side. Follows the @supabase/ssr pattern: cookies written during `getUser()` are
 * copied onto whatever response leaves the proxy.
 */
export async function updateSession(request: NextRequest, config: PublicSupabaseConfig): Promise<NextResponse> {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(config.url, config.anonKey, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (list, headers) => {
        list.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        list.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
        Object.entries(headers ?? {}).forEach(([k, v]) => response.headers.set(k, v));
      },
    },
  });

  // getUser() validates the JWT with Supabase Auth; do not trust the cookie payload alone.
  const { data } = await supabase.auth.getUser();
  const user = data.user;
  const { pathname, search } = request.nextUrl;

  const redirectTo = (path: string) => {
    const url = request.nextUrl.clone();
    const [p, q] = path.split("?");
    url.pathname = p;
    url.search = q ? `?${q}` : "";
    const res = NextResponse.redirect(url);
    response.cookies.getAll().forEach((c) => res.cookies.set(c));
    // A redirect may carry a refreshed session cookie: never let a cache keep it.
    res.headers.set("Cache-Control", "private, no-store");
    return res;
  };

  if (isAdminPath(pathname)) {
    const allowed = user ? await isAdminUser(supabase, user.id) : false;
    const out = allowed
      ? response
      : pathname.startsWith("/api/")
        ? NextResponse.json({ error: { code: "forbidden", message: "Forbidden." } }, { status: 403 })
        : // Not advertised: the same 404 page as any unknown address (the proxy rewrites; a layout notFound() would stream after a 200).
          NextResponse.rewrite(new URL("/__not-found", request.url));
    if (out !== response) response.cookies.getAll().forEach((c) => out.cookies.set(c));
    Object.entries(ADMIN_HEADERS).forEach(([k, v]) => out.headers.set(k, v));
    return out;
  }

  if (!user && isProtectedPath(pathname)) {
    return redirectTo(`/login?next=${encodeURIComponent(pathname + search)}`);
  }
  if (user && isSignedOutOnlyPath(pathname)) {
    return redirectTo(safeNextPath(request.nextUrl.searchParams.get("next")));
  }
  return response;
}
