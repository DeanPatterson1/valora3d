import type { Metadata } from "next";
import { BRAND } from "@/lib/brand";
import { ForgotPasswordScreen } from "@/components/auth/PasswordResetScreens";

export const metadata: Metadata = { title: `Reset password · ${BRAND.name}`, robots: { index: false } };

export default function ForgotPasswordPage() {
  return <ForgotPasswordScreen />;
}
