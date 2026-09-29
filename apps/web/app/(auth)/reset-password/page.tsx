import type { Metadata } from "next";
import { ResetPasswordScreen } from "@/components/auth/PasswordResetScreens";

export const metadata: Metadata = { title: "Set a new password", robots: { index: false } };

export default function ResetPasswordPage() {
  return <ResetPasswordScreen />;
}
