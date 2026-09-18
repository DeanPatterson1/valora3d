"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import {
  animate,
  motion,
  useMotionValue,
  useReducedMotion,
  useTransform,
} from "motion/react";
import { BRAND } from "@/lib/brand";
import { useCreditsStore } from "@/lib/stores/credits";
import { DUR, EASE } from "@/lib/motion/tokens";

const NAV = [
  { href: "/projects", label: "Projects" },
  { href: "/pricing", label: "Pricing" },
] as const;

/** Renders a number that ticks from its previous value to the new one. */
function TickingNumber({ value }: { value: number }) {
  const rm = useReducedMotion();
  const raw = useMotionValue(value);
  const rounded = useTransform(raw, (v) => Math.round(v));

  useEffect(() => {
    if (rm) {
      raw.set(value);
      return;
    }
    const controls = animate(raw, value, {
      duration: DUR.slow,
      ease: EASE.emphasized,
    });
    return () => controls.stop();
  }, [value, rm, raw]);

  return <motion.span className="font-mono tabular">{rounded}</motion.span>;
}

export function Header() {
  const pathname = usePathname();
  const balance = useCreditsStore((s) => s.balance);
  const refresh = useCreditsStore((s) => s.refresh);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg-0/90 backdrop-blur-sm">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:gap-6 sm:px-6">
        <Link
          href="/"
          className="flex items-center gap-2.5 rounded-sm focus-visible:focus-ring"
        >
          <span
            aria-hidden
            className="size-2 rounded-full bg-accent shadow-[0_0_12px_2px_rgb(242_168_59_/_0.45)]"
          />
          <span className="font-display text-lg font-semibold leading-none text-fg">
            {BRAND.name}
          </span>
        </Link>

        <nav aria-label="Primary" className="flex items-center gap-0 sm:gap-1">
          {NAV.map(({ href, label }) => {
            const active = pathname === href || pathname.startsWith(href + "/");
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={[
                  "rounded-md px-2 py-1.5 text-sm transition-colors sm:px-3 duration-fast ease-standard focus-visible:focus-ring",
                  active ? "text-fg" : "text-fg-muted hover:text-fg",
                ].join(" ")}
              >
                {label}
              </Link>
            );
          })}
        </nav>

        <Link
          href="/pricing"
          aria-label={`${balance} credits. Buy more`}
          className="ml-auto flex h-8 shrink-0 items-center gap-2 rounded-md border border-line bg-bg-1 px-3 text-sm text-fg transition-colors duration-fast ease-standard hover:border-fg-muted focus-visible:focus-ring"
        >
          <TickingNumber value={balance} />
          <span className="hidden text-fg-muted sm:inline">credits</span>
        </Link>
      </div>
    </header>
  );
}
