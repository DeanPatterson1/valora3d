import type { Metadata } from "next";
import { MotionConfig } from "motion/react";
import {
  Bricolage_Grotesque,
  IBM_Plex_Mono,
  Instrument_Sans,
} from "next/font/google";
import { BRAND } from "@/lib/brand";
import { Header } from "@/components/layout/Header";
import { Toaster } from "@/components/ui/Toast";
import "./globals.css";

const display = Bricolage_Grotesque({
  variable: "--font-display-next",
  subsets: ["latin"],
  axes: ["opsz", "wdth"],
  display: "swap",
});

const sans = Instrument_Sans({
  variable: "--font-sans-next",
  subsets: ["latin"],
  display: "swap",
});

const mono = IBM_Plex_Mono({
  variable: "--font-mono-next",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: BRAND.name,
  description: BRAND.tagline,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${display.variable} ${sans.variable} ${mono.variable} h-full`}
    >
      <body className="flex min-h-full flex-col">
        <MotionConfig reducedMotion="user">
          <Header />
          <main className="flex flex-1 flex-col">{children}</main>
          <Toaster />
        </MotionConfig>
      </body>
    </html>
  );
}
