import type { Metadata } from "next";
import { cookies } from "next/headers";
import { BRAND } from "@/lib/brand";
import { serverConfig } from "@/lib/env";
import { EMAIL_FLOW_COOKIE, parseConfirmLink } from "@/lib/auth/emailLink";
import { safeNextPath } from "@/lib/supabase/proxy";
import { createRequestSupabase } from "@/lib/supabase/server";
import { ConfirmLinkScreen, LinkInvalidScreen, SignedInAsScreen } from "@/components/auth/ConfirmLinkScreens";

export const metadata: Metadata = {
  title: `Continue · ${BRAND.name}`,
  robots: { index: false },
  // The token is in this page's URL: never leak it through a Referer.
  referrer: "no-referrer",
};

type Search = Record<string, string | string[] | undefined>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : null);

/**
 * /auth/continue: the click-to-continue step between an email link and the sign-in it performs (login-CSRF
 * defence, lib/auth/emailLink.ts). `?token_hash&type&next` shows the confirm form; `?done=1&next` (after a link
 * opened in a browser that did not ask for it) shows which account is now signed in, with a way out.
 */
export default async function ContinuePage({ searchParams }: { searchParams: Promise<Search> }) {
  const params = await searchParams;
  const config = serverConfig();

  if (one(params.done) === "1") {
    const next = safeNextPath(one(params.next));
    let email: string | null = null;
    if (config) {
      const { data } = await (await createRequestSupabase(config)).auth.getUser();
      email = data.user?.email ?? null;
    }
    if (!email) return <LinkInvalidScreen />;
    return <SignedInAsScreen email={email} next={next} />;
  }

  const link = parseConfirmLink((k) => one(params[k]));
  if (!link) return <LinkInvalidScreen />;
  const startedHere = (await cookies()).has(EMAIL_FLOW_COOKIE);
  return <ConfirmLinkScreen link={link} startedHere={startedHere} />;
}
