/**
 * THE price list (TypeScript layer). Every number a user pays, spends or is granted lives here once; the
 * database mirrors live together in supabase/migrations/20260930120000_pricing_referrals.sql, and
 * lib/pricing.test.ts pins the two layers to each other.
 *
 * PLACEHOLDER PRICES (pricing v3, owner-approved direction from a blind buyer-panel review). Unit: 100 credits =
 * one 1080p final clip. Before launch they are re-derived from the measured p90 GPU cost per clip
 * (docs/launch-plan.md, "Pricing"; expected cost per final about $0.10-0.40).
 */

/**
 * Credits granted once to a new account (the Free plan), after the email is confirmed. SQL:
 * `public.free_plan_credits()`.
 */
export const FREE_PLAN_CREDITS = 10;
/** The balance a brand-new account starts with: exactly the Free plan grant. */
export const STARTING_BALANCE = FREE_PLAN_CREDITS;

export const CREDIT_COSTS = {
  model_analysis: 0,
  /** SQL: `public.scene_action_cost('generate')`. */
  scene_generation: 5,
  /** SQL: `public.scene_action_cost('edit')`. */
  prompt_edit: 2,
  /** SQL: `public.scene_action_cost('adjust')`. */
  slider_change: 0,
  /** A 540p preview render on the cloud GPU (lib/render/cost.ts). SQL: `public.render_cost('preview')`. */
  preview_render: 5,
  local_final: 3,
  /** A 1080p final render on the cloud GPU. There is no 4K tier: the worker renders 540p or 1080p. SQL: `render_cost('final')`. */
  final_render: 100,
} as const;

/**
 * Credits kept when the user's own model or scene makes a render fail: the price of one Preview (never more than
 * the job cost). lib/render/failurePolicy.ts applies it; SQL: `public.render_failure_fee()`.
 */
export const RENDER_FAILURE_FEE = CREDIT_COSTS.preview_render;

/**
 * Monthly plan credits roll over for at most this many billing periods: credits granted for a period that are
 * still unused when the NEXT period ends expire (a `credit_expiry` ledger row written by the daily sweep).
 * Pack credits, the Free grant and referral bonuses never expire. SQL: `public.plan_credit_rollover()`.
 */
export const PLAN_CREDIT_ROLLOVER_PERIODS = 1;

/**
 * Referrals: both the referrer and the new user get this bonus when the new user's FIRST payment completes
 * (never on signup alone). SQL: `public.referral_bonus_credits()`.
 */
export const REFERRAL_BONUS_CREDITS = 100;
/** At most this many referrals are rewarded per referrer per calendar month (UTC). SQL: `public.referral_monthly_cap()`. */
export const REFERRAL_MONTHLY_CAP = 20;

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

const fmt = (n: number) => n.toLocaleString("en-US");
const count = (n: number, one: string) => `${fmt(n)} ${n === 1 ? one : `${one}s`}`;

/**
 * What a number of credits buys, in renders, honest to the plan: a plan that cannot render Finals is never told
 * how many Finals its credits would buy. "3 Previews", "40 Previews or 2 Finals".
 */
export function creditValue(credits: number, plan: PlanId): string {
  const previews = Math.floor(credits / CREDIT_COSTS.preview_render);
  const finals = Math.floor(credits / CREDIT_COSTS.final_render);
  const p = count(previews, "Preview");
  if (!PLAN_LIMITS[plan].tiers.includes("final") || finals === 0) return p;
  return `${p} or ${count(finals, "Final")}`;
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

/** Plan-card line for the rollover rule. */
export const ROLLOVER_NOTE = `Unused plan credits roll over ${PLAN_CREDIT_ROLLOVER_PERIODS === 1 ? "one month" : `${PLAN_CREDIT_ROLLOVER_PERIODS} months`}`;

export type PlanDef = {
  name: string;
  priceUsd: number;
  period: "once" | "month";
  credits: number;
  /** What the credits buy on this plan: "3 Previews", "40 Previews or 2 Finals" (creditValue). */
  value: string;
  features: string[];
  highlighted: boolean;
};

function planDef(id: PlanId, name: string, priceUsd: number, credits: number, highlighted: boolean): PlanDef {
  const period = id === "free" ? "once" : "month";
  const creditsLine = period === "once" ? `${fmt(credits)} credits, once` : `${fmt(credits)} credits / month`;
  const extra = period === "month" ? [ROLLOVER_NOTE] : [];
  return {
    name, priceUsd, period, credits, value: creditValue(credits, id),
    features: [creditsLine, ...limitFeatures(id), ...extra], highlighted,
  };
}

export const PLANS: PlanDef[] = [
  planDef("free", "Free", 0, FREE_PLAN_CREDITS, false),
  planDef("creator", "Creator", 24, 800, true),
  planDef("pro", "Pro", 49, 2500, false),
];

/**
 * One-time credit packs. `id` is the checkout key and env-name stem (`pack:first` -> PADDLE_PRICE_PACK_FIRST,
 * `pack:5` -> PADDLE_PRICE_PACK_5); `clips` is how many 1080p finals the credits buy. Pack credits never expire.
 * The "first" pack is a once-per-account intro price: the checkout route refuses a second purchase and the database
 * records it in `billing_transactions.pack_id` under a unique index (supabase/migrations/20260930120000).
 */
export const CREDIT_PACKS = [
  { id: "first", clips: 1, credits: 100, priceUsd: 2, oncePerAccount: true },
  { id: "1", clips: 1, credits: 100, priceUsd: 6, oncePerAccount: false },
  { id: "5", clips: 5, credits: 500, priceUsd: 20, oncePerAccount: false },
  { id: "15", clips: 15, credits: 1500, priceUsd: 55, oncePerAccount: false },
] as const;

export type CreditPack = (typeof CREDIT_PACKS)[number];
/** The pack id sold once per account (the database stores it as `pack_id`). */
export const FIRST_CLIP_PACK_ID = "first";

/** Largest accepted model upload (200 MB). Mirrored by `public.max_upload_bytes()` in the database. */
export const MAX_UPLOAD_BYTES = 200 * 1024 * 1024;

/** Monthly credits each plan grants (from PLANS). Free is the one-off signup grant. */
export function planCredits(plan: PlanId): number {
  const def = PLANS.find((p) => p.name.toLowerCase() === plan);
  if (!def) throw new Error(`unknown plan ${plan}`);
  return def.credits;
}

export type PackItem = `pack:${CreditPack["id"]}`;
export type CheckoutItem = "plan:creator" | "plan:pro" | PackItem;

/**
 * What the browser may ask to buy: a catalog key, never a price or an amount. The server maps a
 * key to a Paddle price id (lib/billing/catalog.ts); the webhook maps the price id back.
 */
export const CHECKOUT_ITEMS: readonly CheckoutItem[] = [
  "plan:creator",
  "plan:pro",
  ...CREDIT_PACKS.map((p) => `pack:${p.id}` as PackItem),
];

/** Env var holding the Paddle price id for a checkout item: PADDLE_PRICE_CREATOR_MONTHLY, PADDLE_PRICE_PACK_FIRST, PADDLE_PRICE_PACK_15, … */
export function priceEnvName(item: CheckoutItem): string {
  if (item === "plan:creator") return "PADDLE_PRICE_CREATOR_MONTHLY";
  if (item === "plan:pro") return "PADDLE_PRICE_PRO_MONTHLY";
  return `PADDLE_PRICE_PACK_${item.slice("pack:".length).toUpperCase()}`;
}

/** "First clip", "1 clip", "5 clips": what a pack is called on the card, its button and the structured data. */
export function packTitle(pack: CreditPack): string {
  return pack.oncePerAccount ? "First clip" : `${pack.clips} ${pack.clips === 1 ? "clip" : "clips"}`;
}

/** The pack behind a `pack:<id>` checkout item, or null. */
export function packForItem(item: string): CreditPack | null {
  return CREDIT_PACKS.find((p) => `pack:${p.id}` === item) ?? null;
}
