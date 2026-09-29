import { ogCard, OG_SIZE } from "@/lib/og";
import { FREE_PLAN_CREDITS, PLANS } from "@/lib/pricing";

export const alt = "Valora3D pricing";
export const size = OG_SIZE;
export const contentType = "image/png";

/** Prices come from PLANS, so the card can never disagree with the page. */
export default function PricingOpenGraphImage() {
  const paid = PLANS.filter((p) => p.period === "month").map((p) => `${p.name} $${p.priceUsd}/mo`).join(" · ");
  return ogCard({ eyebrow: "Pricing", title: "Start free. Upgrade when you render more.", lead: `${FREE_PLAN_CREDITS} free credits, no card. ${paid}. One-time credit packs.` });
}
