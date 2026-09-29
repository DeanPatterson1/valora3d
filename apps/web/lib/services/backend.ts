import { publicSupabaseConfig } from "@/lib/env";
import type { AuthFeatures } from "./types";

/**
 * The cheap half of the services seam: which backend this build talks to and what its auth offers,
 * without importing either implementation. Marketing and auth pages read these synchronously at
 * render, so they must not pull in supabase-js or zod (lib/services/index.ts) just to decide a label;
 * the stores import the implementations lazily when an action actually runs.
 */
export type Backend = "local" | "supabase";

export const BACKEND: Backend = publicSupabaseConfig() ? "supabase" : "local";

export const LOCAL_AUTH_FEATURES: AuthFeatures = { guest: true, providers: ["google", "apple"], passwordReset: false, serverAccount: false };
export const SUPABASE_AUTH_FEATURES: AuthFeatures = { guest: false, providers: ["google"], passwordReset: true, serverAccount: true };

export const AUTH_FEATURES: AuthFeatures = BACKEND === "local" ? LOCAL_AUTH_FEATURES : SUPABASE_AUTH_FEATURES;

/** The Local prototype's "Continue as guest" account. */
export const GUEST_ID = "guest";

/** Passwords shorter than this are refused by both backends. */
export const MIN_PASSWORD = 8;

export function normaliseEmail(email: string): string {
  return email.trim().toLowerCase();
}

export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

/** The full services object, loaded on first use. Same module instance as a static import. */
export const loadServices = () => import("./index").then((m) => m.services);
