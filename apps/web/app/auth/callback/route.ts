import { NextResponse, type NextRequest } from "next/server";
import { serverConfig } from "@/lib/env";
import { createRequestSupabase } from "@/lib/supabase/server";
import { safeNextPath } from "@/lib/supabase/proxy";

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
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) return NextResponse.redirect(new URL(next, url.origin));
  }
  const failed = new URL("/login", url.origin);
  failed.searchParams.set("error", "link_invalid");
  return NextResponse.redirect(failed);
}
