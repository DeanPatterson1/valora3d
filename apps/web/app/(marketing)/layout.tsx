import { Inter_Tight } from "next/font/google";

// Display face for landing headlines only; the app stays on Inter.
const display = Inter_Tight({
  variable: "--font-display-next",
  subsets: ["latin"],
  weight: ["700", "800"],
  display: "swap",
});

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return <div className={`${display.variable} min-h-dvh bg-bg-0 text-fg`}>{children}</div>;
}
