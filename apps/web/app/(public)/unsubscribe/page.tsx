import type { Metadata } from "next";
import Link from "next/link";
import { CATEGORY_LABEL } from "@/lib/email/categories";
import { isOptOutCategory } from "@/lib/email/unsubscribe";

export const metadata: Metadata = {
  title: "Email preferences",
  description: "Unsubscribe from Valora3D emails.",
  robots: { index: false, follow: false },
};

type Search = { u?: string; c?: string; t?: string; done?: string; error?: string };
const one = (v: unknown) => (typeof v === "string" ? v.slice(0, 100) : "");

const BUTTON =
  "inline-flex h-11 cursor-pointer items-center rounded-full bg-primary px-5 text-sm font-medium text-primary-fg transition-colors duration-fast ease-standard hover:bg-primary/90 focus-visible:focus-ring";
const LINK = "text-fg underline underline-offset-2 focus-visible:focus-ring";

/**
 * The body link of every product-tips and render mail. One button posts the signed link to /api/email/unsubscribe
 * (no login needed), then the page shows the done state. Opening the link alone changes nothing.
 */
export default async function UnsubscribePage({ searchParams }: { searchParams: Promise<Search> }) {
  const q = await searchParams;
  const done = one(q.done);
  const error = one(q.error);
  const c = one(q.c);

  let body: React.ReactNode;
  if (isOptOutCategory(done)) {
    body = (
      <>
        <h1 className="text-3xl font-semibold tracking-tight">You&apos;re unsubscribed</h1>
        <p className="text-fg-muted">
          We won&apos;t send you {CATEGORY_LABEL[done]} anymore. Account and billing emails still arrive. You can turn it back on
          any time in <Link href="/settings?section=notifications" className={LINK}>Settings</Link>.
        </p>
      </>
    );
  } else if (error || !isOptOutCategory(c) || !q.u || !q.t) {
    body = (
      <>
        <h1 className="text-3xl font-semibold tracking-tight">{error === "unavailable" ? "Please try again" : "This link doesn't work"}</h1>
        <p className="text-fg-muted">
          {error === "unavailable"
            ? "We couldn't update your preferences just now. Try the link again in a minute."
            : "The unsubscribe link is incomplete or out of date."}{" "}
          You can always change which emails you get in <Link href="/settings?section=notifications" className={LINK}>Settings</Link>, or
          write to <a href="mailto:support@valora3d.com" className={LINK}>support@valora3d.com</a>.
        </p>
      </>
    );
  } else {
    body = (
      <>
        <h1 className="text-3xl font-semibold tracking-tight">Unsubscribe from {CATEGORY_LABEL[c]}?</h1>
        <p className="text-fg-muted">
          You&apos;ll stop getting {CATEGORY_LABEL[c]} from Valora3D. Account and billing emails, like receipts and payment problems,
          still arrive.
        </p>
        <form method="post" action="/api/email/unsubscribe" className="mt-2">
          <input type="hidden" name="u" value={one(q.u)} />
          <input type="hidden" name="c" value={c} />
          <input type="hidden" name="t" value={one(q.t)} />
          <input type="hidden" name="from" value="page" />
          <button type="submit" className={BUTTON}>
            Unsubscribe
          </button>
        </form>
      </>
    );
  }

  return <div className="mx-auto flex max-w-xl flex-col gap-4 px-5 py-20 sm:px-8">{body}</div>;
}
