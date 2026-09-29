import { Suspense } from "react";
import type { Metadata } from "next";
import { SignupScreen } from "@/components/auth/SignupScreen";

export const metadata: Metadata = { title: "Sign up" };

export default function SignupPage() {
  return (
    <Suspense fallback={null}>
      <SignupScreen />
    </Suspense>
  );
}
