import type { SupabaseClient } from "@supabase/supabase-js";
import { serverConfig } from "@/lib/env";
import { createServiceSupabase } from "@/lib/supabase/server";

/**
 * Feature flags, kill switches and numeric settings (table `feature_flags`, edited in /admin -> Flags, every change
 * audited). Server-only: `flag(key, subject)` reads a 30-second cache of the whole table, so a change applies within
 * about 30 s on every Worker isolate. The database enforces the render and signup switches itself
 * (render_jobs_capacity_guard, signups_guard); the routes check the rest and give the friendly answers.
 *
 * Fail open: without a backend (Local mode), or when the table cannot be read, every flag is on and every setting is
 * unset. A kill switch exists to stop spend or abuse on a working system; a database outage already stops both.
 */

export const KILL_SWITCHES = ["renders_enabled", "finals_enabled", "signups_enabled", "sharing_enabled", "checkout_enabled"] as const;
export type KillSwitch = (typeof KILL_SWITCHES)[number];
export const SETTINGS = [
  "global_max_active_renders",
  "daily_gpu_budget_seconds",
  "gpu_seconds_estimate_preview",
  "gpu_seconds_estimate_final",
] as const;
export type SettingKey = (typeof SETTINGS)[number];

export type FlagRow = {
  key: string;
  kind: "flag" | "setting";
  enabled: boolean;
  rollout_percent: number;
  allowlist: string[] | null;
  value: number | string | null;
};

export const FLAG_CACHE_MS = 30_000;

/**
 * Deterministic bucket 0..99 for a subject (user id or browser session id) under a key: FNV-1a over "key:subject".
 * The same subject always lands in the same bucket for a key, and buckets are independent between keys.
 */
export function bucket(key: string, subject: string): number {
  let h = 0x811c9dc5;
  const s = `${key}:${subject}`;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h % 100;
}

/** Pure evaluation of one row for one subject. Off beats everything; then the allowlist; then the rollout bucket. */
export function evaluateFlag(row: FlagRow | undefined, subject: string | null | undefined): boolean {
  if (!row) return true;
  if (!row.enabled) return false;
  const rollout = Math.max(0, Math.min(100, Number(row.rollout_percent ?? 100)));
  if (rollout >= 100) return true;
  if (subject && (row.allowlist ?? []).includes(subject)) return true;
  if (!subject) return false;
  return bucket(row.key, subject) < rollout;
}

type Loader = () => Promise<FlagRow[] | null>;

let cache: { at: number; rows: Map<string, FlagRow> } | null = null;
let loaderOverride: Loader | null = null;

function defaultLoader(): Loader {
  return async () => {
    const config = serverConfig();
    if (!config) return null;
    const admin: SupabaseClient = createServiceSupabase(config);
    const { data, error } = await admin.from("feature_flags").select("key, kind, enabled, rollout_percent, allowlist, value");
    if (error) return null;
    return (data ?? []) as FlagRow[];
  };
}

async function rows(now = Date.now()): Promise<Map<string, FlagRow>> {
  if (cache && now - cache.at < FLAG_CACHE_MS) return cache.rows;
  let list: FlagRow[] | null = null;
  try {
    list = await (loaderOverride ?? defaultLoader())();
  } catch {
    list = null;
  }
  // A failed read keeps serving the last good copy (or the fail-open defaults) and retries after the TTL.
  const map = list ? new Map(list.map((r) => [r.key, r])) : (cache?.rows ?? new Map<string, FlagRow>());
  cache = { at: now, rows: map };
  return map;
}

/** Is `key` on for this subject (a user id, else a browser session id, else nobody in particular)? */
export async function flag(key: string, subject?: string | null): Promise<boolean> {
  return evaluateFlag((await rows()).get(key), subject);
}

/** A numeric setting, or null for "no limit" / unknown. */
export async function setting(key: SettingKey): Promise<number | null> {
  const row = (await rows()).get(key);
  if (!row || row.kind !== "setting" || row.value === null || row.value === undefined) return null;
  const n = Number(row.value);
  return Number.isFinite(n) ? n : null;
}

/** Every kill switch for one subject: what GET /api/flags tells the browser. */
export async function publicFlags(subject?: string | null): Promise<Record<KillSwitch, boolean>> {
  const map = await rows();
  return Object.fromEntries(KILL_SWITCHES.map((k) => [k, evaluateFlag(map.get(k), subject)])) as Record<KillSwitch, boolean>;
}

/** Drops the cache (after an admin edit on this isolate, so the owner sees the change at once). */
export function invalidateFlags(): void {
  cache = null;
}

/** Test hook: replace the table read. */
export function _setFlagLoader(loader: Loader | null): void {
  loaderOverride = loader;
  cache = null;
}
