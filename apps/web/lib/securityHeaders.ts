/**
 * The site's security headers, in ONE place: next.config.ts `headers()` sends them on every route, and proxy.ts
 * puts them on the responses it generates itself (the 410 share page, the admin 403 / 404 rewrites, the dev 404
 * rewrite), which next.config's headers do not reach. Keep this file free of `@/` imports: next.config.ts loads it.
 */

const supabase = "https://*.supabase.co wss://*.supabase.co";
// Paddle.js v2 loads from cdn.paddle.com, opens its overlay checkout in an iframe on
// buy.paddle.com / sandbox-buy.paddle.com and calls *.paddle.com APIs; the wildcard covers all of
// them (script, connect, img, frame). lib/billing/csp.test.ts pins what checkout needs.
const paddle = "https://*.paddle.com https://cdn.paddle.com";
const turnstile = "https://challenges.cloudflare.com";
const r2 = "https://*.r2.cloudflarestorage.com";

/** The Content-Security-Policy. eval and localhost sockets are dev-only. */
export function contentSecurityPolicy(isDev = process.env.NODE_ENV !== "production"): string {
  // Static App Router pages use inline hydration scripts; Motion and three.js use inline
  // styles. Keep those allowances explicit.
  return [
    "default-src 'self'",
    `script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval' ${isDev ? "'unsafe-eval'" : ""} ${paddle} ${turnstile} https://static.cloudflareinsights.com`,
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
  ].join("; ");
}

export function securityHeaders(isDev?: boolean): { key: string; value: string }[] {
  return [
    { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Content-Security-Policy", value: contentSecurityPolicy(isDev) },
  ];
}

/** Sets every security header on a response (a Response built with `new Response` has mutable headers). */
export function withSecurityHeaders<T extends Response>(response: T): T {
  for (const { key, value } of securityHeaders()) response.headers.set(key, value);
  return response;
}
