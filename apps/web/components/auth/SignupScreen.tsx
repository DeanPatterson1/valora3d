"use client";

import { useRouter, useSearchParams } from "next/navigation";
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

  const done = () => router.replace(next);

  return (
    <AuthCard
      title="Create your account"
      subtitle="Projects, scenes and credits stay in this browser."
      footer={{ text: "Already have an account?", linkLabel: "Log in", href: `/login${params.get("next") ? `?next=${encodeURIComponent(next)}` : ""}` }}
    >
      <div className="flex flex-col gap-5">
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
            if (await signInWith(provider)) done();
          }}
        />
      </div>
    </AuthCard>
  );
}
