import { NextResponse, type NextRequest } from "next/server";
import { publicSupabaseConfig } from "@/lib/env";
import { ADMIN_HEADERS, isAdminPath, updateSession } from "@/lib/supabase/proxy";

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
  return updateSession(request, config);
}

export const config = {
  // Skip static files, images and the landing media; run on pages and API routes.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|landing/|samples/|hdri/|.*\\.(?:svg|png|jpg|jpeg|gif|webp|avif|mp4|webm|glb|hdr|exr|ico|txt|xml)$).*)"],
};
