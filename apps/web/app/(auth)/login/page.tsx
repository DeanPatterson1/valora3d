import { Suspense } from "react";
import type { Metadata } from "next";
import { BRAND } from "@/lib/brand";
import { LoginScreen } from "@/components/auth/LoginScreen";

export const metadata: Metadata = { title: `Log in · ${BRAND.name}` };

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginScreen />
    </Suspense>
  );
}
