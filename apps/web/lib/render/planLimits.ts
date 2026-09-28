import { PLAN_LIMITS, type PlanId, type PlanLimits } from "@/lib/pricing";
import { TIERS, type RenderTier } from "./params";

export type { PlanId };
export type RenderPlanLimits = PlanLimits;

/**
 * The limits of a plan for DISPLAY (the studio's tier cards, the pricing page). The server never trusts this:
 * create_render_job reads the live entitlement with `user_plan_limits(user_id)` and enforces tiers, concurrent
 * jobs and the watermark under the credit lock. Unknown or missing plan => Free.
 */
export function renderPlanLimits(plan: PlanId | null | undefined): RenderPlanLimits {
  return PLAN_LIMITS[plan ?? "free"] ?? PLAN_LIMITS.free;
}

const PLAN_IDS = Object.keys(PLAN_LIMITS) as PlanId[];

/** One row of `public.user_plan_limits(user_id)` as PostgREST returns it. */
export type PlanLimitsRow = {
  plan: string;
  max_resolution: string;
  tiers: string[];
  watermark: boolean;
  retention_days: number;
  max_active_jobs: number;
  plan_rank: number;
};

/**
 * Parses a `user_plan_limits` row. Anything malformed falls back to Free's limits (fail closed: previews only,
 * watermarked, one at a time), never to a looser plan.
 */
export function limitsFromRow(row: PlanLimitsRow | null | undefined): { plan: PlanId; limits: RenderPlanLimits } {
  const free = { plan: "free" as const, limits: PLAN_LIMITS.free };
  if (!row || !PLAN_IDS.includes(row.plan as PlanId)) return free;
  const tiers = Array.isArray(row.tiers) ? row.tiers.filter((t): t is RenderTier => (TIERS as readonly string[]).includes(t)) : [];
  if (tiers.length === 0 || typeof row.watermark !== "boolean") return free;
  const maxResolution = row.max_resolution === "1080p" ? "1080p" : "540p";
  const int = (v: unknown, min: number) => (typeof v === "number" && Number.isInteger(v) && v >= min ? v : null);
  const retentionDays = int(row.retention_days, 1);
  const maxActiveJobs = int(row.max_active_jobs, 1);
  if (retentionDays === null || maxActiveJobs === null) return free;
  return {
    plan: row.plan as PlanId,
    limits: { maxResolution, tiers, watermark: row.watermark, retentionDays, maxActiveJobs, rank: int(row.plan_rank, 0) ?? 0 },
  };
}
