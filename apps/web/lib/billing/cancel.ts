import { z } from "zod";

/**
 * The in-app "Cancel plan" flow (Profile -> Usage & billing): one question, then an offer, then the action. Shared by
 * the dialog (components/account/CancelPlanDialog.tsx) and POST /api/billing/cancel. Mirrors the `reason` check on
 * public.cancellation_feedback (20260930130000_lifecycle.sql; pinned by a test).
 */

export const CANCEL_REASONS = [
  { id: "too_expensive", label: "It's too expensive" },
  { id: "not_using", label: "I'm not using it enough" },
  { id: "missing_feature", label: "It's missing something I need" },
  { id: "quality", label: "The renders aren't good enough" },
  { id: "technical", label: "Something isn't working" },
  { id: "switching", label: "I'm switching to another tool" },
  { id: "temporary", label: "I only needed it for one project" },
  { id: "other", label: "Something else" },
] as const;
export type CancelReason = (typeof CANCEL_REASONS)[number]["id"];

export const CANCEL_ACTIONS = ["cancel", "pause", "downgrade"] as const;
export type CancelAction = (typeof CANCEL_ACTIONS)[number];

export const CancelRequest = z
  .object({
    action: z.enum(CANCEL_ACTIONS),
    reason: z.enum(CANCEL_REASONS.map((r) => r.id) as [CancelReason, ...CancelReason[]]),
    detail: z.string().trim().max(1000).optional(),
  })
  .strict();
export type CancelRequestBody = z.infer<typeof CancelRequest>;

export type CancelResponse = {
  outcome: "canceled" | "paused" | "downgraded";
  /** canceled: when the plan ends; paused: when the pause starts. */
  at: string | null;
  /** paused: when billing resumes. */
  resumesAt?: string | null;
};

/** How long "Pause instead" pauses for. */
export const PAUSE_DAYS = 30;

/** When a pause that starts at `periodEnd` resumes. */
export function pauseResumeAt(periodEnd: Date): Date {
  return new Date(periodEnd.getTime() + PAUSE_DAYS * 86_400_000);
}

export type Offer = "pause" | "downgrade";

/**
 * Which offers to show before cancelling. Pause needs an active subscription (Paddle refuses to pause a past_due one);
 * the cheaper plan is offered only from Pro (Creator is the cheapest paid plan) and only when it is on sale.
 */
export function offersFor(sub: { plan: "creator" | "pro"; status: string }, creatorOnSale: boolean): Offer[] {
  const offers: Offer[] = [];
  if (sub.plan === "pro" && creatorOnSale) offers.push("downgrade");
  if (sub.status === "active") offers.push("pause");
  return offers;
}
