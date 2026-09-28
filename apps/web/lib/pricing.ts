import type { ScenePlan } from "@/lib/schema";

/**
 * Credits granted once to a new account (the Free plan). The database grant mirrors this in
 * supabase/migrations/*_init.sql (`public.free_plan_credits()`); pricing.test.ts pins both.
 */
export const FREE_PLAN_CREDITS = 50;
/** The balance a brand-new account starts with: exactly the Free plan grant. */
export const STARTING_BALANCE = FREE_PLAN_CREDITS;

export const CREDIT_COSTS = {
  model_analysis: 0,
  scene_generation: 2,
  prompt_edit: 1,
  slider_change: 0,
  preview_render: 3,
  local_final: 5,
  cloud_final: { standard: 30, high: 60, ultra: 90, "4k": 160 },
} as const;

export type PlanDef = {
  name: string;
  priceUsd: number;
  period: "once" | "month";
  credits: number;
  features: string[];
  highlighted: boolean;
};

export const PLANS: PlanDef[] = [
  { name: "Free", priceUsd: 0, period: "once", credits: FREE_PLAN_CREDITS,
    features: [`${FREE_PLAN_CREDITS} credits`, "720p renders", "Watermark", "7-day retention"], highlighted: false },
  { name: "Creator", priceUsd: 19, period: "month", credits: 500,
    features: ["500 credits / month", "1080p renders", "Cloud GPU rendering", "30-day retention"], highlighted: true },
  { name: "Pro", priceUsd: 49, period: "month", credits: 2000,
    features: ["2,000 credits / month", "4K renders", "Priority GPU", "Commercial use", "90-day retention"], highlighted: false },
];

export const CREDIT_PACKS = [
  { credits: 100, priceUsd: 5 },
  { credits: 500, priceUsd: 20 },
  { credits: 2000, priceUsd: 70 },
] as const;

/** Cloud final render price for an output setting. 4K has one rate whatever the quality; draft is billed as standard. */
export function cloudPrice(output: ScenePlan["output"]): number {
  if (output.resolution === "4k") return CREDIT_COSTS.cloud_final["4k"];
  if (output.quality === "draft") return CREDIT_COSTS.cloud_final.standard;
  return CREDIT_COSTS.cloud_final[output.quality];
}

/** Largest accepted model upload (200 MB). Mirrored by `public.max_upload_bytes()` in the database. */
export const MAX_UPLOAD_BYTES = 200 * 1024 * 1024;

/** Paid plans, keyed by the `plan_tier` value stored in the database. */
export type PlanId = "free" | "creator" | "pro";

/** Monthly credits each plan grants (from PLANS). Free is the one-off signup grant. */
export function planCredits(plan: PlanId): number {
  const def = PLANS.find((p) => p.name.toLowerCase() === plan);
  if (!def) throw new Error(`unknown plan ${plan}`);
  return def.credits;
}

export type PlanLimits = {
  /** Largest output resolution a render may use. */
  maxResolution: "720p" | "1080p" | "4k";
  /** Burn the Valora3D watermark into the output. */
  watermark: boolean;
  /** Days render outputs are kept before deletion. */
  retentionDays: number;
  /** Queue priority: higher runs first. */
  priority: number;
};

/**
 * Server-enforced limits per plan. Mirrored by `public.plan_limits(plan)` in
 * supabase/migrations/*_billing.sql (pricing.test.ts pins both). The render lane reads the SQL
 * side with `user_plan_limits(user_id)`, which also resolves the user's effective plan.
 */
export const PLAN_LIMITS: Record<PlanId, PlanLimits> = {
  free: { maxResolution: "720p", watermark: true, retentionDays: 7, priority: 0 },
  creator: { maxResolution: "1080p", watermark: false, retentionDays: 30, priority: 1 },
  pro: { maxResolution: "4k", watermark: false, retentionDays: 90, priority: 2 },
};

export function planLimits(plan: PlanId): PlanLimits {
  return PLAN_LIMITS[plan];
}

/**
 * What the browser may ask to buy: a catalog key, never a price or an amount. The server maps a
 * key to a Paddle price id (lib/billing/catalog.ts); the webhook maps the price id back.
 */
export const CHECKOUT_ITEMS = ["plan:creator", "plan:pro", "pack:100", "pack:500", "pack:2000"] as const;
export type CheckoutItem = (typeof CHECKOUT_ITEMS)[number];
