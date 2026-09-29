import { NextResponse, type NextRequest } from "next/server";
import { publicSupabaseConfig, serverConfig } from "@/lib/env";
import { log } from "@/lib/server/log";
import { createPublicShareReader, lookupPublicShare } from "@/lib/server/shareLookup";
import { goneResponse } from "@/lib/share/public";
import { ADMIN_HEADERS, isAdminPath, updateSession } from "@/lib/supabase/proxy";

/** A public share page, `/r/<slug>` (not its /video or /poster routes, which answer 410 themselves). */
const SHARE_PAGE = /^\/r\/[A-Za-z0-9_-]{22,64}$/;

/**
 * Server-side session refresh + route protection (Next 16 `proxy`, formerly middleware).
 * Without Supabase configured the app runs on the in-browser fakes, whose client-side AuthGate
 * is the only gate, so the proxy passes everything through.
 */
export async function proxy(request: NextRequest) {
  // The dev layout's notFound() streams after a 200 has gone out; rewrite to a missing route for a real 404.
  if (process.env.NODE_ENV === "production" && /^\/dev(\/|$)/.test(request.nextUrl.pathname)) {
    return NextResponse.rewrite(new URL("/__not-found", request.url));
  }
  const config = publicSupabaseConfig();
  if (!config) {
    // Local mode: /admin renders its "requires the live backend" notice and the admin API answers 403.
    const response = NextResponse.next();
    if (isAdminPath(request.nextUrl.pathname)) Object.entries(ADMIN_HEADERS).forEach(([k, v]) => response.headers.set(k, v));
    return response;
  }
  if (SHARE_PAGE.test(request.nextUrl.pathname)) return shareGate(request);
  return updateSession(request, config);
}

/**
 * A page cannot send 410, so a revoked or expired share link is answered here with the friendly 410 page.
 * Live and unknown slugs go on to the page (which renders the video, or a 404). The share page is public and
 * needs no session, so the session refresh is skipped for it.
 */
async function shareGate(request: NextRequest): Promise<Response> {
  const server = serverConfig();
  if (!server || (request.method !== "GET" && request.method !== "HEAD")) return NextResponse.next();
  try {
    const slug = request.nextUrl.pathname.slice("/r/".length);
    const found = await lookupPublicShare(createPublicShareReader(server), slug);
    if (found.state === "gone") return goneResponse(found.reason);
  } catch {
    // The page repeats the lookup and fails on its own terms; never block a live link on this check.
    log("error", "/r/[slug]", "share_gate_failed");
  }
  return NextResponse.next();
}

export const config = {
  // Skip static files, images and the landing media; run on pages and API routes.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|landing/|samples/|hdri/|.*\.(?:svg|png|jpg|jpeg|gif|webp|avif|mp4|webm|glb|hdr|exr|ico|txt|xml)$).*)"],
};
