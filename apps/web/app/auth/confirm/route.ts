import { NextResponse, type NextRequest } from "next/server";
import { serverConfig } from "@/lib/env";
import { EMAIL_FLOW_COOKIE, continueUrl, parseConfirmLink } from "@/lib/auth/emailLink";
import { sameOrigin } from "@/lib/server/api";
import { createRequestSupabase } from "@/lib/supabase/server";

/**
 * Email links from the Supabase templates: `/auth/confirm?token_hash=…&type=email|recovery|…&next=/path`
 * (token-hash flow, so a link works on another device than the one that asked for it).
 *
 * GET never spends the token: it forwards to the /auth/continue interstitial, whose button POSTs back here. A
 * cross-site link therefore cannot silently sign someone into another account (login CSRF, security review L2),
 * and a mail scanner that prefetches the link does not burn it. See lib/auth/emailLink.ts.
 */
export async function GET(request: NextRequest) {
  const url = request.nextUrl;
  const link = parseConfirmLink((k) => url.searchParams.get(k));
  if (!link || !serverConfig()) return linkInvalid(url.origin);
  return NextResponse.redirect(new URL(continueUrl(link), url.origin), 303);
}

/** The interstitial's form post: same-origin only, then verify the token and continue. */
export async function POST(request: NextRequest) {
  const origin = request.nextUrl.origin;
  const config = serverConfig();
  if (!config || !sameOrigin(request)) return linkInvalid(origin);
  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return linkInvalid(origin);
  }
  const field = (k: string) => {
    const v = form.get(k);
    return typeof v === "string" ? v : null;
  };
  const link = parseConfirmLink(field);
  if (!link) return linkInvalid(origin);

  const supabase = await createRequestSupabase(config);
  const { error } = await supabase.auth.verifyOtp({ type: link.type, token_hash: link.tokenHash });
  if (error) return linkInvalid(origin);

  // Asked for in this browser: straight on. Otherwise show who they are now signed in as, with a way out.
  const startedHere = request.cookies.has(EMAIL_FLOW_COOKIE);
  const target = startedHere
    ? new URL(link.next, origin)
    : new URL(`/auth/continue?${new URLSearchParams({ done: "1", next: link.next }).toString()}`, origin);
  const response = NextResponse.redirect(target, 303);
  if (startedHere) response.cookies.delete(EMAIL_FLOW_COOKIE);
  return response;
}

function linkInvalid(origin: string): Response {
  const failed = new URL("/login", origin);
  failed.searchParams.set("error", "link_invalid");
  return NextResponse.redirect(failed, 303);
}
