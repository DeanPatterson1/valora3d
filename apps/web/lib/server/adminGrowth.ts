import { PLANS } from "@/lib/pricing";

/** Monthly list price per paid plan in minor units (USD cents), from lib/pricing.ts: MRR's price table. */
export function planPricesMinor(): Record<string, number> {
  return Object.fromEntries(
    PLANS.filter((p) => p.period === "month" && p.priceUsd > 0).map((p) => [p.name.toLowerCase(), Math.round(p.priceUsd * 100)]),
  );
}
