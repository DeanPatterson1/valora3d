import { z } from "@/lib/zod";
import { nextFromRedirectTo } from "@/lib/nav/next";

/**
 * Email links (`/auth/confirm?token_hash=…&type=…`) and login CSRF (security review L2).
 *
 * A token-hash link signs in whoever opens it as the account it was sent to. Anyone can get such a link for
 * THEIR OWN account and mail it to someone else; opening it would silently sign the victim into the attacker's
 * account (their uploads and payments then land there). So:
 *   1. GET /auth/confirm never uses the token. It forwards to /auth/continue, an interstitial with a POST form.
 *      (That also stops mail scanners that prefetch links from burning the one-time token.)
 *   2. POST /auth/confirm accepts only a same-origin form post, then verifies the token.
 *   3. A browser that asked for an email here (sign-up, password reset) carries the EMAIL_FLOW_COOKIE hint. A link
 *      opened without it (another device, or someone else's link) gets a warning before, and "you're signed in as
 *      <email>, not you? sign out" after. Cross-device confirmation keeps working: it is one extra click.
 */

export { EMAIL_FLOW_COOKIE } from "./emailFlow";

/** The link types our templates send (lib/email/authTemplates.ts). `magiclink` is not one of them. */
export const CONFIRM_TYPES = ["email", "signup", "recovery", "email_change", "invite"] as const;
export type ConfirmType = (typeof CONFIRM_TYPES)[number];

const ConfirmParams = z.object({
  token_hash: z.string().regex(/^[A-Za-z0-9_-]{16,256}$/),
  type: z.enum(CONFIRM_TYPES),
  next: z.string().max(512).nullish(),
});

export type ConfirmLink = { tokenHash: string; type: ConfirmType; next: string };

/**
 * Where a confirmed link continues to: recovery always sets a new password; the rest go to a same-origin `next`.
 * The confirmation template fills `next` from `{{ .RedirectTo }}` (an absolute URL), so only its path is kept.
 */
export function nextFor(type: ConfirmType, next: string | null | undefined): string {
  return type === "recovery" ? "/reset-password" : nextFromRedirectTo(next);
}

/** Reads token_hash / type / next from a query string or a posted form. Null when anything is off. */
export function parseConfirmLink(get: (name: string) => string | null | undefined): ConfirmLink | null {
  const parsed = ConfirmParams.safeParse({ token_hash: get("token_hash"), type: get("type"), next: get("next") });
  if (!parsed.success) return null;
  return { tokenHash: parsed.data.token_hash, type: parsed.data.type, next: nextFor(parsed.data.type, parsed.data.next) };
}

/** The interstitial for a link: /auth/continue?token_hash=…&type=…&next=… */
export function continueUrl(link: ConfirmLink): string {
  const q = new URLSearchParams({ token_hash: link.tokenHash, type: link.type, next: link.next });
  return `/auth/continue?${q.toString()}`;
}
