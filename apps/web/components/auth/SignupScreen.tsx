"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { AUTH_FEATURES, BACKEND } from "@/lib/services/backend";
import { loginHref, nextFromParams } from "@/lib/nav/next";
import { FREE_PLAN_CREDITS, creditValue } from "@/lib/pricing";
import { useAuthStore } from "@/lib/stores/auth";
import { AuthCard, OrDivider, useSignedInRedirect } from "./AuthCard";
import { EmailPasswordForm } from "./EmailPasswordForm";
import { ProviderButtons } from "./ProviderButtons";

/** The offer, restated where the decision is made. Derived from the pricing constants, never hand-typed. */
export const SIGNUP_OFFER = `Start free with ${FREE_PLAN_CREDITS} credits, enough for ${creditValue(FREE_PLAN_CREDITS, "free")}. No card needed.`;

export function SignupScreen() {
  const router = useRouter();
  const params = useSearchParams();
  // `?next=`, or a plan/pack picked on /pricing: after signup (and after the emailed link) it lands there.
  const next = nextFromParams(params);
  const signUp = useAuthStore((s) => s.signUp);
  const signInWith = useAuthStore((s) => s.signInWith);
  const [error, setError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  useSignedInRedirect(next);

  const done = () => router.replace(next);

  if (sentTo) {
    return (
      <AuthCard title="Check your email" subtitle={sentTo} footer={{ text: "Already confirmed?", linkLabel: "Log in", href: loginHref(next) }}>
        <p className="text-sm text-fg-muted">The link expires after a day. If it doesn&apos;t arrive, check spam or sign up again with the same email.</p>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Create your account"
      subtitle={SIGNUP_OFFER}
      footer={{ text: "Already have an account?", linkLabel: "Log in", href: loginHref(next) }}
    >
      <div className="flex flex-col gap-4">
        <EmailPasswordForm
          mode="signup"
          onSubmit={async ({ email, password, name, captchaToken }) => {
            if (await signUp(email, password, name, captchaToken, next)) {
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
          providers={AUTH_FEATURES.providers}
          demo={BACKEND === "local"}
          onChoose={async (provider) => {
            setError(null);
            if (await signInWith(provider, next)) done();
            else setError(useAuthStore.getState().error?.message ?? "Could not sign in.");
          }}
        />
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        <p className="text-center text-xs leading-relaxed text-fg-muted">
          By creating an account you agree to the{" "}
          <Link href="/terms" className="rounded-sm underline underline-offset-4 hover:text-fg focus-visible:focus-ring">Terms</Link> and{" "}
          <Link href="/privacy" className="rounded-sm underline underline-offset-4 hover:text-fg focus-visible:focus-ring">Privacy notice</Link>.
        </p>
      </div>
    </AuthCard>
  );
}
