"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { BACKEND, GUEST_ID } from "@/lib/services/backend";
import { useAuthStore } from "@/lib/stores/auth";

export type AuthCardProps = {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  /** Switch line under the card: "No account? Sign up". */
  footer?: { text: string; linkLabel: string; href: string };
};

/**
 * A compact auth panel using the site's neutral surfaces and white actions.
 */
export function AuthCard({ title, subtitle, children, footer }: AuthCardProps) {
  return (
    <div className="flex w-full max-w-[28rem] flex-col items-stretch gap-5 rounded-[24px] border border-line bg-bg-1 p-5 sm:p-7">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-[-0.04em] text-fg">{title}</h1>
        {subtitle && <p className="text-sm text-fg-muted">{subtitle}</p>}
      </div>
      {BACKEND === "local" && (
        <p className="border-l-2 border-fg-muted/40 pl-3 text-xs leading-relaxed text-fg-muted">
          Prototype: accounts live in this browser only. No email is sent and passwords are not stored.
        </p>
      )}
      {children}
      {footer && (
        <p className="text-center text-sm text-fg-muted">
          {footer.text}{" "}
          <Link href={footer.href} className="rounded-sm text-fg underline underline-offset-4 focus-visible:focus-ring">
            {footer.linkLabel}
          </Link>
        </p>
      )}
    </div>
  );
}

/** The "OR" rule between the email form and the provider buttons. */
export function OrDivider() {
  return (
    <div className="flex items-center gap-3" aria-hidden>
      <span className="h-px flex-1 bg-line" />
      <span className="text-xs text-fg-muted">OR</span>
      <span className="h-px flex-1 bg-line" />
    </div>
  );
}

/**
 * Someone already signed in who opens /login or /signup goes straight on to `next`. With Supabase the proxy does
 * this before the page renders; in Local mode the session lives in this browser, so the page checks once.
 */
export function useSignedInRedirect(next: string) {
  const router = useRouter();
  useEffect(() => {
    let live = true;
    void useAuthStore.getState().refresh().then(() => {
      const user = useAuthStore.getState().user;
      // A Local guest is here to create a real account, so the form stays.
      if (live && user && user.id !== GUEST_ID) router.replace(next);
    });
    return () => {
      live = false;
    };
    // Once per visit: a sign-in on this page navigates by itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
