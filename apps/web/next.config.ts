import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep the dev badge off the sidebar (bottom-left), the studio's top-left status and its
  // top-right details button; the composer is centred, so the bottom-right corner is free.
  devIndicators: { position: "bottom-right" },
};

export default nextConfig;
