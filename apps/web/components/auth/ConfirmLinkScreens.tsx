"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui";
import type { ConfirmLink, ConfirmType } from "@/lib/auth/emailLink";
import { services } from "@/lib/services";
import { AuthCard } from "./AuthCard";

const WIDE = "h-12 w-full rounded-full text-base";

/** Copy per link type for the interstitial. */
const CONFIRM_COPY: Record<ConfirmType, { title: string; action: string }> = {
  email: { title: "Confirm your email", action: "Continue" },
  signup: { title: "Confirm your email", action: "Continue" },
  recovery: { title: "Reset your password", action: "Continue" },
  email_change: { title: "Confirm your new email", action: "Confirm change" },
  invite: { title: "Accept your invite", action: "Continue" },
};

/**
 * Step between an email link and the sign-in it performs. The button posts the token to /auth/confirm (same-origin
 * only), so a link someone else sent cannot sign this browser into their account without a visible click, and
 * without a warning when this browser never asked for an email.
 */
export function ConfirmLinkScreen({ link, startedHere }: { link: ConfirmLink; startedHere: boolean }) {
  const [busy, setBusy] = useState(false);
  const copy = CONFIRM_COPY[link.type];
  return (
    <AuthCard title={copy.title} subtitle="One more step to finish with the link from your email.">
      {!startedHere && (
        <p role="note" className="border-l-2 border-fg-muted/40 pl-3 text-sm leading-relaxed text-fg-muted">
          This link was opened in a different browser from the one that asked for it. That&apos;s fine if you
          requested it yourself. If someone sent you this link, close this page: it signs in to the account it was
          sent to, which may not be yours.
        </p>
      )}
      <form method="post" action="/auth/confirm" onSubmit={() => setBusy(true)} className="flex flex-col gap-3">
        <input type="hidden" name="token_hash" value={link.tokenHash} />
        <input type="hidden" name="type" value={link.type} />
        <input type="hidden" name="next" value={link.next} />
        <Button type="submit" variant="primary" size="lg" loading={busy} className={WIDE}>
          {copy.action}
        </Button>
      </form>
      <p className="text-center text-sm text-fg-muted">
        Didn&apos;t ask for this?{" "}
        <Link href="/" className="rounded-sm text-fg underline underline-offset-4 focus-visible:focus-ring">
          Leave
        </Link>
      </p>
    </AuthCard>
  );
}

/** After a link opened in a browser that did not ask for it: say which account is now signed in. */
export function SignedInAsScreen({ email, next }: { email: string; next: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const signOut = async () => {
    setBusy(true);
    await services.auth.signOut();
    router.replace("/login");
  };
  return (
    <AuthCard title="Is this your account?" subtitle="The link signed you in as:">
      <p className="break-all rounded-md border border-line bg-bg-0 px-4 py-3 text-base font-medium text-fg">{email}</p>
      <div className="flex flex-col gap-2">
        <Button variant="primary" size="lg" className={WIDE} disabled={busy} onClick={() => router.replace(next)}>
          Yes, continue
        </Button>
        <Button variant="secondary" size="lg" className={WIDE} loading={busy} onClick={signOut}>
          Not me, sign out
        </Button>
      </div>
    </AuthCard>
  );
}

export function LinkInvalidScreen() {
  return (
    <AuthCard title="Link expired" footer={{ text: "Need a new one?", linkLabel: "Log in", href: "/login" }}>
      <p className="text-sm text-fg-muted">That link is invalid or has already been used. Sign in, or request a new link.</p>
    </AuthCard>
  );
}
