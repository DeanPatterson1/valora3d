import type { Metadata } from "next";
import { BRAND } from "@/lib/brand";
import { SettingsScreen } from "@/components/settings/SettingsScreen";

export const metadata: Metadata = { title: `Settings · ${BRAND.name}` };

export default function SettingsPage() {
  return <SettingsScreen />;
}
