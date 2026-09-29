// @vitest-environment node
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { CLIENT_EVENTS, EVENT_NAMES, routeTemplate, serverProps, validateBatch } from "./events";

const SQL = readFileSync(join(__dirname, "../../supabase/migrations/20260930110000_analytics.sql"), "utf8");
const sqlList = (fn: string) => {
  const body = SQL.slice(SQL.indexOf(`function public.${fn}()`));
  const arr = body.slice(body.indexOf("array["), body.indexOf("]::text[]"));
  return [...arr.matchAll(/'([a-z_]+)'/g)].map((m) => m[1]).sort();
};

describe("event allowlist", () => {
  it("matches the database's lists exactly", () => {
    expect([...EVENT_NAMES].sort()).toEqual(sqlList("product_event_names"));
    expect([...CLIENT_EVENTS].sort()).toEqual(sqlList("client_event_names"));
  });

  it("turns paths into route templates: no ids, slugs, queries or odd characters", () => {
    expect(routeTemplate("/")).toBe("/");
    expect(routeTemplate("/projects/3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f")).toBe("/projects/[id]");
    expect(routeTemplate("/r/AbCdEfGhIjKlMnOpQrStUvWx")).toBe("/r/[slug]");
    expect(routeTemplate("/pricing?email=a@b.com#x")).toBe("/pricing");
    expect(routeTemplate("/help/42")).toBe("/help/[n]");
    expect(routeTemplate("/weird path/é")).toBe("/other");
    expect(routeTemplate("relative")).toBe("/other");
  });

  it("keeps valid browser events, drops bad props, and refuses a bad envelope", () => {
    const ok = validateBatch({
      session_id: "abcdefghijklmnop_1",
      events: [
        { event: "landing_view", path: "/?utm_source=x" },
        { event: "cta_click", props: { cta: "signup:/" } },
        { event: "cta_click", props: { cta: "Has Spaces" } },
        { event: "help_search", props: { q_len: 5, q: "secret words" } },
        { event: "signup_start", props: { method: "email" } },
      ],
    });
    expect(ok?.events).toEqual([
      { event: "landing_view", props: {}, path: "/" },
      { event: "cta_click", props: { cta: "signup:/" }, path: null },
      { event: "signup_start", props: { method: "email" }, path: null },
    ]);
    expect(validateBatch({ session_id: "short", events: [{ event: "landing_view" }] })).toBeNull();
    expect(validateBatch({ session_id: "abcdefghijklmnop_1", events: [{ event: "checkout_complete" }] })).toBeNull();
    expect(validateBatch({ session_id: "abcdefghijklmnop_1", events: [], extra: 1 })).toBeNull();
    expect(validateBatch({ session_id: "abcdefghijklmnop_1", events: Array(26).fill({ event: "landing_view" }) })).toBeNull();
  });

  it("checks a route's own props", () => {
    expect(serverProps("checkout_open", { item: "pack:100" })).toEqual({ item: "pack:100" });
    expect(serverProps("checkout_open", { item: "anything" })).toBeNull();
    expect(serverProps("experiment_exposure", { key: "hero_headline", variant: "control" })).toBeTruthy();
  });
});
