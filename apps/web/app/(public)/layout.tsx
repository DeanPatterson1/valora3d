import Link from "next/link";
import { BRAND } from "@/lib/brand";
import { signupHref } from "@/lib/nav/next";
import { LogoMark } from "@/components/layout/LogoMark";
import { SiteFooter } from "@/components/layout/SiteFooter";

const LINK = "h-9 items-center rounded-full px-2.5 text-fg-muted transition-colors duration-fast ease-standard hover:text-fg focus-visible:focus-ring sm:px-3";

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-bg-0 text-fg">
      <a href="#main-content" className="sr-only rounded-full bg-primary px-5 py-3 text-primary-fg focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50">Skip to content</a>
      <header className="border-b border-line">
        {/* Same frame as the page content (max-w-[1100px] with the padding inside), so the two left edges line up. */}
        <nav aria-label="Main" className="mx-auto flex max-w-[1100px] items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <Link href="/" className="flex items-center gap-2 rounded-sm font-semibold tracking-tight focus-visible:focus-ring">
            <LogoMark />
            {BRAND.name}
          </Link>
          <div className="flex items-center gap-1 text-sm">
            <Link href="/pricing" className={`hidden sm:inline-flex ${LINK}`}>Pricing</Link>
            <Link href="/help" className={`inline-flex ${LINK}`}>Help</Link>
            <Link href="/login" className={`inline-flex ${LINK}`}>Log in</Link>
            <Link href={signupHref()} className="ml-1 inline-flex h-9 items-center rounded-full bg-primary px-4 font-medium text-primary-fg transition-colors duration-fast ease-standard hover:bg-primary/90 focus-visible:focus-ring">Get started</Link>
          </div>
        </nav>
      </header>
      <main id="main-content" tabIndex={-1} className="flex-1 outline-none">{children}</main>
      <SiteFooter />
    </div>
  );
}
