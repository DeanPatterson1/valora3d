import { CREDIT_COSTS } from "@/lib/pricing";
import type { RenderTier } from "./params";

/**
 * Credits one render costs, by tier. Flat per tier (the studio offers 8-12 s clips); the numbers are the
 * existing placeholder prices in lib/pricing.ts until per-clip GPU cost is measured (worker README section 5:
 * set prices from the p90). Preview = 540p / 16 spp; final = 1080p adaptive, the old "High" cloud price.
 */
export const RENDER_COSTS: Record<RenderTier, number> = {
  preview: CREDIT_COSTS.preview_render,
  final: CREDIT_COSTS.cloud_final.high,
};

export function renderCost(tier: RenderTier): number {
  return RENDER_COSTS[tier];
}
