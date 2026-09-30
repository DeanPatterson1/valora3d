"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { AUTH_FEATURES, BACKEND } from "@/lib/services/backend";
import { nextFromParams, signupHref } from "@/lib/nav/next";
import { useAuthStore } from "@/lib/stores/auth";
import { AuthCard, OrDivider, useSignedInRedirect } from "./AuthCard";
import { EmailPasswordForm } from "./EmailPasswordForm";
import { ProviderButtons } from "./ProviderButtons";

/** Messages for `/login?error=` set by the auth callback routes. */
const LINK_ERRORS: Record<string, string> = {
  link_invalid: "That link is invalid or has expired. Sign in, or request a new link.",
};

export function LoginScreen() {
  const router = useRouter();
  const params = useSearchParams();
  const next = nextFromParams(params);
  const signIn = useAuthStore((s) => s.signIn);
  const signInWith = useAuthStore((s) => s.signInWith);
  const guest = useAuthStore((s) => s.guest);
  const features = AUTH_FEATURES;
  const [guestBusy, setGuestBusy] = useState(false);
  const [error, setError] = useState<string | null>(LINK_ERRORS[params.get("error") ?? ""] ?? null);

  useSignedInRedirect(next);

  const done = () => router.replace(next);
  const errorMessage = () => useAuthStore.getState().error?.message ?? "Could not sign in.";

  return (
    <AuthCard title="Welcome back" subtitle="Pick up where you left off in Valora3D." footer={{ text: "New to Valora3D?", linkLabel: "Create an account", href: signupHref(next) }}>
      <div className="flex flex-col gap-5">
        <EmailPasswordForm
          mode="login"
          onSubmit={async ({ email, password, captchaToken }) => {
            if (await signIn(email, password, captchaToken)) {
              done();
              return null;
            }
            return errorMessage();
          }}
        />
        {features.passwordReset && (
          <Link href="/forgot-password" className="-mt-2 self-end rounded-sm text-sm text-fg-muted underline-offset-4 hover:text-fg hover:underline focus-visible:focus-ring">
            Forgot password?
          </Link>
        )}
        {features.providers.length > 0 && (
          <>
            <OrDivider />
            <ProviderButtons
              providers={features.providers}
              demo={BACKEND === "local"}
              onChoose={async (provider) => {
                setError(null);
                if (await signInWith(provider, next)) done();
                else setError(errorMessage());
              }}
            />
          </>
        )}
        {features.guest && <button
          type="button"
          disabled={guestBusy}
          onClick={async () => {
            setGuestBusy(true);
            setError(null);
            try {
              if (await guest()) done();
              else setError(errorMessage());
            } finally { setGuestBusy(false); }
          }}
          className="min-h-11 cursor-pointer rounded-full text-sm text-fg-muted transition-colors hover:bg-bg-2 hover:text-fg focus-visible:focus-ring disabled:opacity-50"
        >
          Continue as guest
        </button>}
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      </div>
    </AuthCard>
  );
}
