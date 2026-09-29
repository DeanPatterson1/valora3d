import type { Metadata } from "next";
import Link from "next/link";
import { BRAND } from "@/lib/brand";

export const metadata: Metadata = { title: `Sign-ups paused · ${BRAND.name}`, robots: { index: false, follow: false } };

/**
 * Shown in place of /signup while the `signups_enabled` kill switch is off (proxy.ts rewrites to it, so the address
 * stays /signup). Existing accounts can still log in.
 */
export default function SignupsPausedPage() {
  return (
    <div className="mx-auto flex max-w-[480px] flex-col items-center gap-4 px-5 py-24 text-center">
      <h1 className="text-2xl font-semibold tracking-tight text-fg">New sign-ups are paused</h1>
      <p className="text-fg-muted">
        We&apos;re not taking new accounts for a little while. Please check back soon. If you already have an account, you can
        still log in.
      </p>
      <div className="mt-2 flex flex-wrap justify-center gap-3">
        <Link href="/login" className="inline-flex h-10 items-center rounded-full bg-primary px-5 text-sm font-medium text-primary-fg focus-visible:focus-ring">
          Log in
        </Link>
        <Link href="/" className="inline-flex h-10 items-center rounded-full border border-line px-5 text-sm font-medium text-fg hover:bg-bg-3 focus-visible:focus-ring">
          Back to home
        </Link>
      </div>
    </div>
  );
}
