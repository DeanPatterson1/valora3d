"use client";

import { useState } from "react";
import { Button, Dialog } from "@/components/ui";
import { cancelPlan } from "@/lib/account/lifecycleClient";
import type { SubscriptionSummary } from "@/lib/account/history";
import { CANCEL_REASONS, PAUSE_DAYS, pauseResumeAt, type CancelAction, type CancelReason, type CancelRequestBody, type CancelResponse } from "@/lib/billing/cancel";
import type { Result } from "@/lib/services";
import { ChoiceList, TextArea } from "./ChoiceList";
import { PLAN_LABEL } from "./planLabel";

const DATE: Intl.DateTimeFormatOptions = { month: "long", day: "numeric", year: "numeric" };
const fmt = (ms: number | string | null | undefined) => (ms ? new Date(ms).toLocaleDateString("en-US", DATE) : null);

export type CancelStep = "reason" | "offer" | "done";

/**
 * Profile -> Usage & billing -> "Cancel plan": one question (why), then the offers that fit (a cheaper plan from Pro,
 * a one-month pause for an active plan), then cancel at the end of the paid period. Nothing changes until a button in
 * the second step is pressed. `submit` is injectable for previews and tests.
 */
export function CancelPlanDialog({
  open,
  onClose,
  onChanged,
  subscription,
  submit = cancelPlan,
  initialStep = "reason",
  initialReason = null,
  initialDone = null,
}: {
  open: boolean;
  onClose: () => void;
  /** Called after Paddle accepted a change, so the page can reload the plan. */
  onChanged?: (r: CancelResponse) => void;
  subscription: SubscriptionSummary;
  submit?: (body: CancelRequestBody) => Promise<Result<CancelResponse>>;
  initialStep?: CancelStep;
  initialReason?: CancelReason | null;
  initialDone?: CancelResponse | null;
}) {
  const [step, setStep] = useState<CancelStep>(initialStep);
  const [reason, setReason] = useState<CancelReason | null>(initialReason);
  const [detail, setDetail] = useState("");
  const [pending, setPending] = useState<CancelAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<CancelResponse | null>(initialDone);

  const plan = PLAN_LABEL[subscription.plan];
  const periodEnd = subscription.next?.at ?? null;
  const endDate = fmt(periodEnd) ?? "the end of your billing period";
  const offerDowngrade = subscription.plan === "pro";
  const offerPause = subscription.status === "active" && periodEnd !== null;

  const close = () => {
    if (pending) return;
    onClose();
    // Start fresh next time, unless a change went through (the page re-reads the plan then).
    setStep(initialStep);
    setError(null);
  };

  const act = async (action: CancelAction) => {
    if (!reason) return;
    setPending(action);
    setError(null);
    const r = await submit({ action, reason, ...(detail.trim() ? { detail: detail.trim() } : {}) });
    setPending(null);
    if (!r.ok) {
      setError(r.error.message);
      return;
    }
    setDone(r.value);
    setStep("done");
    onChanged?.(r.value);
  };

  let title = `Cancel ${plan}?`;
  let description: string | undefined = "One quick question first. It helps us fix what isn't working.";
  let body: React.ReactNode = null;

  if (step === "reason") {
    body = (
      <>
        <ChoiceList legend="What's the main reason?" options={CANCEL_REASONS} value={reason} onChange={setReason} />
        <TextArea label="Anything else we should know? (optional)" value={detail} onChange={setDetail} maxLength={1000} rows={2} />
        <div className="flex flex-wrap justify-end gap-2 pt-1">
          <Button onClick={close}>Keep my plan</Button>
          <Button variant="primary" disabled={!reason} onClick={() => setStep("offer")}>
            Continue
          </Button>
        </div>
      </>
    );
  } else if (step === "offer") {
    title = offerDowngrade || offerPause ? "Before you go" : `Cancel ${plan}?`;
    description = undefined;
    const resume = periodEnd ? fmt(pauseResumeAt(new Date(periodEnd)).getTime()) : null;
    body = (
      <>
        {(offerDowngrade || offerPause) && (
          <ul className="flex flex-col gap-2">
            {offerDowngrade && (
              <li className="flex flex-col gap-2 rounded-md border border-line p-3">
                <span className="text-sm font-medium text-fg">Switch to Creator</span>
                <span className="text-sm text-fg-muted">
                  Keep 1080p finals and no watermark for less. Switches today; your next renewal is billed at the Creator price.
                </span>
                <Button size="sm" className="self-start" loading={pending === "downgrade"} disabled={Boolean(pending)} onClick={() => void act("downgrade")}>
                  Switch to Creator
                </Button>
              </li>
            )}
            {offerPause && (
              <li className="flex flex-col gap-2 rounded-md border border-line p-3">
                <span className="text-sm font-medium text-fg">Pause for {PAUSE_DAYS} days instead</span>
                <span className="text-sm text-fg-muted">
                  Keep {plan} until {endDate}, then no charges until {resume}. Your credits and projects stay.
                </span>
                <Button size="sm" className="self-start" loading={pending === "pause"} disabled={Boolean(pending)} onClick={() => void act("pause")}>
                  Pause instead
                </Button>
              </li>
            )}
          </ul>
        )}
        <p className="text-sm text-fg-muted">
          If you cancel, you keep {plan} until {endDate}. After that your account moves to Free: your credits stay, and nothing more is
          charged.
        </p>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <div className="flex flex-wrap justify-end gap-2 pt-1">
          <Button onClick={close} disabled={Boolean(pending)}>
            Keep my plan
          </Button>
          <Button variant="danger" loading={pending === "cancel"} disabled={Boolean(pending)} onClick={() => void act("cancel")}>
            Cancel at period end
          </Button>
        </div>
      </>
    );
  } else if (done) {
    description = undefined;
    const at = fmt(done.at);
    if (done.outcome === "canceled") {
      title = "Your plan will end";
      body = <p className="text-sm text-fg-muted">You keep {plan} until {at ?? endDate}. We&apos;ve emailed you a confirmation. Changed your mind? Reply to it before then and we&apos;ll keep your plan running.</p>;
    } else if (done.outcome === "paused") {
      title = "Pause scheduled";
      body = (
        <p className="text-sm text-fg-muted">
          You keep {plan} until {at ?? endDate}. Billing pauses then and resumes on {fmt(done.resumesAt) ?? "the date in your confirmation email"}.
        </p>
      );
    } else {
      title = "You're on Creator";
      body = <p className="text-sm text-fg-muted">Your plan switches to Creator. Your credits stay, and your next renewal is billed at the Creator price.</p>;
    }
    body = (
      <>
        {body}
        <div className="flex justify-end pt-1">
          <Button variant="primary" onClick={close}>
            Done
          </Button>
        </div>
      </>
    );
  }

  return (
    <Dialog open={open} onClose={close} title={title} description={description}>
      <div className="flex flex-col gap-4">{body}</div>
    </Dialog>
  );
}
