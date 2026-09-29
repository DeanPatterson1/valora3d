import Script from "next/script";
import type { Metadata } from "next";
import { MotionConfig } from "motion/react";
import { Inter } from "next/font/google";
import { BRAND } from "@/lib/brand";
import { SITE_URL } from "@/lib/site";
import { Toaster } from "@/components/ui/Toast";
import { Analytics } from "@/components/analytics/Analytics";
import { ErrorReporter } from "@/components/analytics/ErrorReporter";
import "./globals.css";

const inter = Inter({
  variable: "--font-text-next",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: BRAND.name,
  description: "Upload a .glb model, describe your shot and create cinematic renders and videos with Valora3D.",
  applicationName: BRAND.name,
  openGraph: { siteName: BRAND.name, type: "website", locale: "en_US" },
  twitter: { card: "summary_large_image" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} h-full`}>
      <body className="h-full">
        <MotionConfig reducedMotion="user">
          {children}
          <Toaster />
          {/* First-party, cookieless product events (lib/analytics/track.ts). */}
          <Analytics />
          <ErrorReporter />
          {process.env.NEXT_PUBLIC_CF_ANALYTICS_TOKEN?.trim() && (
            <Script
              id="cloudflare-web-analytics"
              src="https://static.cloudflareinsights.com/beacon.min.js"
              strategy="afterInteractive"
              data-cf-beacon={JSON.stringify({ token: process.env.NEXT_PUBLIC_CF_ANALYTICS_TOKEN.trim() })}
            />
          )}
        </MotionConfig>
      </body>
    </html>
  );
}
