"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { services } from "@/lib/services";
import { useAuthStore } from "@/lib/stores/auth";
import { safeNextPath } from "@/lib/supabase/proxy";
import { AuthCard, OrDivider } from "./AuthCard";
import { EmailPasswordForm } from "./EmailPasswordForm";
import { ProviderButtons } from "./ProviderButtons";

/** Only same-origin paths are honoured, so `?next=` cannot send people off-site. */
export function safeNext(raw: string | null): string {
  return safeNextPath(raw);
}

/** Messages for `/login?error=` set by the auth callback routes. */
const LINK_ERRORS: Record<string, string> = {
  link_invalid: "That link is invalid or has expired. Sign in, or request a new link.",
};

export function LoginScreen() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const signIn = useAuthStore((s) => s.signIn);
  const signInWith = useAuthStore((s) => s.signInWith);
  const guest = useAuthStore((s) => s.guest);
  const features = services.auth.features;
  const [guestBusy, setGuestBusy] = useState(false);
  const [error, setError] = useState<string | null>(LINK_ERRORS[params.get("error") ?? ""] ?? null);

  const done = () => router.replace(next);
  const errorMessage = () => useAuthStore.getState().error?.message ?? "Could not sign in.";

  return (
    <AuthCard title="Welcome back" subtitle="Pick up where you left off in Valora3D." footer={{ text: "No account?", linkLabel: "Sign up", href: `/signup${params.get("next") ? `?next=${encodeURIComponent(next)}` : ""}` }}>
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
        <OrDivider />
        <ProviderButtons
          providers={features.providers}
          demo={services.backend === "local"}
          onChoose={async (provider) => {
            setError(null);
            if (await signInWith(provider)) done();
            else setError(errorMessage());
          }}
        />
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
