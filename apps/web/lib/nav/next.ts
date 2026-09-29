import { CHECKOUT_ITEMS, type CheckoutItem } from "@/lib/pricing";
import { safeNextPath } from "./safePath";

/**
 * Where a visitor goes after signing up or logging in, and how that destination survives the trip
 * (signup -> email confirmation or Google OAuth -> back here). ONE place builds and reads these links so
 * other intent carried through signup (a referral, a campaign) can be added here rather than to each CTA.
 *
 * Every destination is a same-origin path and is re-checked with `safeNextPath` wherever it is read.
 */

/** Where a brand-new visitor starts: the projects list with the New project dialog open. */
export const START_PATH = "/projects?new=1";
/** The default after sign-in when nothing else was asked for. */
export const DEFAULT_NEXT = "/projects";

export function isCheckoutItem(value: string | null | undefined): value is CheckoutItem {
  return typeof value === "string" && (CHECKOUT_ITEMS as readonly string[]).includes(value);
}

/** /pricing with a pending checkout, which opens by itself once the visitor is signed in. */
export function checkoutPath(item: CheckoutItem): string {
  return `/pricing?checkout=${encodeURIComponent(item)}`;
}

function withNext(path: "/signup" | "/login", next: string | null | undefined): string {
  const safe = next ? safeNextPath(next) : null;
  return safe && safe !== DEFAULT_NEXT ? `${path}?next=${encodeURIComponent(safe)}` : path;
}

/** "Get started" for a signed-out visitor. With an item, signup ends in that item's checkout. */
export function signupHref(next: string = START_PATH, item?: CheckoutItem): string {
  return withNext("/signup", item ? checkoutPath(item) : next);
}

export function loginHref(next?: string | null): string {
  return withNext("/login", next);
}

type Params = { get(name: string): string | null };

/**
 * The destination an auth page was asked for: `?next=`, or a plan/pack chosen before signup
 * (`?plan=creator|pro`, `?pack=100|500|2000`), which becomes that item's checkout.
 */
export function nextFromParams(params: Params): string {
  const plan = params.get("plan");
  if (plan && isCheckoutItem(`plan:${plan}`)) return checkoutPath(`plan:${plan}` as CheckoutItem);
  const pack = params.get("pack");
  if (pack && isCheckoutItem(`pack:${pack}`)) return checkoutPath(`pack:${pack}` as CheckoutItem);
  return safeNextPath(params.get("next"), DEFAULT_NEXT);
}

/** The PKCE landing for Google sign-in and email links: exchanges the code, then continues to `next`. */
export function authCallbackUrl(origin: string, next: string): string {
  return `${origin}/auth/callback?next=${encodeURIComponent(safeNextPath(next, DEFAULT_NEXT))}`;
}

/**
 * The `next` on an emailed confirmation link. The template fills it from Supabase's `{{ .RedirectTo }}`,
 * which is the absolute `emailRedirectTo` passed at signup (`authCallbackUrl`), or the Site URL when that
 * address is not on the project's allow list. Only a PATH is ever taken from it, so a foreign origin
 * cannot become a redirect target; everything else falls back to the default.
 */
export function nextFromRedirectTo(raw: string | null | undefined, fallback = DEFAULT_NEXT): string {
  if (!raw) return fallback;
  if (raw.startsWith("/")) return safeNextPath(raw, fallback);
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return fallback;
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") return fallback;
  if (url.pathname === "/auth/callback") return safeNextPath(url.searchParams.get("next"), fallback);
  if (url.pathname === "/" && !url.search) return fallback;
  return safeNextPath(url.pathname + url.search, fallback);
}
export { safeNextPath };
