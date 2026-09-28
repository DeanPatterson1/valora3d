import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";
const supabase = "https://*.supabase.co wss://*.supabase.co";
const paddle = "https://*.paddle.com https://cdn.paddle.com";
const turnstile = "https://challenges.cloudflare.com";
const r2 = "https://*.r2.cloudflarestorage.com";

// Static App Router pages use inline hydration scripts; Motion and three.js use inline
// styles. Keep those allowances explicit. eval and localhost sockets are dev-only.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval' ${isDev ? "'unsafe-eval'" : ""} ${paddle} ${turnstile}`,
  "style-src 'self' 'unsafe-inline'",
  `img-src 'self' blob: data: https://*.supabase.co ${paddle} ${r2}`,
  "font-src 'self' data:",
  `connect-src 'self' blob: data: ${supabase} ${paddle} ${turnstile} ${r2} ${isDev ? "ws://localhost:* ws://127.0.0.1:*" : ""}`,
  `media-src 'self' blob: data: https://*.supabase.co ${r2}`,
  `frame-src ${paddle} ${turnstile}`,
  "worker-src 'self' blob:",
  "manifest-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const nextConfig: NextConfig = {
  // Keep the dev badge off the sidebar (bottom-left), the studio's top-left status and its
  // top-right details button; the composer is centred, so the bottom-right corner is free.
  devIndicators: { position: "bottom-right" },
  headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Content-Security-Policy", value: csp },
      ],
    }];
  },
};

export default nextConfig;
