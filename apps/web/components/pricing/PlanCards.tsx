"use client";

import Link from "next/link";
import { PLANS, type PlanDef } from "@/lib/pricing";
import { Button, cx } from "@/components/ui";
import { useGrant } from "./useGrant";
import { usePricingAccount } from "./usePricingAccount";

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

function PlanCard({ plan, pending, onChoose, signedIn }: { plan: PlanDef; pending: boolean; onChoose: () => void; signedIn: boolean }) {
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
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xl font-semibold tracking-tight">{plan.name}</h2>
          {hi && (
            <span className="inline-flex h-6 items-center rounded-full bg-bg-0 px-2.5 text-xs font-medium text-fg">
              Most popular
            </span>
          )}
        </div>
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
        onClick={onChoose}
        aria-label={`Choose plan: ${plan.name}`}
        className={cx("w-full", hi && "bg-bg-0 text-fg hover:bg-bg-3 disabled:hover:bg-bg-0")}
      >
        Choose plan
      </Button> : (
        <Link href="/signup" aria-label={`Get started: ${plan.name}`} className={cx("inline-flex h-11 w-full items-center justify-center rounded-full border border-line px-5 text-sm font-medium focus-visible:focus-ring", hi ? "bg-bg-0 text-fg" : "bg-bg-3 text-fg")}>
          Get started
        </Link>
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
  const { grant, pending } = useGrant();
  const user = usePricingAccount();
  return (
    <ul className="grid grid-cols-1 gap-4 min-[900px]:grid-cols-3" aria-label="Plans">
      {PLANS.map((plan) => (
        <PlanCard
          key={plan.name}
          plan={plan}
          signedIn={Boolean(user)}
          pending={pending === `plan:${plan.name}`}
          onChoose={() => void grant(`plan:${plan.name}`, plan.credits, "plan_grant")}
        />
      ))}
    </ul>
  );
}
