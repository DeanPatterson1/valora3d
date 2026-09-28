"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { services } from "@/lib/services";
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
  const [sentTo, setSentTo] = useState<string | null>(null);

  const done = () => router.replace(next);

  if (sentTo) {
    return (
      <AuthCard title="Check your email" subtitle={sentTo} footer={{ text: "Already confirmed?", linkLabel: "Log in", href: "/login" }}>
        <p className="text-sm text-fg-muted">The link expires after a day. If it doesn&apos;t arrive, check spam or sign up again with the same email.</p>
      </AuthCard>
    );
  }

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
            const err = useAuthStore.getState().error;
            if (err?.code === "verification_sent") {
              setSentTo(err.message);
              return null;
            }
            return err?.message ?? "Could not create the account.";
          }}
        />
        <OrDivider />
        <ProviderButtons
          providers={services.auth.features.providers}
          demo={services.backend === "local"}
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
