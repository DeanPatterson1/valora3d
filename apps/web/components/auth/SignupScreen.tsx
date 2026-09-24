"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useAuthStore } from "@/lib/stores/auth";
import { AuthCard, OrDivider } from "./AuthCard";
import { EmailPasswordForm } from "./EmailPasswordForm";
import { safeNext } from "./LoginScreen";
import { ProviderButtons } from "./ProviderButtons";

export function SignupScreen() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const signUp = useAuthStore((s) => s.signUp);
  const signInWith = useAuthStore((s) => s.signInWith);
  const [error, setError] = useState<string | null>(null);

  const done = () => router.replace(next);

  return (
    <AuthCard
      title="Create your account"
      subtitle="Your workspace for models, scenes and ideas."
      footer={{ text: "Already have an account?", linkLabel: "Log in", href: `/login${params.get("next") ? `?next=${encodeURIComponent(next)}` : ""}` }}
    >
      <div className="flex flex-col gap-4">
        <EmailPasswordForm
          mode="signup"
          onSubmit={async ({ email, password, name }) => {
            if (await signUp(email, password, name)) {
              done();
              return null;
            }
            return useAuthStore.getState().error?.message ?? "Could not create the account.";
          }}
        />
        <OrDivider />
        <ProviderButtons
          onChoose={async (provider) => {
            setError(null);
            if (await signInWith(provider)) done();
            else setError(useAuthStore.getState().error?.message ?? "Could not sign in.");
          }}
        />
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      </div>
    </AuthCard>
  );
}
