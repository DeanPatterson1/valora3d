import { billingConfig } from "@/lib/env";
import { CancelRequest, pauseResumeAt, offersFor, type CancelResponse } from "@/lib/billing/cancel";
import { createPaddleApi } from "@/lib/billing/paddle-api";
import { cancelScheduledEmail, planPausedEmail } from "@/lib/email/lifecycle";
import { readBody } from "@/lib/server/api";
import { lifecycleSender, sendClaimed } from "@/lib/server/lifecycle";
import { apiError, createServiceSupabase, requireUser } from "@/lib/supabase/server";

type Sub = { id: string; plan: "creator" | "pro"; status: string; current_period_end: string | null; scheduled_change: { action?: string } | null };

const json = (body: CancelResponse) => Response.json(body, { headers: { "Cache-Control": "no-store" } });

/**
 * POST /api/billing/cancel {action, reason, detail?} — the in-app cancel flow (Profile -> Usage & billing).
 *   cancel     cancel at the end of the paid period (Paddle `effective_from: next_billing_period`); the plan stays until then
 *   pause      pause from the end of the period for 30 days (Paddle pause + `resume_at`); active subscriptions only
 *   downgrade  Pro -> Creator now, not billed (same rule as a downgrade at checkout; the next renewal is at Creator)
 * The reason is stored in cancellation_feedback (admin -> Feedback) only once Paddle accepted the change, and a
 * confirmation mail goes out (transactional). Credits and plan state still change only through the Paddle webhook;
 * `scheduled_change` is written here too so the page shows the end date before the webhook arrives.
 */
export async function POST(request: Request) {
  const ctx = await requireUser();
  if (ctx instanceof Response) return ctx;
  const body = await readBody(request, CancelRequest);
  if (body instanceof Response) return body;
  const billing = billingConfig();
  if (!billing?.apiKey) return apiError(503, "checkout_unavailable", "Billing isn't open yet.");

  const admin = createServiceSupabase(ctx.config);
  const [subs, customer, profile] = await Promise.all([
    admin
      .from("billing_subscriptions")
      .select("id, plan, status, current_period_end, scheduled_change")
      .eq("user_id", ctx.user.id)
      .in("status", ["active", "trialing", "past_due"])
      .order("current_period_end", { ascending: false })
      .limit(1),
    admin.from("billing_customers").select("paddle_customer_id").eq("user_id", ctx.user.id).maybeSingle(),
    admin.from("profiles").select("email, name").eq("id", ctx.user.id).maybeSingle<{ email: string; name: string }>(),
  ]);
  if (subs.error || customer.error) return apiError(500, "server", "Something went wrong on our side.");
  const sub = ((subs.data ?? []) as Sub[])[0];
  if (!sub) return apiError(404, "no_subscription", "There's no active plan to cancel.");
  if (sub.scheduled_change?.action === "cancel") return apiError(409, "already_scheduled", "Your plan is already set to end.");
  if (body.action !== "cancel" && !offersFor(sub, Boolean(billing.prices["plan:creator"])).includes(body.action)) {
    return apiError(409, "not_available", "That option isn't available for your plan.");
  }

  const paddle = createPaddleApi(billing.apiKey, billing.environment);
  const periodEnd = sub.current_period_end ? new Date(sub.current_period_end) : null;
  let response: CancelResponse;
  if (body.action === "cancel") {
    const r = await paddle.cancelAtPeriodEnd(sub.id);
    if ("error" in r) return apiError(502, "server", "Couldn't reach billing. Nothing was changed; try again in a minute.");
    response = { outcome: "canceled", at: sub.current_period_end };
  } else if (body.action === "pause") {
    if (!periodEnd) return apiError(409, "not_available", "That option isn't available for your plan.");
    const resume = pauseResumeAt(periodEnd);
    const r = await paddle.pauseAtPeriodEnd(sub.id, resume.toISOString());
    if ("error" in r) return apiError(502, "server", "Couldn't reach billing. Nothing was changed; try again in a minute.");
    response = { outcome: "paused", at: sub.current_period_end, resumesAt: resume.toISOString() };
  } else {
    const r = await paddle.changeSubscriptionPrice(sub.id, billing.prices["plan:creator"]!, "downgrade");
    if ("error" in r) return apiError(502, "server", "Couldn't reach billing. Nothing was changed; try again in a minute.");
    response = { outcome: "downgraded", at: null };
  }

  // Best-effort from here on: Paddle has accepted the change, which is what matters.
  if (response.outcome !== "downgraded" && sub.current_period_end) {
    await admin
      .from("billing_subscriptions")
      .update({ scheduled_change: { action: response.outcome === "canceled" ? "cancel" : "pause", effective_at: sub.current_period_end } })
      .eq("id", sub.id)
      .then(() => undefined, () => undefined);
  }
  await admin
    .from("cancellation_feedback")
    .insert({ user_id: ctx.user.id, subscription_id: sub.id, plan: sub.plan, reason: body.reason, detail: body.detail || null, outcome: response.outcome })
    .then(() => undefined, () => undefined);

  const send = lifecycleSender(ctx.config);
  if (send && profile.data?.email && response.outcome !== "downgraded") {
    const input = { name: profile.data.name, plan: sub.plan, at: periodEnd, resumeAt: response.resumesAt ? new Date(response.resumesAt) : null };
    const kind = response.outcome === "canceled" ? "cancel_scheduled" : "plan_paused";
    try {
      await sendClaimed(
        { db: admin, send, unsubscribeSecret: ctx.config.unsubscribeSecret },
        { user_id: ctx.user.id, email: profile.data.email, name: profile.data.name },
        kind,
        `${sub.id}:${sub.current_period_end ?? "none"}`,
        () => (kind === "cancel_scheduled" ? cancelScheduledEmail(input) : planPausedEmail(input)),
      );
    } catch {
      // The change itself went through; the page shows it.
    }
  }
  return json(response);
}
