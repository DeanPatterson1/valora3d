import type { Metadata } from "next";
import { BRAND } from "@/lib/brand";
import { SettingsScreen } from "@/components/settings/SettingsScreen";

export const metadata: Metadata = { title: `Settings · ${BRAND.name}`, description: "Choose your Valora3D rendering and appearance preferences.", robots: { index: false, follow: false } };

export default function SettingsPage() {
  return <SettingsScreen />;
}
