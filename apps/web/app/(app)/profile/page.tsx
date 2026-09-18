import type { Metadata } from "next";
import { BRAND } from "@/lib/brand";
import { ProfileScreen } from "@/components/account/ProfileScreen";

export const metadata: Metadata = { title: `Profile · ${BRAND.name}` };

export default function ProfilePage() {
  return <ProfileScreen />;
}
