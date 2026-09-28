import type { Metadata } from "next";
import { BRAND } from "@/lib/brand";
import { ResetPasswordScreen } from "@/components/auth/PasswordResetScreens";

export const metadata: Metadata = { title: `Set a new password · ${BRAND.name}`, robots: { index: false } };

export default function ResetPasswordPage() {
  return <ResetPasswordScreen />;
}
