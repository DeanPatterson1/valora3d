"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Field } from "@/components/ui";
import { services } from "@/lib/services";
import { MIN_PASSWORD, isValidEmail } from "@/lib/services/local/auth";
import { AuthCard } from "./AuthCard";

const INPUT = "h-12 rounded-md px-4 text-base";

/** /forgot-password: asks for the email and always answers the same way (no account probing). */
export function ForgotPasswordScreen() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  if (!services.auth.features.passwordReset) {
    return (
      <AuthCard title="Reset password" footer={{ text: "Remembered it?", linkLabel: "Log in", href: "/login" }}>
        <p className="text-sm text-fg-muted">Password reset isn&apos;t available in this prototype.</p>
      </AuthCard>
    );
  }

  if (sent) {
    return (
      <AuthCard title="Check your email" footer={{ text: "Remembered it?", linkLabel: "Log in", href: "/login" }}>
        <p className="text-sm text-fg-muted">
          If an account uses {email.trim()}, a link to set a new password is on its way. It expires after an hour.
        </p>
      </AuthCard>
    );
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValidEmail(email)) {
      setError("Enter a valid email address.");
      return;
    }
    setBusy(true);
    setError(null);
    const r = await services.auth.requestPasswordReset(email);
    setBusy(false);
    if (r.ok) setSent(true);
    else setError(r.error.message);
  };

  return (
    <AuthCard title="Reset password" subtitle="We'll email you a link to set a new one." footer={{ text: "Remembered it?", linkLabel: "Log in", href: "/login" }}>
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <Field
          label="Email address"
          name="email"
          type="email"
          autoComplete="email"
          autoFocus
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (error) setError(null);
          }}
          error={error ?? undefined}
          disabled={busy}
          inputClassName={INPUT}
        />
        <Button type="submit" variant="primary" size="lg" loading={busy} className="h-12 w-full text-base">
          Send reset link
        </Button>
      </form>
    </AuthCard>
  );
}

/** /reset-password: reached from the emailed link (the callback route has opened a session). */
export function ResetPasswordScreen() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < MIN_PASSWORD) {
      setError(`Use at least ${MIN_PASSWORD} characters.`);
      return;
    }
    setBusy(true);
    setError(null);
    const r = await services.auth.updatePassword(password);
    setBusy(false);
    if (r.ok) router.replace("/projects");
    else setError(r.error.message);
  };

  return (
    <AuthCard title="Set a new password" footer={{ text: "Link expired?", linkLabel: "Send a new one", href: "/forgot-password" }}>
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <Field
          label="New password"
          name="password"
          type="password"
          autoComplete="new-password"
          autoFocus
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            if (error) setError(null);
          }}
          error={error ?? undefined}
          hint={`At least ${MIN_PASSWORD} characters.`}
          disabled={busy}
          inputClassName={INPUT}
        />
        <Button type="submit" variant="primary" size="lg" loading={busy} className="h-12 w-full text-base">
          Save password
        </Button>
      </form>
    </AuthCard>
  );
}
