"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cx } from "@/components/ui/cx";

export const ADMIN_SECTIONS = [
  { id: "overview", label: "Overview", path: "" },
  { id: "renders", label: "Renders", path: "/renders" },
  { id: "users", label: "Users", path: "/users" },
  { id: "billing", label: "Billing", path: "/billing" },
  { id: "audit", label: "Audit", path: "/audit" },
] as const;

export type AdminSection = (typeof ADMIN_SECTIONS)[number]["id"];

/** The console frame: one top bar with the five sections, then a single dense column. */
export function AdminShell({
  current: forced,
  base = "/admin",
  nav = true,
  children,
}: {
  current?: AdminSection | null;
  base?: string;
  nav?: boolean;
  children: React.ReactNode;
}) {
  const pathname = usePathname() ?? "";
  const current = forced !== undefined ? forced : sectionFor(pathname, base);
  return (
    <div className="flex min-h-dvh flex-col bg-bg-0 text-fg">
      <header className="sticky top-0 z-10 border-b border-line bg-bg-0/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <Link href={base} className="text-sm font-semibold tracking-tight text-fg focus-visible:focus-ring">
            Valora3D <span className="font-normal text-fg-muted">Admin</span>
          </Link>
          {nav ? (
            <nav aria-label="Admin" className="order-last -mx-1 flex w-full min-w-0 gap-1 overflow-x-auto sm:order-none sm:w-auto sm:flex-1">
              {ADMIN_SECTIONS.map((s) => (
                <Link
                  key={s.id}
                  href={`${base}${s.path}`}
                  aria-current={current === s.id ? "page" : undefined}
                  className={cx(
                    "whitespace-nowrap rounded-full px-3 py-1.5 text-sm transition-colors duration-fast focus-visible:focus-ring",
                    current === s.id ? "bg-bg-3 text-fg" : "text-fg-muted hover:bg-bg-2 hover:text-fg",
                  )}
                >
                  {s.label}
                </Link>
              ))}
            </nav>
          ) : (
            <span className="hidden flex-1 sm:block" />
          )}
          <Link href="/projects" className="ml-auto text-sm text-fg-muted sm:ml-0 hover:text-fg focus-visible:focus-ring">
            Back to app
          </Link>
        </div>
      </header>
      <main id="main-content" className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-4 py-6">
        {children}
      </main>
    </div>
  );
}

export function sectionFor(pathname: string, base: string): AdminSection | null {
  const rest = pathname.startsWith(base) ? pathname.slice(base.length) : "";
  const hit = ADMIN_SECTIONS.filter((s) => s.path && (rest === s.path || rest.startsWith(`${s.path}/`)))[0];
  if (hit) return hit.id;
  return rest === "" || rest === "/" ? "overview" : null;
}

/** Local mode (no Supabase configured): nothing to operate. */
export function AdminLocalNotice() {
  return (
    <div className="flex max-w-xl flex-col gap-3 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Admin requires the live backend</h1>
      <p className="text-sm leading-relaxed text-fg-muted">
        This build runs in Local mode: accounts, credits and renders live in each visitor&apos;s browser, so there is nothing to
        operate here. Build with the Supabase environment (<code>NEXT_PUBLIC_SUPABASE_URL</code>,{" "}
        <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code>, and the <code>SUPABASE_SERVICE_ROLE_KEY</code> secret) and sign in as an
        admin to use the console.
      </p>
    </div>
  );
}
