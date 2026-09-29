"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import { Button, Skeleton, useToastStore } from "@/components/ui";
import { services } from "@/lib/services";
import { REFERRAL_TERMS_LINE, localReferralCode, referralLink, toReferralSummary, type ReferralSummary } from "@/lib/referrals";

type State = { status: "loading" } | { status: "error" } | { status: "ready"; summary: ReferralSummary };

async function loadSummary(userId: string): Promise<ReferralSummary | null> {
  // Local mode has no referral backend: a stable demo link, nothing is ever paid for it.
  if (services.backend !== "supabase") return { code: localReferralCode(userId), joined: 0, qualified: 0, creditsEarned: 0 };
  try {
    const res = await fetch("/api/referrals", { credentials: "same-origin", cache: "no-store" });
    if (!res.ok) return null;
    return toReferralSummary(await res.json());
  } catch {
    return null;
  }
}

function Count({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xl font-semibold tracking-tight tabular text-fg">{value.toLocaleString("en-US")}</span>
      <span className="text-xs text-fg-muted">{label}</span>
    </div>
  );
}

/** Profile → Invite friends: the user's referral link, a copy button, counts and the terms in one line. */
export function InviteCard({ userId }: { userId: string }) {
  const push = useToastStore((s) => s.push);
  const [state, setState] = useState<State>({ status: "loading" });
  // Read once; the link input only renders after the summary loads (client side), so SSR never needs it.
  const [origin] = useState(() => (typeof window === "undefined" ? "" : window.location.origin));
  const linkId = useId();

  useEffect(() => {
    let live = true;
    void loadSummary(userId).then((summary) => {
      if (live) setState(summary ? { status: "ready", summary } : { status: "error" });
    });
    return () => {
      live = false;
    };
  }, [userId]);

  const url = state.status === "ready" && origin ? referralLink(origin, state.summary.code) : "";
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      push({ kind: "success", message: "Invite link copied" });
    } catch {
      push({ kind: "danger", message: "Could not copy. Select the link and copy it." });
    }
  };

  return (
    <section aria-labelledby="invite" className="mb-10 flex flex-col gap-4 rounded-lg border border-line bg-bg-1 p-5">
      <div className="flex flex-col gap-1">
        <h2 id="invite" className="text-lg font-semibold tracking-tight text-fg">
          Invite friends
        </h2>
        <p className="text-sm text-fg-muted">{REFERRAL_TERMS_LINE}</p>
      </div>
      {state.status === "loading" ? (
        <Skeleton className="h-9 w-full" />
      ) : state.status === "error" ? (
        <p role="alert" className="text-sm text-danger">
          Could not load your invite link. Try again later.
        </p>
      ) : (
        <>
          <div className="flex flex-col gap-2 sm:flex-row">
            <label htmlFor={linkId} className="sr-only">
              Your invite link
            </label>
            <input
              id={linkId}
              readOnly
              value={url}
              onFocus={(e) => e.currentTarget.select()}
              className="h-9 w-full min-w-0 rounded-sm border border-line bg-bg-2 px-3 text-sm text-fg outline-none focus-visible:focus-ring sm:flex-1"
            />
            <Button variant="secondary" onClick={() => void copy()} disabled={!url}>
              Copy link
            </Button>
          </div>
          <div role="group" aria-label="Invites" className="grid grid-cols-3 gap-3">
            <Count value={state.summary.joined} label="Joined" />
            <Count value={state.summary.qualified} label="Made a first payment" />
            <Count value={state.summary.creditsEarned} label="Credits earned" />
          </div>
          <p className="text-xs text-fg-muted">
            <Link href="/terms#referrals" className="underline-offset-4 hover:underline focus-visible:focus-ring">
              Referral terms
            </Link>
          </p>
        </>
      )}
    </section>
  );
}
