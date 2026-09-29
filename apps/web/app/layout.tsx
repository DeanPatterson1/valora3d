import Script from "next/script";
import type { Metadata } from "next";
import { MotionConfig } from "motion/react";
import { Inter } from "next/font/google";
import { BRAND } from "@/lib/brand";
import { HOME_DESCRIPTION, HOME_TITLE, SITE_URL, TITLE_TEMPLATE } from "@/lib/site";
import { Toaster } from "@/components/ui/Toast";
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
