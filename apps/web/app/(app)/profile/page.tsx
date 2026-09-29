import type { Metadata } from "next";
import { ProfileScreen } from "@/components/account/ProfileScreen";

export const metadata: Metadata = { title: "Profile", description: "Manage your Valora3D profile and account details.", robots: { index: false, follow: false } };

/** `?tab=billing` opens "Usage & billing" directly. */
export default async function ProfilePage({ searchParams }: { searchParams: Promise<{ tab?: string | string[] }> }) {
  const { tab } = await searchParams;
  return <ProfileScreen initialTab={tab === "billing" ? "billing" : "overview"} />;
}
