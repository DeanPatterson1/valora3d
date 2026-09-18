import { Suspense } from "react";
import type { Metadata } from "next";
import { BRAND } from "@/lib/brand";
import { SignupScreen } from "@/components/auth/SignupScreen";

export const metadata: Metadata = { title: `Sign up · ${BRAND.name}` };

export default function SignupPage() {
  return (
    <Suspense fallback={null}>
      <SignupScreen />
    </Suspense>
  );
}
