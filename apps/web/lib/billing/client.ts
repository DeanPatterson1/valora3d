"use client";

import { publicPaddleConfig, type PublicPaddleConfig } from "@/lib/env";
import type { CheckoutItem } from "@/lib/pricing";
import { apiFetch } from "@/lib/services/http";
import { fail, failFrom, ok, type Result } from "@/lib/services/result";
import type { CheckoutResponse, PortalResponse } from "./types";

/**
 * Browser side of checkout: asks /api/billing/checkout what to open, then opens Paddle.js's
 * overlay. Credits are NOT added here; they arrive when Paddle's webhook reaches the server.
 */

export const PADDLE_JS_URL = "https://cdn.paddle.com/paddle/v2/paddle.js";

export type PaddleEvent = { name?: string; data?: unknown };

type PaddleCheckoutOptions = {
  items: { priceId: string; quantity: number }[];
  customer?: { email: string };
  customData?: Record<string, string>;
  settings?: { displayMode?: "overlay"; theme?: "light" | "dark"; allowLogout?: boolean };
};

export type PaddleGlobal = {
  Environment: { set(env: "sandbox" | "production"): void };
  Initialize(options: { token: string; eventCallback?: (event: PaddleEvent) => void }): void;
  Checkout: { open(options: PaddleCheckoutOptions): void };
};

declare global {
  interface Window {
    Paddle?: PaddleGlobal;
  }
}

const listeners = new Set<(event: PaddleEvent) => void>();
let loading: Promise<PaddleGlobal> | null = null;

/** Subscribe to Paddle.js checkout events (checkout.completed, checkout.closed, ...). */
export function onPaddleEvent(listener: (event: PaddleEvent) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function initialize(paddle: PaddleGlobal, config: PublicPaddleConfig): PaddleGlobal {
  if (config.environment === "sandbox") paddle.Environment.set("sandbox");
  paddle.Initialize({ token: config.clientToken, eventCallback: (e) => listeners.forEach((l) => l(e)) });
  return paddle;
}

/** Loads Paddle.js once from Paddle's CDN (allowed by the CSP in next.config.ts). */
export function loadPaddle(config: PublicPaddleConfig): Promise<PaddleGlobal> {
  if (loading) return loading;
  loading = new Promise<PaddleGlobal>((resolve, reject) => {
    if (window.Paddle) return resolve(initialize(window.Paddle, config));
    const script = document.createElement("script");
    script.src = PADDLE_JS_URL;
    script.async = true;
    script.onload = () => (window.Paddle ? resolve(initialize(window.Paddle, config)) : reject(new Error("Paddle.js missing")));
    script.onerror = () => reject(new Error("Paddle.js failed to load"));
    document.head.appendChild(script);
  }).catch((e: unknown) => {
    loading = null; // let the next click retry
    throw e;
  });
  return loading;
}

/** Test hook: forget the cached loader. */
export function resetPaddleLoader() {
  loading = null;
  listeners.clear();
}

export type CheckoutOutcome = "opened" | "changed";

export async function startCheckout(
  item: CheckoutItem,
  deps: { config?: PublicPaddleConfig | null; fetchImpl?: typeof fetch; load?: typeof loadPaddle } = {},
): Promise<Result<CheckoutOutcome>> {
  const config = deps.config === undefined ? publicPaddleConfig() : deps.config;
  if (!config) return fail("checkout_unavailable", "Checkout isn't open yet.");
  const r = await apiFetch<CheckoutResponse>(
    "/api/billing/checkout",
    { method: "POST", body: JSON.stringify({ item }) },
    deps.fetchImpl,
  );
  if (!r.ok) return failFrom(r.error);
  if (r.value.kind === "changed") return ok("changed");

  let paddle: PaddleGlobal;
  try {
    paddle = await (deps.load ?? loadPaddle)(config);
  } catch {
    return fail("offline", "Checkout could not load. Check your connection and try again.");
  }
  paddle.Checkout.open({
    items: [{ priceId: r.value.priceId, quantity: 1 }],
    ...(r.value.customerEmail ? { customer: { email: r.value.customerEmail } } : {}),
    customData: r.value.customData,
    settings: { displayMode: "overlay", theme: "dark", allowLogout: false },
  });
  return ok("opened");
}

/** Opens the Paddle customer portal (invoices, payment method, cancel) in this tab. */
export async function openBillingPortal(
  deps: { fetchImpl?: typeof fetch; navigate?: (url: string) => void } = {},
): Promise<Result<void>> {
  const r = await apiFetch<PortalResponse>("/api/billing/portal", { method: "POST", body: "{}" }, deps.fetchImpl);
  if (!r.ok) return failFrom(r.error);
  (deps.navigate ?? ((url) => window.location.assign(url)))(r.value.url);
  return ok(undefined);
}
