"use client";

import { routeTemplate, type ClientEvent, type EventProps } from "./events";

/**
 * Browser side of first-party product analytics. `track()` queues an event; the queue is sent to POST /api/events
 * in small batches (after a short delay, or with sendBeacon when the page is hidden). Cookieless: a random id for
 * this tab lives in sessionStorage and nothing else identifies the visitor (the server adds the account id when
 * someone is signed in). Nothing is sent when the browser asks not to be tracked (Global Privacy Control or DNT),
 * in tests, or on the server.
 */

type Queued = { event: ClientEvent; props: Record<string, unknown>; path: string };

const ENDPOINT = "/api/events";
const SESSION_KEY = "v3d_sid";
const FLUSH_MS = 2000;
const MAX_BATCH = 20;
/** Per page load, so a runaway loop cannot flood the endpoint. */
const MAX_PER_PAGE = 100;

let queue: Queued[] = [];
let timer: ReturnType<typeof setTimeout> | null = null;
let sentThisPage = 0;
let listening = false;
let memorySession: string | null = null;

function optedOut(): boolean {
  if (typeof navigator === "undefined") return true;
  const nav = navigator as Navigator & { globalPrivacyControl?: boolean };
  return nav.globalPrivacyControl === true || nav.doNotTrack === "1";
}

let forced: boolean | null = null;

export function analyticsEnabled(): boolean {
  if (typeof window === "undefined") return false;
  if (forced !== null) return forced;
  if (process.env.NODE_ENV === "test") return false;
  return !optedOut();
}

function randomId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** This tab's random id. Falls back to memory when storage is blocked. */
export function sessionId(): string {
  try {
    const existing = window.sessionStorage.getItem(SESSION_KEY);
    if (existing && /^[A-Za-z0-9_-]{16,64}$/.test(existing)) return existing;
    const id = randomId();
    window.sessionStorage.setItem(SESSION_KEY, id);
    return id;
  } catch {
    memorySession ??= randomId();
    return memorySession;
  }
}

function body(events: Queued[]): string {
  return JSON.stringify({ session_id: sessionId(), events });
}

/**
 * Sends what is queued. `beacon` when the page is going away (sendBeacon survives unload; text/plain so it needs no
 * CORS preflight, which the route accepts).
 */
export function flush(beacon = false): void {
  if (timer) {
    clearTimeout(timer);
    timer = null;
  }
  while (queue.length) {
    const batch = queue.splice(0, MAX_BATCH);
    const payload = body(batch);
    try {
      if (beacon && typeof navigator.sendBeacon === "function") {
        if (navigator.sendBeacon(ENDPOINT, new Blob([payload], { type: "text/plain;charset=UTF-8" }))) continue;
      }
      void fetch(ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        keepalive: true,
        credentials: "same-origin",
      }).catch(() => {});
    } catch {
      // Analytics never breaks the page.
    }
  }
}

function listen(): void {
  if (listening) return;
  listening = true;
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush(true);
  });
  window.addEventListener("pagehide", () => flush(true));
}

/** Records one browser event (see CLIENT_EVENTS). Props are checked again on the server. */
export function track<E extends ClientEvent>(event: E, props?: EventProps<E>): void {
  if (!analyticsEnabled() || sentThisPage >= MAX_PER_PAGE) return;
  sentThisPage++;
  listen();
  queue.push({ event, props: (props ?? {}) as Record<string, unknown>, path: routeTemplate(window.location.pathname) });
  if (queue.length >= MAX_BATCH) flush();
  else if (!timer) timer = setTimeout(() => flush(), FLUSH_MS);
}

/** Test hooks. */
export function _forceAnalytics(on: boolean | null): void {
  forced = on;
}

export function _resetTracking(): void {
  queue = [];
  if (timer) clearTimeout(timer);
  timer = null;
  sentThisPage = 0;
}

export function _queued(): readonly Queued[] {
  return queue;
}
