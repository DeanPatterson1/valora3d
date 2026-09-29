import { NextRequest, NextResponse } from "next/server";
import { ATTRIBUTION_COOKIE, attributionCookieHeader, attributionFromVisit, shouldCaptureAttribution } from "@/lib/analytics/attribution";
import { publicSupabaseConfig, serverConfig } from "@/lib/env";
import { flag } from "@/lib/flags/flags";
import { log } from "@/lib/server/log";
import { createPublicShareReader, lookupPublicShare } from "@/lib/server/shareLookup";
import { goneResponse } from "@/lib/share/public";
import { contentSecurityPolicy, newNonce, withSecurityHeaders } from "@/lib/securityHeaders";
import { ADMIN_HEADERS, isAdminPath, updateSession } from "@/lib/supabase/proxy";

/** A public share page, `/r/<slug>` (not its /video or /poster routes, which answer 410 themselves). */
const SHARE_PAGE = /^\/r\/[A-Za-z0-9_-]{22,64}$/;

/**
 * Server-side session refresh + route protection (Next 16 `proxy`, formerly middleware).
 * Without Supabase configured the app runs on the in-browser fakes, whose client-side AuthGate
 * is the only gate, so the proxy passes everything through.
 * Every response gets the security headers and the nonce CSP (lib/securityHeaders.ts), including the ones this proxy
 * generates itself (410, admin 403 / 404 rewrites, the dev 404 rewrite). Pages that render under a nonce are dynamic:
 * see the README "Content-Security-Policy" section.
 */
export async function proxy(incoming: NextRequest) {
  // One nonce per request. Next reads it from the CSP on the REQUEST headers and stamps it on its inline scripts and
  // chunks while rendering, so every response below is built from `request` (with those headers), never a bare next().
  const nonce = newNonce();
  const csp = contentSecurityPolicy({ nonce });
  const headers = new Headers(incoming.headers);
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", csp);
  const request = new NextRequest(incoming, { headers });
  return withSecurityHeaders(withAttribution(request, await route(request)), csp);
}

/**
 * First-touch attribution (lib/analytics/attribution.ts): on a page visit that carries utm_* / ref or comes from
 * another site, and only when no attribution cookie exists yet, one first-party cookie records where the visitor came
 * from (90 days, SameSite=Lax, HttpOnly; no identifier). Skipped for API calls, prefetches, redirects and Global
 * Privacy Control. Saved on the account at signup and on each payment; see the privacy notice.
 */
function withAttribution(request: NextRequest, response: Response): Response {
  if (response.status !== 200) return response;
  const capture = shouldCaptureAttribution({
    method: request.method,
    pathname: request.nextUrl.pathname,
    headers: request.headers,
    hasCookie: request.cookies.has(ATTRIBUTION_COOKIE),
  });
  if (!capture) return response;
  const attribution = attributionFromVisit(request.nextUrl, request.headers.get("referer"));
  if (!attribution) return response;
  try {
    response.headers.append("Set-Cookie", attributionCookieHeader(attribution, request.nextUrl.protocol === "https:"));
  } catch {
    // An immutable response (none today) just goes without the cookie.
  }
  return response;
}

async function route(request: NextRequest): Promise<Response> {
  // The dev layout's notFound() streams after a 200 has gone out; rewrite to a missing route for a real 404.
  if (process.env.NODE_ENV === "production" && /^\/dev(\/|$)/.test(request.nextUrl.pathname)) {
    return NextResponse.rewrite(new URL("/__not-found", request.url), { request });
  }
  const config = publicSupabaseConfig();
  if (!config) {
    // Local mode: /admin renders its "requires the live backend" notice and the admin API answers 403.
    const response = NextResponse.next({ request });
    if (isAdminPath(request.nextUrl.pathname)) Object.entries(ADMIN_HEADERS).forEach(([k, v]) => response.headers.set(k, v));
    return response;
  }
  if (SHARE_PAGE.test(request.nextUrl.pathname)) return shareGate(request);
  // Kill switch (feature_flags.signups_enabled, 30 s cache): the sign-up page says so instead of failing on submit.
  // The database refuses new accounts on its own (signups_guard), Google sign-ups included.
  if (request.nextUrl.pathname === "/signup" && request.method === "GET" && serverConfig() && !(await flag("signups_enabled"))) {
    return NextResponse.rewrite(new URL("/signups-paused", request.url), { request });
  }
  return updateSession(request, config);
}

/**
 * A page cannot send 410, so a revoked or expired share link is answered here with the friendly 410 page.
 * Live and unknown slugs go on to the page (which renders the video, or a 404). The share page is public and
 * needs no session, so the session refresh is skipped for it.
 */
async function shareGate(request: NextRequest): Promise<Response> {
  const server = serverConfig();
  if (!server || (request.method !== "GET" && request.method !== "HEAD")) return NextResponse.next({ request });
  try {
    const slug = request.nextUrl.pathname.slice("/r/".length);
    const found = await lookupPublicShare(createPublicShareReader(server), slug);
    if (found.state === "gone") return goneResponse(found.reason);
  } catch {
    // The page repeats the lookup and fails on its own terms; never block a live link on this check.
    log("error", "/r/[slug]", "share_gate_failed");
  }
  return NextResponse.next({ request });
}

export const config = {
  // Skip static files, images and the landing media; run on pages and API routes.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|landing/|samples/|hdri/|.*\.(?:svg|png|jpg|jpeg|gif|webp|avif|mp4|webm|glb|hdr|exr|ico|txt|xml)$).*)"],
};
