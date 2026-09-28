import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";
import type { PublicSupabaseConfig } from "@/lib/env";

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

/**
 * Only same-origin paths survive as a post-login destination. The URL parser strips tabs and
 * newlines and treats `\` as `/`, so `/%09/evil.com` or `/\evil.com` would otherwise become
 * `//evil.com`: refuse control characters and backslashes, then resolve against a sentinel origin
 * and keep only a result that stayed on it.
 */
export function safeNextPath(raw: string | null | undefined, fallback = "/projects"): string {
  if (!raw || !raw.startsWith("/") || /[\u0000-\u001f\u007f\\]/.test(raw)) return fallback;
  let url: URL;
  try {
    url = new URL(raw, "http://sentinel.invalid");
  } catch {
    return fallback;
  }
  if (url.origin !== "http://sentinel.invalid") return fallback;
  return url.pathname + url.search + url.hash;
}

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

  if (!user && isProtectedPath(pathname)) {
    return redirectTo(`/login?next=${encodeURIComponent(pathname + search)}`);
  }
  if (user && isSignedOutOnlyPath(pathname)) {
    return redirectTo(safeNextPath(request.nextUrl.searchParams.get("next")));
  }
  return response;
}
