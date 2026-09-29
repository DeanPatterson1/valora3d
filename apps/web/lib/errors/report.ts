"use client";

import { routeTemplate } from "@/lib/analytics/events";
import { RELEASE_ID, type ErrorKind } from "./shared";

/**
 * Sends one client error report (lib/errors/shared.ts for what it may contain). Fixed fields only: the error's class
 * name and Next's digest, the page's route template, the build id. Never the message or the stack. At most a few per
 * page load, and never throws: reporting must not get in the way of recovery.
 */
const MAX_PER_PAGE = 5;
let sent = 0;
const seen = new Set<string>();

export function reportClientError(kind: ErrorKind, error: unknown): void {
  if (typeof window === "undefined" || sent >= MAX_PER_PAGE) return;
  const e = error as { name?: unknown; digest?: unknown; code?: unknown } | null;
  const name = typeof e?.name === "string" ? e.name : "Error";
  const digest = typeof e?.digest === "string" ? e.digest : typeof e?.code === "string" ? e.code : undefined;
  const key = `${kind}:${name}:${digest ?? ""}:${window.location.pathname}`;
  if (seen.has(key)) return;
  seen.add(key);
  sent++;
  try {
    void fetch("/api/client-errors", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, path: routeTemplate(window.location.pathname), name, ...(digest ? { digest } : {}), release: RELEASE_ID }),
      keepalive: true,
      credentials: "omit",
    }).catch(() => {});
  } catch {
    // Never let reporting fail the page.
  }
}

/** Test hook. */
export function _resetErrorReports(): void {
  sent = 0;
  seen.clear();
}
