"use client";

import { useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Button, Field } from "@/components/ui";
import { DUR, EASE } from "@/lib/motion/tokens";
import { MIN_PASSWORD, isValidEmail } from "@/lib/services/local/auth";
import { Turnstile, turnstileSiteKey } from "./Turnstile";

const INPUT = "h-12 rounded-md px-4 text-base";

export type EmailPasswordFormProps = {
  mode: "login" | "signup";
  /** Resolves to an error message to show, or null on success (the caller navigates). */
  onSubmit: (values: { email: string; password: string; name: string; captchaToken?: string }) => Promise<string | null>;
  disabled?: boolean;
};

/**
 * Login: the email field alone, then the password field once the email is valid
 * (ChatGPT's two-step). Signup: name, email and password, validated inline.
 * Errors from the service land on the field they concern.
 */
export function EmailPasswordForm({ mode, onSubmit, disabled }: EmailPasswordFormProps) {
  const rm = useReducedMotion() ?? false;
  const login = mode === "login";
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [revealed, setRevealed] = useState(!login);
  const [errors, setErrors] = useState<{ name?: string; email?: string; password?: string; form?: string }>({});
  const [busy, setBusy] = useState(false);
  const [captchaToken, setCaptchaToken] = useState("");
  const [challengeAttempt, setChallengeAttempt] = useState(0);
  const passwordRef = useRef<HTMLInputElement>(null);

  // Once revealed, move focus to the new field when the user commits the email.
  const focusPassword = () => passwordRef.current?.focus();

  const validate = () => {
    const next: typeof errors = {};
    if (!login && !name.trim()) next.name = "Enter your name.";
    if (!isValidEmail(email)) next.email = "Enter a valid email address.";
    if (revealed && password.length < MIN_PASSWORD) next.password = `Use at least ${MIN_PASSWORD} characters.`;
    return next;
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    const next = validate();
    if (Object.keys(next).length > 0) {
      setErrors(next);
      return;
    }
    if (login && !revealed) {
      setRevealed(true);
      // Focus lands after the field mounts.
      requestAnimationFrame(focusPassword);
      return;
    }
    // Supabase refuses the request without a solved challenge once CAPTCHA protection is on.
    if (turnstileSiteKey && !captchaToken) {
      setErrors({ form: "Complete the security check and try again." });
      return;
    }
    setErrors({});
    setBusy(true);
    try {
      const message = await onSubmit({ email, password, name, ...(captchaToken ? { captchaToken } : {}) });
      if (message) setErrors({ form: message });
    } finally {
      // Tokens are single-use: every attempt, passed or failed, needs a fresh challenge.
      setCaptchaToken("");
      setChallengeAttempt((attempt) => attempt + 1);
      setBusy(false);
    }
  };

  const off = disabled || busy;

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-3">
      {!login && (
        <Field
          label="Name"
          name="name"
          autoComplete="name"
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={errors.name}
          disabled={off}
          inputClassName={INPUT}
        />
      )}
      <Field
        label="Email address"
        name="email"
        type="email"
        autoComplete="email"
        autoFocus={login}
        value={email}
        onChange={(e) => {
          const v = e.target.value;
          setEmail(v);
          // Login: the password field appears as soon as the email looks complete.
          if (login && !revealed && isValidEmail(v)) setRevealed(true);
          if (errors.email || errors.form) setErrors((s) => ({ ...s, email: undefined, form: undefined }));
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && login && revealed && password === "") {
            e.preventDefault();
            focusPassword();
          }
        }}
        error={errors.email ?? errors.form}
        disabled={off}
        inputClassName={INPUT}
      />
      <AnimatePresence initial={false}>
        {revealed && (
          <motion.div
            key="password"
            initial={rm ? false : { opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={rm ? undefined : { opacity: 0, height: 0 }}
            transition={{ duration: DUR.base, ease: EASE.standard }}
            className="overflow-hidden"
          >
            <Field
              ref={passwordRef}
              label="Password"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete={login ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (errors.password) setErrors((s) => ({ ...s, password: undefined }));
              }}
              error={errors.password}
              hint={login ? undefined : `At least ${MIN_PASSWORD} characters.`}
              disabled={off}
              inputClassName={INPUT}
              trailing={
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-pressed={showPassword}
                  className="h-8 cursor-pointer rounded-sm px-2 text-xs text-fg-muted transition-colors hover:text-fg focus-visible:focus-ring"
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              }
            />
          </motion.div>
        )}
      </AnimatePresence>
      <Turnstile key={challengeAttempt} action={mode} onToken={setCaptchaToken} />
      {/* Screen readers hear a new error the moment it lands. */}
      <p aria-live="polite" className="sr-only">
        {errors.form ?? errors.email ?? errors.password ?? errors.name ?? ""}
      </p>
      <Button type="submit" variant="primary" size="lg" loading={busy} disabled={disabled} className="h-12 w-full text-base">
        {login ? "Continue" : "Create account"}
      </Button>
    </form>
  );
}
