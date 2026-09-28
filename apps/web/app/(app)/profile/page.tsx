import type { Metadata } from "next";
import { BRAND } from "@/lib/brand";
import { ProfileScreen } from "@/components/account/ProfileScreen";

export const metadata: Metadata = { title: `Profile · ${BRAND.name}`, description: "Manage your Valora3D profile and account details.", robots: { index: false, follow: false } };

export default function ProfilePage() {
  return <ProfileScreen />;
}
