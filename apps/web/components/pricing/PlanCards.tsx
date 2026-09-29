"use client";

import Link from "next/link";
import { PLANS, type PlanDef, type PlanId } from "@/lib/pricing";
import { BACKEND } from "@/lib/services/backend";
import { START_PATH, signupHref } from "@/lib/nav/next";
import { Button, cx } from "@/components/ui";
import { useCheckout } from "./useCheckout";
import { useGrant } from "./useGrant";
import { usePricingAccount } from "./usePricingAccount";

/** What the button on a plan card does for a signed-in user. */
export type PlanAction = "choose" | "current" | "manage";

/**
 * Local backend: every plan is a free "grant" (the prototype). Real backend: your plan is marked
 * current, a paid plan opens checkout (or changes the subscription), and Free while paying points
 * to Manage billing, where the subscription is canceled.
 */
export function planAction(backend: "local" | "supabase", plan: PlanId, userPlan: PlanId): PlanAction {
  if (backend === "local") return "choose";
  if (plan === userPlan) return "current";
  return plan === "free" ? "manage" : "choose";
}

/** Said at the button, not only in the terms: what a subscription does after today. */
export const RENEWAL_NOTE = "Renews monthly until canceled. Cancel anytime.";

/** Signed out: signup, then straight to this plan's checkout (Free just starts a project). */
export function planSignupHref(plan: PlanDef): string {
  const id = plan.name.toLowerCase() as PlanId;
  return id === "free" ? signupHref(START_PATH) : signupHref(undefined, `plan:${id}`);
}

const ACTION_LABEL: Record<PlanAction, string> = { choose: "Choose plan", current: "Current plan", manage: "Manage billing" };

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 16 16"
      className={cx("size-4 shrink-0", className)}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 8.5l3 3 7-7" />
    </svg>
  );
}

function PlanCard({ plan, pending, onChoose, signedIn, action }: { plan: PlanDef; pending: boolean; onChoose: () => void; signedIn: boolean; action: PlanAction }) {
  const hi = plan.highlighted;
  return (
    <li
      data-plan={plan.name}
      data-highlighted={hi || undefined}
      className={cx(
        "flex flex-col gap-6 rounded-lg border p-6",
        hi ? "border-primary bg-primary text-primary-fg" : "border-line bg-bg-2 text-fg",
      )}
    >
      <div className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold tracking-tight">{plan.name}</h2>
        <p className="flex items-baseline gap-1.5">
          <span className="text-3xl font-semibold tracking-tight tabular">${plan.priceUsd}</span>{" "}
          <span className={cx("text-sm", hi ? "text-primary-fg/70" : "text-fg-muted")}>
            {plan.period === "month" ? "USD / month" : "Free · no card needed"}
          </span>
        </p>
      </div>

      {signedIn ? <Button
        variant={hi ? "primary" : "secondary"}
        size="lg"
        loading={pending}
        disabled={action === "current"}
        onClick={onChoose}
        aria-label={`${ACTION_LABEL[action]}: ${plan.name}`}
        className={cx("w-full", hi && "bg-bg-0 text-fg hover:bg-bg-3 disabled:hover:bg-bg-0")}
      >
        {ACTION_LABEL[action]}
      </Button> : (
        <Link href={planSignupHref(plan)} aria-label={`Get started: ${plan.name}`} className={cx("inline-flex h-11 w-full items-center justify-center rounded-full border border-line px-5 text-sm font-medium focus-visible:focus-ring", hi ? "bg-bg-0 text-fg" : "bg-bg-3 text-fg")}>
          Get started
        </Link>
      )}

      {plan.period === "month" && (
        <p className={cx("-mt-3 text-xs", hi ? "text-primary-fg/70" : "text-fg-muted")}>{RENEWAL_NOTE}</p>
      )}

      <ul className="flex flex-col gap-2.5 text-sm">
        {plan.features.map((f) => (
          <li key={f} className="flex items-start gap-2.5">
            <CheckIcon className={cx("mt-0.5", hi ? "text-primary-fg/70" : "text-fg-muted")} />
            <span>{f}</span>
          </li>
        ))}
      </ul>
    </li>
  );
}

export function PlanCards() {
  const { grant, pending: grantPending } = useGrant();
  const checkout = useCheckout();
  const user = usePricingAccount();
  const backend = BACKEND;
  return (
    <ul className="grid grid-cols-1 gap-4 min-[900px]:grid-cols-3" aria-label="Plans">
      {PLANS.map((plan) => {
        const id = plan.name.toLowerCase() as PlanId;
        const action = planAction(backend, id, user?.plan ?? "free");
        const key = `plan:${plan.name}`;
        const onChoose = () => {
          if (backend === "local") return void grant(key, plan.credits, "plan_grant");
          if (action === "manage") return void checkout.manage();
          if (action === "choose" && id !== "free") void checkout.buy(key, `plan:${id}`);
        };
        return (
          <PlanCard
            key={plan.name}
            plan={plan}
            signedIn={Boolean(user)}
            action={action}
            pending={grantPending === key || checkout.pending === key || (action === "manage" && checkout.pending === "portal")}
            onChoose={onChoose}
          />
        );
      })}
    </ul>
  );
}
