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
  /** A 540p preview render on the cloud GPU (lib/render/cost.ts). */
  preview_render: 3,
  local_final: 5,
  /** A 1080p final render on the cloud GPU (lib/render/cost.ts). There is no 4K tier: the worker renders 540p or 1080p. */
  final_render: 60,
} as const;

/** Paid plans, keyed by the `plan_tier` value stored in the database. */
export type PlanId = "free" | "creator" | "pro";

/** The render tiers the worker can produce (Rendering-worker `worker/contract.py`): preview 540p, final 1080p. */
export type PlanTier = "preview" | "final";

export type PlanLimits = {
  /** Largest output the plan can render: its best tier's short side. */
  maxResolution: "540p" | "1080p";
  /** Render tiers the plan may use. */
  tiers: readonly PlanTier[];
  /** Burn the Valora3D watermark into the output (the worker's params.watermark, set server-side). */
  watermark: boolean;
  /** Days render outputs are kept after the render finishes, and models after their last use. */
  retentionDays: number;
  /** Renders that may be queued or running at once. */
  maxActiveJobs: number;
  /** Free < Creator < Pro: decides upgrade vs downgrade. Not a GPU priority (RunPod has none per job). */
  rank: number;
};

/**
 * Server-enforced limits per plan: the single source of truth for the plan cards and the render gate.
 * Mirrored by `public.plan_limits(plan)` in supabase/migrations/20260928150000_plan_limits_v2.sql
 * (lib/billing/billing.test.ts pins both). The server reads the SQL side with `user_plan_limits(user_id)`,
 * which also resolves the user's live plan; create_render_job enforces tiers, concurrency and the watermark.
 */
export const PLAN_LIMITS: Record<PlanId, PlanLimits> = {
  free: { maxResolution: "540p", tiers: ["preview"], watermark: true, retentionDays: 7, maxActiveJobs: 1, rank: 0 },
  creator: { maxResolution: "1080p", tiers: ["preview", "final"], watermark: false, retentionDays: 30, maxActiveJobs: 1, rank: 1 },
  pro: { maxResolution: "1080p", tiers: ["preview", "final"], watermark: false, retentionDays: 90, maxActiveJobs: 3, rank: 2 },
};

export function planLimits(plan: PlanId): PlanLimits {
  return PLAN_LIMITS[plan];
}

/** Plan-card lines derived from PLAN_LIMITS, so a card can only promise what the render gate enforces. */
export function limitFeatures(plan: PlanId): string[] {
  const l = PLAN_LIMITS[plan];
  return [
    l.tiers.includes("final") ? "540p previews + 1080p final renders" : "540p preview renders",
    l.watermark ? "Watermark on renders" : "No watermark",
    l.maxActiveJobs === 1 ? "1 render at a time" : `${l.maxActiveJobs} renders at once`,
    `${l.retentionDays}-day retention`,
  ];
}

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
    features: [`${FREE_PLAN_CREDITS} credits`, ...limitFeatures("free")], highlighted: false },
  { name: "Creator", priceUsd: 19, period: "month", credits: 500,
    features: ["500 credits / month", ...limitFeatures("creator")], highlighted: true },
  { name: "Pro", priceUsd: 49, period: "month", credits: 2000,
    features: ["2,000 credits / month", ...limitFeatures("pro")], highlighted: false },
];

export const CREDIT_PACKS = [
  { credits: 100, priceUsd: 5 },
  { credits: 500, priceUsd: 20 },
  { credits: 2000, priceUsd: 70 },
] as const;

/** Largest accepted model upload (200 MB). Mirrored by `public.max_upload_bytes()` in the database. */
export const MAX_UPLOAD_BYTES = 200 * 1024 * 1024;

/** Monthly credits each plan grants (from PLANS). Free is the one-off signup grant. */
export function planCredits(plan: PlanId): number {
  const def = PLANS.find((p) => p.name.toLowerCase() === plan);
  if (!def) throw new Error(`unknown plan ${plan}`);
  return def.credits;
}

/**
 * What the browser may ask to buy: a catalog key, never a price or an amount. The server maps a
 * key to a Paddle price id (lib/billing/catalog.ts); the webhook maps the price id back.
 */
export const CHECKOUT_ITEMS = ["plan:creator", "plan:pro", "pack:100", "pack:500", "pack:2000"] as const;
export type CheckoutItem = (typeof CHECKOUT_ITEMS)[number];
