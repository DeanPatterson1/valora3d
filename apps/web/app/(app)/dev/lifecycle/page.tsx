"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CancelPlanDialog, type CancelStep } from "@/components/account/CancelPlanDialog";
import { PastDueBanner } from "@/components/account/PastDueBanner";
import { FeedbackDialog } from "@/components/feedback/FeedbackDialog";
import type { SubscriptionSummary } from "@/lib/account/history";
import type { CancelResponse } from "@/lib/billing/cancel";
import { ok } from "@/lib/services/result";

/**
 * /dev/lifecycle?view=… — the lifecycle surfaces with fixtures, for design review in Local mode (the real ones need
 * a live subscription): past-due banner, the three cancel-flow steps, the feedback dialog. 404 in production.
 */
const PERIOD_END = Date.parse("2026-10-28T00:00:00Z");
const PRO: SubscriptionSummary = { plan: "pro", status: "active", next: { kind: "renews", at: PERIOD_END } };
const DONE: CancelResponse = { outcome: "canceled", at: new Date(PERIOD_END).toISOString() };
const slow = <T,>(v: T) => new Promise<T>((r) => setTimeout(() => r(v), 400));

const VIEWS = ["past-due", "cancel-reason", "cancel-offer", "cancel-done", "feedback"] as const;

export default function LifecyclePreviewPage() {
  const view = useSearchParams().get("view") ?? "past-due";
  const nav = (
    <nav aria-label="Previews" className="flex flex-wrap gap-2 px-5 py-4 text-sm sm:px-8">
      {VIEWS.map((v) => (
        <Link key={v} href={`/dev/lifecycle?view=${v}`} className="rounded-full border border-line px-3 py-1 text-fg-muted hover:text-fg">
          {v}
        </Link>
      ))}
    </nav>
  );

  if (view === "past-due") {
    return (
      <>
        <PastDueBanner subscription={{ plan: "creator", status: "past_due", next: { kind: "renews", at: PERIOD_END } }} openPayment={() => slow(ok({ url: "#" }))} />
        {nav}
        <div className="px-5 sm:px-8">
          <h1 className="text-3xl font-semibold tracking-tight">Projects</h1>
          <p className="mt-2 text-sm text-fg-muted">The banner above shows on the dashboard, profile and settings while a payment is overdue.</p>
        </div>
      </>
    );
  }
  if (view.startsWith("cancel-")) {
    const step = view.slice("cancel-".length) as CancelStep;
    return (
      <>
        {nav}
        <CancelPlanDialog
          key={step}
          open
          onClose={() => {}}
          subscription={PRO}
          initialStep={step}
          initialReason={step === "reason" ? null : "too_expensive"}
          initialDone={step === "done" ? DONE : null}
          submit={() => slow(ok(DONE))}
        />
      </>
    );
  }
  return (
    <>
      {nav}
      <FeedbackDialog open onClose={() => {}} initialKind="bug" page="/projects/3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f" local={false} submit={() => slow(ok({ ok: true as const }))} />
    </>
  );
}
