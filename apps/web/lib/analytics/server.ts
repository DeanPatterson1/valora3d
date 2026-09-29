import type { SupabaseClient } from "@supabase/supabase-js";
import { ATTRIBUTION_COOKIE, decodeAttribution, type Attribution } from "./attribution";
import { routeTemplate, serverProps, type EventName, type EventProps } from "./events";

/**
 * Server-side analytics helpers, over the SERVICE-ROLE client (routes only). Most server events are written by
 * database triggers on the source-of-truth tables (supabase/migrations/20260930110000_analytics.sql); these helpers
 * cover what only a route knows (checkout_open, experiment exposures) and the signup attribution. All best-effort:
 * a failed analytics write never changes the route's answer.
 */

type Rpc = Pick<SupabaseClient, "rpc">;

export async function recordEvent<E extends EventName>(
  admin: Rpc,
  event: E,
  ctx: { userId?: string | null; props?: EventProps<E>; path?: string | null },
): Promise<boolean> {
  const props = serverProps(event, ctx.props ?? {});
  if (!props) return false;
  try {
    const { error } = await admin.rpc("record_product_event", {
      p_event: event,
      p_user_id: ctx.userId ?? null,
      p_props: props,
      p_path: ctx.path ? routeTemplate(ctx.path) : null,
    });
    return !error;
  } catch {
    return false;
  }
}

/** The first-touch attribution cookie of this request, validated (proxy.ts sets it). */
export function attributionFromCookie(value: string | undefined | null): Attribution | null {
  return decodeAttribution(value ?? null);
}

/** Reads it from the Next request cookies (route handlers and server components). */
export async function requestAttribution(): Promise<Attribution | null> {
  try {
    const { cookies } = await import("next/headers");
    return attributionFromCookie((await cookies()).get(ATTRIBUTION_COOKIE)?.value);
  } catch {
    return null;
  }
}

/**
 * Saves the first-touch source on a new account (profiles.signup_source). The SQL writes it once, only for an account
 * made in the last day, and records share_signup when the ref is a share link. Best-effort.
 */
export async function saveSignupSource(admin: Rpc, userId: string, attribution: Attribution | null): Promise<boolean> {
  if (!attribution) return false;
  try {
    const { data, error } = await admin.rpc("record_signup_source", { p_user_id: userId, p_source: attribution });
    return !error && data === true;
  } catch {
    return false;
  }
}
