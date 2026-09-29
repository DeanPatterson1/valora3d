import { Suspense } from "react";
import type { Metadata } from "next";
import { LoginScreen } from "@/components/auth/LoginScreen";

export const metadata: Metadata = { title: "Log in" };

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginScreen />
    </Suspense>
  );
}
