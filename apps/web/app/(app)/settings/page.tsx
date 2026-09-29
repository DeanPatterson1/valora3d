import type { Metadata } from "next";
import { BRAND } from "@/lib/brand";
import { SettingsScreen } from "@/components/settings/SettingsScreen";

export const metadata: Metadata = { title: `Settings · ${BRAND.name}`, description: "Choose your Valora3D rendering and appearance preferences.", robots: { index: false, follow: false } };

// Mirrors SECTIONS in SettingsScreen (a client module, so its values cannot be imported here).
const SECTIONS = ["general", "rendering", "notifications", "local", "data", "account"] as const;
type Section = (typeof SECTIONS)[number];

/** `?section=notifications` opens that section (the render-ready mail links here to turn it off). */
export default async function SettingsPage({ searchParams }: { searchParams: Promise<{ section?: string | string[] }> }) {
  const { section } = await searchParams;
  const initial = SECTIONS.find((s) => s === section) as Section | undefined;
  return <SettingsScreen initialSection={initial ?? "general"} />;
}
