import Link from "next/link";
import { signupHref } from "@/lib/nav/next";

export const PRIMARY_LINK =
  "inline-flex h-10 items-center rounded-full bg-primary px-5 text-sm font-medium text-primary-fg transition-colors duration-fast ease-standard hover:bg-primary/90 focus-visible:focus-ring";
export const SECONDARY_LINK =
  "inline-flex h-10 items-center rounded-full border border-line px-5 text-sm text-fg transition-colors duration-fast ease-standard hover:bg-bg-3 focus-visible:focus-ring";

/** The closing call to action on the public content pages (examples, guides, the .glb checker). */
export function SignupCta({ title, lead, secondary }: { title: string; lead: string; secondary?: { href: string; label: string } }) {
  return (
    <section aria-label="Get started" className="mt-14 rounded-lg border border-line bg-bg-1 p-6 sm:p-8">
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <p className="mt-2 max-w-xl text-sm leading-relaxed text-fg-muted">{lead}</p>
      <div className="mt-5 flex flex-wrap gap-3">
        <Link href={signupHref()} className={PRIMARY_LINK} data-cta="content_signup">Start free</Link>
        {secondary && <Link href={secondary.href} className={SECONDARY_LINK}>{secondary.label}</Link>}
      </div>
    </section>
  );
}
