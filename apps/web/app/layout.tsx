import type { Metadata } from "next";
import { MotionConfig } from "motion/react";
import { Inter } from "next/font/google";
import { BRAND } from "@/lib/brand";
import { Toaster } from "@/components/ui/Toast";
import "./globals.css";

const inter = Inter({
  variable: "--font-text-next",
  subsets: ["latin"],
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
    <html lang="en" className={`${inter.variable} h-full`}>
      <body className="h-full">
        <MotionConfig reducedMotion="user">
          {children}
          <Toaster />
        </MotionConfig>
      </body>
    </html>
  );
}
