/**
 * The site's security headers, in ONE place: next.config.ts `headers()` sends them on every route, and proxy.ts
 * puts them (plus the per-request nonce CSP) on every response it generates or forwards. Keep this file free of `@/` imports: next.config.ts loads it.
 */

const supabase = "https://*.supabase.co wss://*.supabase.co";
// Paddle.js v2 loads from cdn.paddle.com, opens its overlay checkout in an iframe on
// buy.paddle.com / sandbox-buy.paddle.com and calls *.paddle.com APIs; the wildcard covers all of
// them (script, connect, img, frame). lib/billing/csp.test.ts pins what checkout needs.
const paddle = "https://*.paddle.com https://cdn.paddle.com";
const turnstile = "https://challenges.cloudflare.com";
/** Dev / unset fallback: any R2 account. Production sets R2_ACCOUNT_ID, which narrows it to our own endpoint. */
export const R2_WILDCARD = "https://*.r2.cloudflarestorage.com";

/**
 * The R2 S3 endpoint the browser talks to (presigned PUT uploads, video and poster redirects), built from
 * R2_ACCOUNT_ID at request time. A Cloudflare account id is 32 hex characters; anything else (unset, a typo, a
 * value that could smuggle a second source into the header) falls back to the wildcard, which is what dev uses.
 */
export function r2Origin(accountId: string | undefined = process.env.R2_ACCOUNT_ID): string {
  const id = accountId?.trim().toLowerCase();
  return id && /^[a-f0-9]{32}$/.test(id) ? `https://${id}.r2.cloudflarestorage.com` : R2_WILDCARD;
}

/** A fresh per-request nonce: 128 random bits, base64. Edge-safe (no Buffer). */
export function newNonce(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}

export type CspOptions = {
  /** The request's nonce (newNonce()). It authorises Next's own inline scripts; `'strict-dynamic'` lets those load the rest. */
  nonce: string;
  /** eval and localhost sockets are dev-only. */
  isDev?: boolean;
  /** Override for tests; defaults to process.env.R2_ACCOUNT_ID. */
  r2AccountId?: string;
};

/**
 * The Content-Security-Policy, built per request by proxy.ts.
 *
 * script-src: no 'unsafe-inline'. Next stamps the nonce (read from the request's CSP header) on every inline script
 * and framework chunk it renders, and 'strict-dynamic' extends that trust to scripts those create (Paddle.js,
 * Turnstile and the Cloudflare beacon are injected at runtime). Where 'strict-dynamic' is supported the host list
 * is ignored; it stays as the fallback for older browsers.
 *
 * style-src keeps 'unsafe-inline' on purpose: Motion, three.js canvases and React `style={{}}` props write inline
 * style attributes, which a nonce cannot cover, and a nonce in the same directive would switch 'unsafe-inline' off.
 * The risk left is CSS injection, which cannot run script.
 */
export function contentSecurityPolicy({ nonce, isDev = process.env.NODE_ENV !== "production", r2AccountId }: CspOptions): string {
  const r2 = r2Origin(r2AccountId ?? process.env.R2_ACCOUNT_ID);
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic' 'wasm-unsafe-eval' ${isDev ? "'unsafe-eval'" : ""} ${paddle} ${turnstile} https://static.cloudflareinsights.com`,
    "style-src 'self' 'unsafe-inline'",
    `img-src 'self' blob: data: https://*.supabase.co ${paddle} ${r2}`,
    "font-src 'self' data:",
    `connect-src 'self' blob: data: ${supabase} ${paddle} ${turnstile} ${r2} https://cloudflareinsights.com ${isDev ? "ws://localhost:* ws://127.0.0.1:*" : ""}`,
    `media-src 'self' blob: data: https://*.supabase.co ${r2}`,
    `frame-src ${paddle} ${turnstile}`,
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ").replace(/\s{2,}/g, " ");
}

/** The headers that do not vary per request. The CSP does (nonce), so proxy.ts adds it. */
export function securityHeaders(): { key: string; value: string }[] {
  return [
    { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    { key: "X-Frame-Options", value: "DENY" },
  ];
}

/** Sets every security header, and the given per-request CSP, on a response (a Response built with `new Response` has mutable headers). */
export function withSecurityHeaders<T extends Response>(response: T, csp: string): T {
  for (const { key, value } of securityHeaders()) response.headers.set(key, value);
  response.headers.set("Content-Security-Policy", csp);
  return response;
}
