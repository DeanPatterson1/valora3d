"use client";

import Link from "next/link";
import { CREDIT_COSTS, CREDIT_PACKS, creditValue, type CheckoutItem } from "@/lib/pricing";
import { BACKEND } from "@/lib/services/backend";
import { signupHref } from "@/lib/nav/next";
import { Button } from "@/components/ui";
import { useCheckout } from "./useCheckout";
import { useGrant } from "./useGrant";
import { usePricingAccount } from "./usePricingAccount";

const fmt = (n: number) => n.toLocaleString("en-US");

/** Cents per credit, one decimal: 500 for $20 → "4.0¢ / credit". */
export function perCredit(priceUsd: number, credits: number): string {
  return `${((priceUsd / credits) * 100).toFixed(1)}¢ / credit`;
}

/** Said at the button: a pack is a single charge, never a subscription. */
export const PACK_NOTE = "One-time purchase. Pack credits never expire.";

/** What a pack buys: Previews on any plan, Finals only on the plans that render them. */
export function packValue(credits: number): string {
  const finals = Math.floor(credits / CREDIT_COSTS.final_render);
  const previews = creditValue(credits, "free");
  return finals > 0 ? `${previews}, or ${finals.toLocaleString("en-US")} ${finals === 1 ? "Final" : "Finals"} on Creator and Pro` : previews;
}

export function CreditPacks() {
  const { grant, pending: grantPending } = useGrant();
  const checkout = useCheckout();
  const user = usePricingAccount();
  const pending = grantPending ?? checkout.pending;
  return (
    <ul className="grid grid-cols-1 gap-4 sm:grid-cols-3" aria-label="Credit packs">
      {CREDIT_PACKS.map((pack) => {
        const key = `pack:${pack.credits}`;
        return (
          <li
            key={pack.credits}
            data-pack={pack.credits}
            className="flex items-center justify-between gap-4 rounded-lg border border-line bg-bg-2 p-5 sm:flex-col sm:items-start"
          >
            <div className="flex flex-col gap-0.5">
              <span className="text-lg font-semibold tracking-tight text-fg tabular">{fmt(pack.credits)} credits</span>
              <span className="text-sm text-fg tabular">${pack.priceUsd}</span>
              <span className="text-xs text-fg-muted tabular">{perCredit(pack.priceUsd, pack.credits)}</span>
              <span className="text-xs text-fg-muted">= {packValue(pack.credits)}</span>
              <span className="mt-1 text-xs text-fg-muted">{PACK_NOTE}</span>
            </div>
            {user ? <Button
              variant="secondary"
              loading={pending === key}
              onClick={() =>
                BACKEND === "local"
                  ? void grant(key, pack.credits, "pack_purchase")
                  : void checkout.buy(key, key as CheckoutItem)}
              aria-label={`Buy ${fmt(pack.credits)} credits`}
              className="sm:w-full"
            >
              Buy
            </Button> : (
              <Link href={signupHref(undefined, key as CheckoutItem)} aria-label={`Get started: ${fmt(pack.credits)} credits`} className="inline-flex h-10 items-center justify-center rounded-full border border-line bg-bg-3 px-4 text-sm text-fg focus-visible:focus-ring sm:w-full">Get started</Link>
            )}
          </li>
        );
      })}
    </ul>
  );
}
