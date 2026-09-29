"use client";

import Link from "next/link";
import { useState } from "react";
import { motion, useMotionValueEvent, useScroll } from "motion/react";
import { BRAND } from "@/lib/brand";
import { EASE } from "@/lib/motion/tokens";
import { cx } from "@/components/ui";
import { LogoMark } from "@/components/layout/LogoMark";
import { START_PATH, signupHref } from "@/lib/nav/next";

const LINKS = [
  { href: "#features", label: "Features" },
  { href: "#gallery", label: "Gallery" },
  { href: "#pricing", label: "Pricing" },
] as const;

/**
 * Floating pill nav. Hidden over the hero (whose own header carries the logo, Log in and Get started); fades
 * in once the sheet has scrolled past it.
 *
 * `animate` is the same for everyone: with `initial={false}` motion writes it into the
 * SSR `style`, so branching it on `useReducedMotion()` (server `null`, client the real
 * preference) would hand React two different `transform`s to hydrate. `data-landing-nav`
 * drops the `y` travel from app/globals.css instead. `<MotionConfig reducedMotion="user">`
 * alone is not enough here: it snaps `y` rather than removing it, and on the way out that
 * snap lands while the pill is still opaque, which reads as a 12px jump.
 */
export function LandingNav() {
  const { scrollY } = useScroll();
  const [visible, setVisible] = useState(false);
  useMotionValueEvent(scrollY, "change", (v) => {
    const threshold = typeof window === "undefined" ? 600 : window.innerHeight * 0.75;
    setVisible(v > threshold);
  });

  return (
    <motion.nav
      aria-label="Landing"
      data-landing-nav
      data-visible={visible || undefined}
      inert={!visible}
      initial={false}
      animate={{ opacity: visible ? 1 : 0, y: visible ? 0 : -12 }}
      transition={{ duration: 0.4, ease: EASE.standard }}
      className={cx("fixed inset-x-0 top-4 z-50 flex justify-center px-4", !visible && "pointer-events-none")}
    >
      <div className="glass flex h-12 items-center gap-1 rounded-full pl-4 pr-1.5 shadow-raise">
        <Link href="/" className="mr-2 flex items-center gap-2 rounded-full text-sm font-semibold tracking-tight text-fg focus-visible:focus-ring">
          <LogoMark />
          <span className="hidden sm:inline">{BRAND.name}</span>
        </Link>
        <ul className="hidden items-center md:flex">
          {LINKS.map((l) => (
            <li key={l.href}>
              <a href={l.href} className="inline-flex h-9 items-center rounded-full px-3 text-sm text-fg-muted transition-colors duration-fast ease-standard hover:text-fg focus-visible:focus-ring">
                {l.label}
              </a>
            </li>
          ))}
        </ul>
        <span aria-hidden className="mx-1 hidden h-5 w-px bg-line md:block" />
        <Link href="/help" className="inline-flex h-9 items-center rounded-full px-3 text-sm text-fg-muted hover:text-fg focus-visible:focus-ring">Help</Link>
        <Link href="/login" className="hidden h-9 items-center rounded-full px-3 text-sm text-fg-muted transition-colors duration-fast ease-standard hover:text-fg focus-visible:focus-ring sm:inline-flex">
          Log in
        </Link>
        <Link
          href={signupHref(START_PATH)}
          className="inline-flex h-9 items-center rounded-full bg-primary px-4 text-sm font-medium text-primary-fg transition-colors duration-fast ease-standard hover:bg-primary/90 focus-visible:focus-ring"
        >
          Start a project
        </Link>
      </div>
    </motion.nav>
  );
}
