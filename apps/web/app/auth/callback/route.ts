import { NextResponse, type NextRequest } from "next/server";
import { ATTRIBUTION_COOKIE } from "@/lib/analytics/attribution";
import { attributionFromCookie, saveSignupSource } from "@/lib/analytics/server";
import { serverConfig } from "@/lib/env";
import { createRequestSupabase, createServiceSupabase } from "@/lib/supabase/server";
import { safeNextPath } from "@/lib/nav/safePath";

/**
 * GET /auth/callback?code=…&next=/path — the PKCE landing for Google sign-in, email verification
 * links and password-reset links. Exchanges the code for a session cookie, then continues to a
 * same-origin `next`.
 */
export async function GET(request: NextRequest) {
  const url = request.nextUrl;
  const next = safeNextPath(url.searchParams.get("next"));
  const code = url.searchParams.get("code");
  const config = serverConfig();

  if (code && config) {
    const supabase = await createRequestSupabase(config);
    const { data, error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      // A new account (e.g. Google) gets its first-touch source; the SQL ignores accounts older than a day.
      const attribution = attributionFromCookie(request.cookies.get(ATTRIBUTION_COOKIE)?.value);
      if (data?.user && attribution) await saveSignupSource(createServiceSupabase(config), data.user.id, attribution);
      return NextResponse.redirect(new URL(next, url.origin));
    }
  }
  const failed = new URL("/login", url.origin);
  failed.searchParams.set("error", "link_invalid");
  return NextResponse.redirect(failed);
}
