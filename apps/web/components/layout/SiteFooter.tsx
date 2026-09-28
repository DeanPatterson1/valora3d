import Link from "next/link";
import { BRAND } from "@/lib/brand";

export const TRUST_LINKS = [
  ["/terms", "Terms"],
  ["/privacy", "Privacy"],
  ["/acceptable-use", "Acceptable use"],
  ["/refunds", "Refunds"],
  ["/contact", "Contact"],
] as const;

export function SiteFooter() {
  return (
    <footer className="border-t border-line px-5 py-10 sm:px-8">
      <div className="mx-auto flex max-w-[1100px] flex-col gap-6 text-sm text-fg-muted md:flex-row md:items-start md:justify-between">
        <Link href="/" className="font-semibold text-fg focus-visible:focus-ring">{BRAND.name}</Link>
        <nav aria-label="Footer" className="flex max-w-2xl flex-wrap gap-x-6 gap-y-3">
          <Link href="/pricing" className="hover:text-fg focus-visible:focus-ring">Pricing</Link>
          {TRUST_LINKS.map(([href, label]) => (
            <Link key={href} href={href} className="hover:text-fg focus-visible:focus-ring">{label}</Link>
          ))}
          <Link href="/projects" className="hover:text-fg focus-visible:focus-ring">Open app</Link>
        </nav>
      </div>
    </footer>
  );
}
