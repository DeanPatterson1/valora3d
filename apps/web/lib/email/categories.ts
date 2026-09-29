/**
 * Email categories and lifecycle kinds. Mirrors `email_kinds()` / `email_kind_category()` in
 * supabase/migrations/20260930130000_lifecycle.sql (pinned by lib/email/lifecycle.test.ts).
 *
 *   tips     product tips: welcome, the "haven't rendered yet?" nudge, day-7 tips, win-back. Opt-out
 *            (profiles.email_product_tips).
 *   renders  render notifications: "render ready" and "renders expire soon". Opt-out (profiles.email_render_ready).
 *   account  account and billing: payment overdue, plan canceled / paused, cancel confirmation. Transactional, always
 *            sent (no unsubscribe link, not held back by the suppression list).
 */

export const LIFECYCLE_KINDS = [
  "welcome",
  "activation_nudge",
  "tips",
  "expiry_warning",
  "winback",
  "past_due",
  "plan_canceled",
  "cancel_scheduled",
  "plan_paused",
] as const;
export type LifecycleKind = (typeof LIFECYCLE_KINDS)[number];

export const EMAIL_CATEGORIES = ["tips", "renders", "account"] as const;
export type EmailCategory = (typeof EMAIL_CATEGORIES)[number];
/** The categories a person can turn off (and one-click unsubscribe from). */
export type OptOutCategory = Exclude<EmailCategory, "account">;
export const OPT_OUT_CATEGORIES: readonly OptOutCategory[] = ["tips", "renders"];

export function kindCategory(kind: LifecycleKind): EmailCategory {
  if (kind === "welcome" || kind === "activation_nudge" || kind === "tips" || kind === "winback") return "tips";
  if (kind === "expiry_warning") return "renders";
  return "account";
}

/** What each opt-out category is called in Settings and on the unsubscribe page. */
export const CATEGORY_LABEL: Record<OptOutCategory, string> = {
  tips: "product tips",
  renders: "render notifications",
};

/** The profile column each opt-out category writes. */
export const CATEGORY_COLUMN: Record<OptOutCategory, "email_product_tips" | "email_render_ready"> = {
  tips: "email_product_tips",
  renders: "email_render_ready",
};

/** Replies to any Valora3D mail land here (the sender addresses are not read). */
export const SUPPORT_EMAIL = "support@valora3d.com";
