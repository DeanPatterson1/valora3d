import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Studio",
  description: "Plan a shot, preview your model and manage renders in the Valora3D studio.",
  robots: { index: false, follow: false },
};

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  return children;
}
