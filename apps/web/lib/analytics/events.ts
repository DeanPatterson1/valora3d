import { z } from "zod";

/**
 * The product event allowlist: every event name, the props each may carry, and which ones a browser may send.
 * Mirrors `product_event_names()` / `client_event_names()` in supabase/migrations/20260930110000_analytics.sql
 * (events.test.ts pins them equal). No free text anywhere: props are enums, short ids or small numbers, and a
 * path is a route template (/projects/[id]), never a URL with ids or a query string.
 */

const Cta = z.string().regex(/^[a-z0-9][a-z0-9_:/.-]{0,47}$/);
const Code = z.string().regex(/^[A-Z0-9_]{1,40}$/);
const Tier = z.enum(["preview", "final"]);
const Item = z.string().regex(/^(plan:(creator|pro)|pack:\d{1,6})$/);
const Key = z.string().regex(/^[a-z][a-z0-9_]{1,47}$/);

export const EVENT_PROPS = {
  // Browser
  landing_view: z.object({}).strict(),
  pricing_view: z.object({}).strict(),
  cta_click: z.object({ cta: Cta }).strict(),
  signup_start: z.object({ method: z.enum(["email", "google"]) }).strict(),
  help_search: z.object({ q_len: z.number().int().min(0).max(200) }).strict(),
  experiment_exposure: z.object({ key: Key, variant: Key }).strict(),
  // Server (triggers on the source-of-truth tables, or the route itself)
  signup_complete: z.object({}).strict(),
  first_project: z.object({}).strict(),
  upload_start: z.object({}).strict(),
  upload_ready: z.object({}).strict(),
  upload_rejected: z.object({ reason: z.enum(["empty", "too_large", "size_mismatch", "not_glb", "other"]) }).strict(),
  scene_generated: z.object({}).strict(),
  scene_saved: z.object({}).strict(),
  render_requested: z.object({ tier: Tier }).strict(),
  render_succeeded: z.object({ tier: Tier }).strict(),
  render_failed: z.object({ tier: Tier, code: Code }).strict(),
  checkout_open: z.object({ item: Item }).strict(),
  checkout_complete: z.object({ item: z.string().regex(/^(plan:[a-z]+|pack:\d{1,6})$/) }).strict(),
  plan_canceled: z.object({ plan: z.enum(["creator", "pro"]) }).strict(),
  share_created: z.object({}).strict(),
  share_view: z.object({}).strict(),
  share_signup: z.object({}).strict(),
} as const;

export type EventName = keyof typeof EVENT_PROPS;
export type EventProps<E extends EventName> = z.infer<(typeof EVENT_PROPS)[E]>;

export const EVENT_NAMES = Object.keys(EVENT_PROPS) as EventName[];

/** What a browser may send to POST /api/events. Everything else is recorded server-side only. */
export const CLIENT_EVENTS = ["landing_view", "pricing_view", "cta_click", "signup_start", "help_search", "experiment_exposure"] as const;
export type ClientEvent = (typeof CLIENT_EVENTS)[number];

export const SERVER_EVENTS = EVENT_NAMES.filter((e) => !(CLIENT_EVENTS as readonly string[]).includes(e));

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
/** A share slug (/r/<slug>), the one non-uuid dynamic segment. */
const SLUG_ROUTE = /^\/r\/[A-Za-z0-9_-]{22,64}(\/.*)?$/;

/**
 * A pathname as a route template: ids and share slugs become [id] / [slug], the query and hash are dropped, and
 * anything else unusual becomes "/other". Keeps personal data (and share links) out of analytics and error rows.
 */
export function routeTemplate(pathname: string): string {
  const path = (pathname.split(/[?#]/)[0] || "/").slice(0, 200);
  if (!path.startsWith("/")) return "/other";
  if (SLUG_ROUTE.test(path)) return path.replace(/^\/r\/[A-Za-z0-9_-]{22,64}/, "/r/[slug]");
  const parts = path.split("/").map((seg) => {
    if (!seg) return seg;
    if (UUID.test(seg)) return "[id]";
    if (/^\d+$/.test(seg)) return "[n]";
    return seg;
  });
  const out = parts.join("/") || "/";
  return PATH_OK.test(out) && out.length <= 120 ? out : "/other";
}

/** The same check as the database (product_events.path, client_errors.path). */
export const PATH_OK = /^\/[A-Za-z0-9/_.[\]-]*$/;

/** A browser's per-tab random id (sessionStorage), never a cookie. */
export const SESSION_ID = /^[A-Za-z0-9_-]{16,64}$/;

const ClientEventInput = z.object({
  event: z.enum(CLIENT_EVENTS),
  props: z.record(z.string(), z.unknown()).optional(),
  path: z.string().max(200).optional(),
});

/** POST /api/events body: one session, 1-25 events. */
export const EventBatch = z
  .object({
    session_id: z.string().regex(SESSION_ID),
    events: z.array(ClientEventInput).min(1).max(25),
  })
  .strict();

export type ValidEvent = { event: ClientEvent; props: Record<string, unknown>; path: string | null };

/**
 * Validates a batch: unknown names or props that do not match their event's schema drop that event (not the batch);
 * paths are re-templated server-side. Returns null when the envelope itself is invalid.
 */
export function validateBatch(raw: unknown): { sessionId: string; events: ValidEvent[] } | null {
  const parsed = EventBatch.safeParse(raw);
  if (!parsed.success) return null;
  const events: ValidEvent[] = [];
  for (const e of parsed.data.events) {
    const props = EVENT_PROPS[e.event].safeParse(e.props ?? {});
    if (!props.success) continue;
    events.push({ event: e.event, props: props.data as Record<string, unknown>, path: e.path ? routeTemplate(e.path) : null });
  }
  return { sessionId: parsed.data.session_id, events };
}

/** Server-side props check before a route records its own event. */
export function serverProps<E extends EventName>(event: E, props: unknown): EventProps<E> | null {
  const parsed = EVENT_PROPS[event].safeParse(props ?? {});
  return parsed.success ? (parsed.data as EventProps<E>) : null;
}
