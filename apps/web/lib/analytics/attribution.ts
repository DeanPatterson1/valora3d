import { routeTemplate } from "./events";

/**
 * First-touch attribution: where a visitor first came from, kept in one first-party cookie (90 days, SameSite=Lax,
 * no tracking id in it) and saved on the account at signup (`profiles.signup_source`) and on each payment
 * (`billing_transactions.source`). Set by proxy.ts only on a page visit that carries utm_* / ref parameters or
 * arrives from another site, and only if no attribution cookie exists yet (first touch wins).
 * Disclosed in the privacy notice. Not set when the browser sends Global Privacy Control (Sec-GPC: 1).
 */

export const ATTRIBUTION_COOKIE = "v3d_src";
export const ATTRIBUTION_MAX_AGE = 90 * 24 * 3600;

export type Attribution = {
  source?: string;
  medium?: string;
  campaign?: string;
  content?: string;
  term?: string;
  /** ?ref=… (e.g. share_<slug> from a share page's CTA). */
  ref?: string;
  /** Route template of the first page. */
  landing?: string;
  /** Host of the referring site, never its path. */
  referrer?: string;
  /** ISO date (day) of the first touch. */
  at?: string;
};

const KEYS = ["source", "medium", "campaign", "content", "term", "ref", "landing", "referrer", "at"] as const;
const UTM = { utm_source: "source", utm_medium: "medium", utm_campaign: "campaign", utm_content: "content", utm_term: "term" } as const;

/** Short, plain tokens only: lowercased letters, digits and . _ - (campaign names with spaces become dashes). */
function clean(value: string | null | undefined, max = 64): string | undefined {
  if (!value) return undefined;
  const v = value
    .trim()
    .toLowerCase()
    .replace(/[\s+]+/g, "-")
    .replace(/[^a-z0-9._-]/g, "")
    .slice(0, max);
  return v || undefined;
}

/** `ref` keeps its case: share slugs are case-sensitive base64url. */
function cleanRef(value: string | null): string | undefined {
  if (!value) return undefined;
  const v = value.trim().replace(/[^A-Za-z0-9_-]/g, "").slice(0, 80);
  return v || undefined;
}

function referrerHost(referer: string | null, ownHost: string): string | undefined {
  if (!referer) return undefined;
  try {
    const url = new URL(referer);
    if (url.protocol !== "http:" && url.protocol !== "https:") return undefined;
    const host = url.hostname.toLowerCase().replace(/^www\./, "");
    const own = ownHost.toLowerCase().split(":")[0].replace(/^www\./, "");
    if (!host || host === own) return undefined;
    return clean(host, 80);
  } catch {
    return undefined;
  }
}

/**
 * The attribution of one page visit, or null when it carries none (a direct visit, an internal navigation).
 * Pure: the proxy passes the URL, the Referer header and its own host.
 */
export function attributionFromVisit(url: URL, referer: string | null, now = new Date()): Attribution | null {
  const out: Attribution = {};
  for (const [param, key] of Object.entries(UTM) as [keyof typeof UTM, (typeof UTM)[keyof typeof UTM]][]) {
    const v = clean(url.searchParams.get(param));
    if (v) out[key] = v;
  }
  const ref = cleanRef(url.searchParams.get("ref"));
  if (ref) out.ref = ref;
  const referrer = referrerHost(referer, url.host);
  if (referrer) out.referrer = referrer;
  if (!out.source && !out.medium && !out.campaign && !out.ref && !out.referrer) return null;
  out.landing = routeTemplate(url.pathname);
  out.at = now.toISOString().slice(0, 10);
  return out;
}

function toBase64Url(s: string): string {
  const bytes = new TextEncoder().encode(s);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(s: string): string | null {
  try {
    const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/"));
    return new TextDecoder("utf-8", { fatal: true }).decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)));
  } catch {
    return null;
  }
}

export function encodeAttribution(a: Attribution): string {
  return toBase64Url(JSON.stringify(sanitizeAttribution(a) ?? {}));
}

/** Re-validates anything read back (a cookie, Paddle custom data): known keys, short plain strings. */
export function sanitizeAttribution(raw: unknown): Attribution | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const src = raw as Record<string, unknown>;
  const out: Attribution = {};
  for (const key of KEYS) {
    const v = src[key];
    if (typeof v !== "string") continue;
    const c =
      key === "ref"
        ? cleanRef(v)
        : key === "landing"
          ? routeTemplate(v)
          : key === "at"
            ? /^\d{4}-\d{2}-\d{2}$/.test(v)
              ? v
              : undefined
            : clean(v, 80);
    if (c) out[key] = c;
  }
  return Object.keys(out).length ? out : null;
}

export function decodeAttribution(cookie: string | null | undefined): Attribution | null {
  if (!cookie || cookie.length > 800 || !/^[A-Za-z0-9_-]+$/.test(cookie)) return null;
  const json = fromBase64Url(cookie);
  if (!json) return null;
  try {
    return sanitizeAttribution(JSON.parse(json));
  } catch {
    return null;
  }
}

/** Set-Cookie value for a first touch. First-party, 90 days, SameSite=Lax, readable by nothing but our server. */
export function attributionCookieHeader(a: Attribution, secure: boolean): string {
  return [
    `${ATTRIBUTION_COOKIE}=${encodeAttribution(a)}`,
    "Path=/",
    `Max-Age=${ATTRIBUTION_MAX_AGE}`,
    "SameSite=Lax",
    "HttpOnly",
    ...(secure ? ["Secure"] : []),
  ].join("; ");
}

/**
 * Whether the proxy should capture attribution for this request: a top-level page GET (not an API call, a prefetch
 * or an asset), with no attribution cookie yet, and no Global Privacy Control signal.
 */
export function shouldCaptureAttribution(req: { method: string; pathname: string; headers: Headers; hasCookie: boolean }): boolean {
  if (req.hasCookie || req.method !== "GET") return false;
  if (req.pathname.startsWith("/api/") || req.pathname.startsWith("/_next/") || req.pathname.startsWith("/admin")) return false;
  const h = req.headers;
  if (h.get("sec-gpc") === "1") return false;
  if (h.get("next-router-prefetch") || h.get("purpose") === "prefetch" || h.get("sec-purpose")?.includes("prefetch")) return false;
  if (h.get("rsc")) return false;
  const dest = h.get("sec-fetch-dest");
  if (dest && dest !== "document") return false;
  return true;
}

/** Compact form for Paddle custom data (a string value, ≤ 400 chars). */
export function attributionForCheckout(a: Attribution | null): string | null {
  if (!a) return null;
  const { source, medium, campaign, ref, referrer, landing } = a;
  const s = JSON.stringify(sanitizeAttribution({ source, medium, campaign, ref, referrer, landing }) ?? {});
  return s !== "{}" && s.length <= 400 ? s : null;
}

/** Reads the compact form back from a webhook's custom data. */
export function attributionFromCheckout(value: unknown): Attribution | null {
  if (typeof value !== "string" || value.length > 400) return null;
  try {
    return sanitizeAttribution(JSON.parse(value));
  } catch {
    return null;
  }
}
