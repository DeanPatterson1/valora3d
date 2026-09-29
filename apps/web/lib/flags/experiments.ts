import type { SupabaseClient } from "@supabase/supabase-js";
import { recordEvent } from "@/lib/analytics/server";
import { bucket } from "./flags";

/**
 * A/B experiments: deterministic buckets by user id (else the browser's session id), exposure logged as a product
 * event so a test can be read later from product_events. None are configured yet: with no traffic before launch a
 * test could not reach significance. Add one here, e.g.
 *   hero_headline: { variants: ["control", "keyword"], weights: [50, 50] }
 * then `const v = await experiment(admin, "hero_headline", { userId, sessionId })` where the page is rendered.
 */
export type ExperimentDef = { variants: readonly [string, ...string[]]; weights?: readonly number[] };

export const EXPERIMENTS: Record<string, ExperimentDef> = {};

/** Pure: which variant a subject gets. Weights are percentages (default: even split). */
export function assignVariant(key: string, def: ExperimentDef, subject: string): string {
  const weights = def.weights && def.weights.length === def.variants.length ? def.weights : def.variants.map(() => 100 / def.variants.length);
  const total = weights.reduce((a, b) => a + b, 0) || 1;
  const b = bucket(`exp:${key}`, subject);
  let acc = 0;
  for (let i = 0; i < def.variants.length; i++) {
    acc += (weights[i] / total) * 100;
    if (b < acc) return def.variants[i];
  }
  return def.variants[def.variants.length - 1];
}

/**
 * The variant for this user or session, with its exposure logged (best-effort). An unknown experiment, or no subject
 * at all, is "control" and logs nothing.
 */
export async function experiment(
  admin: Pick<SupabaseClient, "rpc"> | null,
  key: string,
  subject: { userId?: string | null; sessionId?: string | null },
  registry: Record<string, ExperimentDef> = EXPERIMENTS,
): Promise<string> {
  const def = registry[key];
  const id = subject.userId || subject.sessionId;
  if (!def || !id) return "control";
  const variant = assignVariant(key, def, id);
  if (admin) await recordEvent(admin, "experiment_exposure", { userId: subject.userId ?? null, props: { key, variant } });
  return variant;
}
