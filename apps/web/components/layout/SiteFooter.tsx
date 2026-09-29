import Link from "next/link";
import { BRAND } from "@/lib/brand";
import { OPERATOR_NAME } from "@/lib/site";

export const TRUST_LINKS = [
  ["/terms", "Terms"],
  ["/privacy", "Privacy"],
  ["/acceptable-use", "Acceptable use"],
  ["/refunds", "Refunds"],
  ["/contact", "Contact"],
] as const;

/** Some gallery and sample renders show real car designs; say whose marks they are and that we are not them. */
export const TRADEMARK_NOTICE = `Car makes and models shown are trademarks of their owners. ${BRAND.name} is not affiliated with, sponsored by or endorsed by any vehicle manufacturer.`;

export function SiteFooter() {
  // Rendered at build for static pages, so the year is the deploy year; any redeploy in a new year updates it.
  const year = new Date().getFullYear();
  return (
    <footer className="border-t border-line py-10">
      <div className="mx-auto flex max-w-[1100px] flex-col gap-6 px-5 text-sm sm:px-8 text-fg-muted md:flex-row md:items-start md:justify-between">
        <Link href="/" className="font-semibold text-fg focus-visible:focus-ring">{BRAND.name}</Link>
        <nav aria-label="Footer" className="flex max-w-2xl flex-wrap gap-x-6 gap-y-3">
          <Link href="/pricing" className="hover:text-fg focus-visible:focus-ring">Pricing</Link>
          <Link href="/help" className="hover:text-fg focus-visible:focus-ring">Help</Link>
          {TRUST_LINKS.map(([href, label]) => (
            <Link key={href} href={href} className="hover:text-fg focus-visible:focus-ring">{label}</Link>
          ))}
          <Link href="/projects" className="hover:text-fg focus-visible:focus-ring">Open app</Link>
        </nav>
      </div>
      <div className="mx-auto mt-8 flex max-w-[1100px] flex-col gap-2 px-5 sm:px-8 text-xs leading-relaxed text-fg-muted">
        <p className="border-t border-line pt-6">© {year} {OPERATOR_NAME}. Payments by Paddle, our merchant of record.</p>
        <p>{TRADEMARK_NOTICE}</p>
      </div>
    </footer>
  );
}
