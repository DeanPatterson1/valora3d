import { NextResponse, type NextRequest } from "next/server";
import type { EmailOtpType } from "@supabase/supabase-js";
import { serverConfig } from "@/lib/env";
import { createRequestSupabase } from "@/lib/supabase/server";
import { safeNextPath } from "@/lib/supabase/proxy";

const TYPES: EmailOtpType[] = ["signup", "invite", "magiclink", "recovery", "email_change", "email"];

/**
 * GET /auth/confirm?token_hash=…&type=signup|recovery&next=/path — for Supabase email templates
 * that link with a token hash (works across devices, unlike the PKCE code). Recovery links land on
 * /reset-password.
 */
export async function GET(request: NextRequest) {
  const url = request.nextUrl;
  const tokenHash = url.searchParams.get("token_hash");
  const type = url.searchParams.get("type") as EmailOtpType | null;
  const config = serverConfig();

  if (tokenHash && type && TYPES.includes(type) && config) {
    const supabase = await createRequestSupabase(config);
    const { error } = await supabase.auth.verifyOtp({ type, token_hash: tokenHash });
    if (!error) {
      const next = type === "recovery" ? "/reset-password" : safeNextPath(url.searchParams.get("next"));
      return NextResponse.redirect(new URL(next, url.origin));
    }
  }
  const failed = new URL("/login", url.origin);
  failed.searchParams.set("error", "link_invalid");
  return NextResponse.redirect(failed);
}
