import { REFERRAL_BONUS_CREDITS, REFERRAL_MONTHLY_CAP } from "@/lib/pricing";

/**
 * Referrals: every account has a code; its link is /signup?ref=u_<code>. The `ref` rides the first-touch
 * attribution cookie (lib/analytics/attribution.ts) into profiles.signup_source, and the database pays
 * REFERRAL_BONUS_CREDITS to both people when the new account's FIRST payment completes
 * (supabase/migrations/20260930120000_pricing_referrals.sql). Nothing is paid for a signup alone.
 */

/** A referral code as the database makes it: 10 lowercase letters/digits. */
export const REFERRAL_CODE = /^[a-z0-9]{10}$/;

/** The attribution `ref` for a code. */
export function referralRef(code: string): string {
  return `u_${code}`;
}

/** The share link for a code, on this site's origin. */
export function referralLink(origin: string, code: string): string {
  return `${origin.replace(/\/+$/, "")}/signup?ref=${referralRef(code)}`;
}

/** The terms in one plain line, shown on the invite card (the full text is in the terms, "Referrals"). */
export const REFERRAL_TERMS_LINE =
  `When someone signs up with your link and makes their first payment, you both get ${REFERRAL_BONUS_CREDITS} credits. ` +
  `Up to ${REFERRAL_MONTHLY_CAP} rewards a month; refunded payments and your own accounts don't count.`;

export type ReferralSummary = {
  code: string;
  /** Accounts that signed up with the link. */
  joined: number;
  /** Of those, how many made a first payment that paid the bonus. */
  qualified: number;
  /** Credits the link has earned this account (net of reversals). */
  creditsEarned: number;
};

/** Validates referral_summary() JSON from the database (snake_case) or the API route (camelCase). */
export function toReferralSummary(raw: unknown): ReferralSummary | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : Number(v));
  if (typeof r.code !== "string" || !REFERRAL_CODE.test(r.code)) return null;
  const joined = num(r.joined);
  const qualified = num(r.qualified);
  const creditsEarned = num(r.credits_earned ?? r.creditsEarned);
  if (![joined, qualified, creditsEarned].every(Number.isFinite)) return null;
  return { code: r.code, joined, qualified, creditsEarned };
}

/**
 * Local mode has no referral backend: a stable demo code from the local user id, so the card can be seen and
 * its link copied. No credits are ever paid for it.
 */
export function localReferralCode(userId: string): string {
  let h = 2166136261;
  for (let i = 0; i < userId.length; i++) h = Math.imul(h ^ userId.charCodeAt(i), 16777619) >>> 0;
  let h2 = h ^ 0x9e3779b9;
  let out = "";
  for (let i = 0; i < 10; i++) {
    h2 = Math.imul(h2 ^ (h2 >>> 15), 2246822507) >>> 0;
    out += "abcdefghijklmnopqrstuvwxyz0123456789"[h2 % 36];
  }
  return out;
}
