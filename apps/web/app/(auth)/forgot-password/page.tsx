import type { Metadata } from "next";
import { ForgotPasswordScreen } from "@/components/auth/PasswordResetScreens";

export const metadata: Metadata = { title: "Reset password", robots: { index: false } };

export default function ForgotPasswordPage() {
  return <ForgotPasswordScreen />;
}
