import { CREDIT_COSTS } from "@/lib/pricing";
import type { RenderTier } from "./params";

/**
 * Credits one render costs, by tier. Flat per tier (the studio offers 8-12 s clips); the numbers are the
 * existing placeholder prices in lib/pricing.ts until per-clip GPU cost is measured (worker README section 5:
 * set prices from the p90). Preview = 540p / 16 spp; final = 1080p adaptive.
 */
export const RENDER_COSTS: Record<RenderTier, number> = {
  preview: CREDIT_COSTS.preview_render,
  final: CREDIT_COSTS.final_render,
};

export function renderCost(tier: RenderTier): number {
  return RENDER_COSTS[tier];
}

export type LowBalance = { text: string; getCredits: boolean };

/**
 * The quiet line under the Render button, in honest render counts. A plan that renders Finals hears about the
 * Final price only while it cannot afford one; a plan that cannot render Finals (Free) is never told to buy
 * credits for a Final it could not start: it sees how many Previews are left, and "Get credits" only at zero.
 * Null when nothing needs saying.
 */
export function lowBalance(balance: number, canFinal: boolean): LowBalance | null {
  const preview = renderCost("preview");
  const final = renderCost("final");
  const previews = Math.max(0, Math.floor(balance / preview));
  const left = `${balance.toLocaleString("en-US")} ${balance === 1 ? "credit" : "credits"} left`;
  const count = `${previews.toLocaleString("en-US")} ${previews === 1 ? "Preview" : "Previews"}`;
  if (canFinal) {
    if (balance >= final) return null;
    return previews === 0
      ? { text: `${left}, not enough for a Preview (${preview}) or a Final (${final}).`, getCredits: true }
      : { text: `${left}: enough for ${count}. A Final uses ${final}.`, getCredits: true };
  }
  return previews === 0
    ? { text: `${left}, not enough for a Preview (${preview}).`, getCredits: true }
    : { text: `${left}: enough for ${count}.`, getCredits: false };
}
