import type { NextConfig } from "next";
import { securityHeaders } from "./lib/securityHeaders";

const nextConfig: NextConfig = {
  // Keep the dev badge off the sidebar (bottom-left), the studio's top-left status and its
  // top-right details button; the composer is centred, so the bottom-right corner is free.
  devIndicators: { position: "bottom-right" },
  headers() {
    // The list lives in lib/securityHeaders.ts so proxy.ts sends the same headers on its own responses.
    return [{ source: "/:path*", headers: securityHeaders() }];
  },
};

export default nextConfig;
