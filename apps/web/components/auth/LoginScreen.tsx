"use client";

import { useRouter, useSearchParams } from "next/navigation";
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

  const done = () => router.replace(next);
  const errorMessage = () => useAuthStore.getState().error?.message ?? "Could not sign in.";

  return (
    <AuthCard title="Welcome back" footer={{ text: "No account?", linkLabel: "Sign up", href: `/signup${params.get("next") ? `?next=${encodeURIComponent(next)}` : ""}` }}>
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
            if (await signInWith(provider)) done();
          }}
        />
        <button
          type="button"
          onClick={() => void guest().then((ok) => ok && done())}
          className="mx-auto cursor-pointer rounded-sm text-sm text-fg-muted underline-offset-4 transition-colors hover:text-fg hover:underline focus-visible:focus-ring"
        >
          Continue as guest
        </button>
      </div>
    </AuthCard>
  );
}
