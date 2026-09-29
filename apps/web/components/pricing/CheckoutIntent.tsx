"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";
import { isCheckoutItem } from "@/lib/nav/next";
import { PLANS, packForItem, type CheckoutItem, type PlanId } from "@/lib/pricing";
import { BACKEND, type Backend } from "@/lib/services/backend";
import { planAction } from "./PlanCards";
import { useCheckout } from "./useCheckout";
import { useGrant } from "./useGrant";
import { usePricingAccount } from "./usePricingAccount";

/** What `/pricing?checkout=<item>` does for a signed-in user: open that item's checkout, or nothing. */
export function intentAction(backend: Backend, item: CheckoutItem, userPlan: PlanId): "checkout" | "grant" | "none" {
  if (backend === "local") return "grant";
  if (item.startsWith("plan:")) return planAction(backend, item.slice(5) as PlanId, userPlan) === "choose" ? "checkout" : "none";
  return "checkout";
}

function creditsFor(item: CheckoutItem): number {
  const [kind, id] = item.split(":");
  if (kind === "pack") return packForItem(item)?.credits ?? 0;
  return PLANS.find((p) => p.name.toLowerCase() === id)?.credits ?? 0;
}

/**
 * The end of the "chose a plan before signing up" path: signup (and its email link or Google) returns here
 * with `?checkout=<item>`, and the checkout opens by itself, once, the same way the card's button would.
 * A signed-out visitor keeps the parameter and sees the cards, whose "Get started" carries it again.
 */
export function CheckoutIntent() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const raw = params.get("checkout");
  const user = usePricingAccount();
  const checkout = useCheckout();
  const { grant } = useGrant();
  const done = useRef(false);

  useEffect(() => {
    if (done.current || !user || !isCheckoutItem(raw)) return;
    done.current = true;
    // Drop the parameter first so a reload or Back does not open checkout a second time.
    router.replace(pathname, { scroll: false });
    const key = raw.startsWith("plan:") ? `plan:${PLANS.find((p) => `plan:${p.name.toLowerCase()}` === raw)?.name}` : raw;
    const action = intentAction(BACKEND, raw, user.plan);
    if (action === "grant") void grant(key, creditsFor(raw), raw.startsWith("plan:") ? "plan_grant" : "pack_purchase", packForItem(raw)?.id);
    else if (action === "checkout") void checkout.buy(key, raw);
  }, [user, raw, router, pathname, grant, checkout]);

  return null;
}
