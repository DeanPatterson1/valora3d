"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { routeTemplate } from "@/lib/analytics/events";
import { track } from "@/lib/analytics/track";

/** Page views worth a funnel step. Everything else is covered by the server-side events. */
const PAGE_VIEWS: Record<string, "landing_view" | "pricing_view"> = { "/": "landing_view", "/pricing": "pricing_view" };

/** Links whose clicks are CTA clicks even without a data-cta attribute. */
const CTA_TARGETS = ["/signup", "/pricing", "/login", "/projects"];

/**
 * The CTA id for a click, or null. An element (or ancestor) with `data-cta="hero_signup"` names itself; otherwise a
 * link to one of CTA_TARGETS is named "<target>:<page template>", e.g. "signup:/pricing".
 */
export function ctaFor(target: EventTarget | null, currentPath: string): string | null {
  if (!(target instanceof Element)) return null;
  const named = target.closest<HTMLElement>("[data-cta]");
  const id = named?.dataset.cta?.trim().toLowerCase();
  if (id && /^[a-z0-9][a-z0-9_:/.-]{0,47}$/.test(id)) return id;
  const link = target.closest<HTMLAnchorElement>("a[href]");
  if (!link) return null;
  let url: URL;
  try {
    url = new URL(link.getAttribute("href") ?? "", window.location.origin);
  } catch {
    return null;
  }
  if (url.origin !== window.location.origin) return null;
  const hit = CTA_TARGETS.find((t) => url.pathname === t);
  if (!hit) return null;
  const from = routeTemplate(currentPath).toLowerCase().replace(/[^a-z0-9_/.-]/g, "");
  return `${hit.slice(1)}:${from}`.slice(0, 48);
}

/** The sign-up method a click or submit on /signup starts, or null. Google is the one live provider. */
export function signupMethodFor(e: Event): "email" | "google" | null {
  if (window.location.pathname !== "/signup") return null;
  if (e.type === "submit") return "email";
  const button = e.target instanceof Element ? e.target.closest("button") : null;
  return button && /continue with google/i.test(button.textContent ?? "") ? "google" : null;
}

/** The help centre search box (app/(public)/help/HelpSearch.tsx). */
const HELP_SEARCH = "#help-search";

/**
 * Mounted once in the root layout: landing/pricing views, CTA clicks, sign-up starts and help searches, sent by
 * lib/analytics/track.ts. Listens at the document (capture) so the pages themselves carry no tracking code.
 */
export function Analytics() {
  const pathname = usePathname();

  useEffect(() => {
    const view = pathname ? PAGE_VIEWS[pathname] : undefined;
    if (view) track(view);
  }, [pathname]);

  useEffect(() => {
    const started = new Set<string>();
    let searchTimer: ReturnType<typeof setTimeout> | null = null;
    const signup = (e: Event) => {
      const method = signupMethodFor(e);
      // Once per method per page, however many times the form is retried.
      if (method && !started.has(method)) {
        started.add(method);
        track("signup_start", { method });
      }
    };
    const onClick = (e: MouseEvent) => {
      const cta = ctaFor(e.target, window.location.pathname);
      if (cta) track("cta_click", { cta });
      signup(e);
    };
    const onInput = (e: Event) => {
      const input = e.target instanceof HTMLInputElement && e.target.matches(HELP_SEARCH) ? e.target : null;
      if (!input) return;
      if (searchTimer) clearTimeout(searchTimer);
      // Only the length of a settled query is recorded, never the words.
      searchTimer = setTimeout(() => {
        const q = input.value.trim();
        if (q) track("help_search", { q_len: Math.min(q.length, 200) });
      }, 1500);
    };
    document.addEventListener("click", onClick, { capture: true });
    document.addEventListener("submit", signup, { capture: true });
    document.addEventListener("input", onInput, { capture: true });
    return () => {
      document.removeEventListener("click", onClick, { capture: true });
      document.removeEventListener("submit", signup, { capture: true });
      document.removeEventListener("input", onInput, { capture: true });
      if (searchTimer) clearTimeout(searchTimer);
    };
  }, []);

  return null;
}
