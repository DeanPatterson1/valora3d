import { execSync } from "node:child_process";
import type { NextConfig } from "next";
import { securityHeaders } from "./lib/securityHeaders";

/**
 * The build id client error reports and server error logs carry (lib/errors/shared.ts, lib/server/log.ts): the env
 * value when CI sets one, else the git short hash, else "dev". Read once at build time and inlined.
 */
function releaseId(): string {
  const fromEnv = process.env.NEXT_PUBLIC_RELEASE_ID?.trim();
  if (fromEnv && /^[A-Za-z0-9._-]{1,40}$/.test(fromEnv)) return fromEnv;
  try {
    const hash = execSync("git rev-parse --short=12 HEAD", { stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
    return /^[0-9a-f]{7,40}$/.test(hash) ? hash : "dev";
  } catch {
    return "dev";
  }
}

const nextConfig: NextConfig = {
  env: { NEXT_PUBLIC_RELEASE_ID: releaseId() },
  // Keep the dev badge off the sidebar (bottom-left), the studio's top-left status and its
  // top-right details button; the composer is centred, so the bottom-right corner is free.
  devIndicators: { position: "bottom-right" },
  headers() {
    // The list lives in lib/securityHeaders.ts so proxy.ts sends the same headers on its own responses.
    return [{ source: "/:path*", headers: securityHeaders() }];
  },
};

export default nextConfig;
