import Link from "next/link";
import { BRAND } from "@/lib/brand";
import { SiteFooter } from "@/components/layout/SiteFooter";

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-bg-0 text-fg">
      <a href="#main-content" className="sr-only rounded-full bg-primary px-5 py-3 text-primary-fg focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50">Skip to content</a>
      <header className="border-b border-line px-5 py-5 sm:px-8">
        <nav aria-label="Main" className="mx-auto flex max-w-[1100px] items-center justify-between gap-6">
          <Link href="/" className="font-semibold focus-visible:focus-ring">{BRAND.name}</Link>
          <div className="flex items-center gap-5 text-sm">
            <Link href="/pricing" className="text-fg-muted hover:text-fg focus-visible:focus-ring">Pricing</Link>
            <Link href="/signup" className="rounded-full bg-primary px-4 py-2 text-primary-fg focus-visible:focus-ring">Get started</Link>
          </div>
        </nav>
      </header>
      <main id="main-content" tabIndex={-1} className="flex-1 outline-none">{children}</main>
      <SiteFooter />
    </div>
  );
}
