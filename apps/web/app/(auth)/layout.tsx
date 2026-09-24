import Link from "next/link";
import { BRAND } from "@/lib/brand";

function LogoMark() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="size-6 shrink-0" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.75" />
      <circle cx="12" cy="12" r="3.5" fill="currentColor" />
    </svg>
  );
}

/** Auth pages: plain page background, brand mark top-left, one centred column (ChatGPT's login). */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-bg-0 text-fg">
      <header className="flex h-16 shrink-0 items-center px-5 sm:px-10">
        <Link
          href="/"
          className="flex items-center gap-2 rounded-sm text-fg focus-visible:focus-ring"
          aria-label={`${BRAND.name} home`}
        >
          <LogoMark />
          <span className="text-sm font-semibold tracking-tight">{BRAND.name}</span>
        </Link>
      </header>
      <main className="flex flex-1 flex-col items-center justify-center px-4 pb-6 pt-4 sm:py-6">
        {children}
      </main>
    </div>
  );
}
