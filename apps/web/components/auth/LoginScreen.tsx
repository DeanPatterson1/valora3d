"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useAuthStore } from "@/lib/stores/auth";
import { AuthCard, OrDivider } from "./AuthCard";
import { EmailPasswordForm } from "./EmailPasswordForm";
import { ProviderButtons } from "./ProviderButtons";

/** Only same-origin paths are honoured, so `?next=` cannot send people off-site. */
export function safeNext(raw: string | null): string {
  return raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/projects";
}

export function LoginScreen() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const signIn = useAuthStore((s) => s.signIn);
  const signInWith = useAuthStore((s) => s.signInWith);
  const guest = useAuthStore((s) => s.guest);
  const [guestBusy, setGuestBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const done = () => router.replace(next);
  const errorMessage = () => useAuthStore.getState().error?.message ?? "Could not sign in.";

  return (
    <AuthCard title="Welcome back" subtitle="Pick up where you left off in Valora3D." footer={{ text: "No account?", linkLabel: "Sign up", href: `/signup${params.get("next") ? `?next=${encodeURIComponent(next)}` : ""}` }}>
      <div className="flex flex-col gap-5">
        <EmailPasswordForm
          mode="login"
          onSubmit={async ({ email, password }) => {
            if (await signIn(email, password)) {
              done();
              return null;
            }
            return errorMessage();
          }}
        />
        <OrDivider />
        <ProviderButtons
          onChoose={async (provider) => {
            setError(null);
            if (await signInWith(provider)) done();
            else setError(errorMessage());
          }}
        />
        <button
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
        </button>
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      </div>
    </AuthCard>
  );
}
