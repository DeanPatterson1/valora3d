import type { RenderTier } from "./params";

export type PlanId = "free" | "creator" | "pro";

export type RenderPlanLimits = {
  tiers: readonly RenderTier[];
  /** Burn a watermark into the clip. The worker contract has no watermark input yet (see README gap list). */
  watermark: boolean;
  /** Days a finished clip stays downloadable. Not enforced yet: needs an R2 lifecycle rule or a sweep. */
  retentionDays: number;
  /** Jobs that may be queued or running at once. */
  maxActiveJobs: number;
};

/**
 * TODO(lane C merge): replace with the billing lane's `plan_limits(plan)` (SQL, server-side) once Paddle
 * billing lands. This stub mirrors the public plan cards in lib/pricing.ts: Free renders previews only
 * (540p, watermarked, 7 days), Creator adds 1080p finals (30 days), Pro keeps 90 days.
 */
export function renderPlanLimits(plan: PlanId | null | undefined): RenderPlanLimits {
  switch (plan) {
    case "pro":
      return { tiers: ["preview", "final"], watermark: false, retentionDays: 90, maxActiveJobs: 4 };
    case "creator":
      return { tiers: ["preview", "final"], watermark: false, retentionDays: 30, maxActiveJobs: 2 };
    default:
      return { tiers: ["preview"], watermark: true, retentionDays: 7, maxActiveJobs: 1 };
  }
}
