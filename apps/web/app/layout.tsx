import Script from "next/script";
import { connection } from "next/server";
import type { Metadata } from "next";
import { MotionConfig } from "motion/react";
import { Inter } from "next/font/google";
import { BRAND } from "@/lib/brand";
import { HOME_DESCRIPTION, HOME_TITLE, SITE_URL, TITLE_TEMPLATE } from "@/lib/site";
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
  title: { default: HOME_TITLE, template: TITLE_TEMPLATE },
  description: HOME_DESCRIPTION,
  applicationName: BRAND.name,
  openGraph: { siteName: BRAND.name, type: "website", locale: "en_US" },
  twitter: { card: "summary_large_image" },
};

/**
 * Every page renders per request. The proxy mints a CSP nonce for each request (lib/securityHeaders.ts) and Next
 * stamps it on the inline hydration scripts while rendering; a prerendered page has no request, so its inline
 * scripts would carry no nonce and the browser would block them. README "Content-Security-Policy" has the cost.
 */
export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await connection();
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
