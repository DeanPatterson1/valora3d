import { CHECKOUT_ITEMS, packForItem, planCredits, type CheckoutItem, type PlanId } from "@/lib/pricing";

/**
 * The server-side catalog: checkout item -> Paddle price id -> what it grants. The browser only
 * ever names a CheckoutItem; the price id comes from env (lib/env.ts `readBillingConfig`) and the
 * credits from lib/pricing. The webhook resolves the paid price id back through the same table, so
 * an unknown price (anything else in the Paddle catalog) grants nothing.
 */
export type CatalogEntry =
  | { item: CheckoutItem; priceId: string; kind: "plan"; plan: Exclude<PlanId, "free">; credits: number }
  | { item: CheckoutItem; priceId: string; kind: "pack"; credits: number; packId: string; oncePerAccount: boolean };

export type Catalog = {
  byItem: (item: string) => CatalogEntry | null;
  byPriceId: (priceId: string) => CatalogEntry | null;
  entries: CatalogEntry[];
};

export function isCheckoutItem(value: unknown): value is CheckoutItem {
  return typeof value === "string" && (CHECKOUT_ITEMS as readonly string[]).includes(value);
}

function describe(item: CheckoutItem, priceId: string): CatalogEntry {
  const [kind, rest] = item.split(":") as ["plan" | "pack", string];
  if (kind === "plan") {
    const plan = rest as Exclude<PlanId, "free">;
    return { item, priceId, kind, plan, credits: planCredits(plan) };
  }
  const pack = packForItem(item);
  if (!pack) throw new Error(`unknown pack ${item}`);
  return { item, priceId, kind, credits: pack.credits, packId: pack.id, oncePerAccount: pack.oncePerAccount };
}

export function buildCatalog(prices: Partial<Record<CheckoutItem, string>>): Catalog {
  const entries: CatalogEntry[] = [];
  const seen = new Set<string>();
  for (const item of CHECKOUT_ITEMS) {
    const priceId = prices[item];
    if (!priceId) continue;
    // Two items on one price would make the webhook ambiguous: refuse the misconfiguration.
    if (seen.has(priceId)) throw new Error(`price ${priceId} is configured for two items`);
    seen.add(priceId);
    entries.push(describe(item, priceId));
  }
  return {
    entries,
    byItem: (item) => entries.find((e) => e.item === item) ?? null,
    byPriceId: (priceId) => entries.find((e) => e.priceId === priceId) ?? null,
  };
}
