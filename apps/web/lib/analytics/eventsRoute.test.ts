// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { encodeAttribution } from "./attribution";

const h = vi.hoisted(() => ({
  config: null as null | Record<string, unknown>,
  limit: vi.fn(),
  rpc: vi.fn(),
  getUser: vi.fn(),
}));
vi.mock("@/lib/env", () => ({ serverConfig: () => h.config }));
vi.mock("@opennextjs/cloudflare", () => ({ getCloudflareContext: () => ({ env: { HYGIENE_RATE_LIMITER: { limit: h.limit } } }) }));
vi.mock("@/lib/supabase/server", () => ({
  apiError: (status: number, code: string, message: string) => Response.json({ error: { code, message } }, { status }),
  createServiceSupabase: () => ({ rpc: h.rpc }),
  createRequestSupabase: async () => ({ auth: { getUser: h.getUser } }),
}));

const { POST } = await import("@/app/api/events/route");

const origin = "https://valora3d.com";
const SID = "abcdefghijklmnop_1";
const USER = "3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f";
const post = (body: unknown, headers: Record<string, string> = {}) =>
  POST(new Request(`${origin}/api/events`, { method: "POST", headers: { origin, "content-type": "text/plain;charset=UTF-8", ...headers }, body: JSON.stringify(body) }));

beforeEach(() => {
  h.config = { supabase: {} };
  h.limit.mockResolvedValue({ success: true });
  h.rpc.mockResolvedValue({ data: 1, error: null });
  h.getUser.mockResolvedValue({ data: { user: { id: USER } } });
});
afterEach(() => vi.clearAllMocks());

describe("POST /api/events", () => {
  it("stores validated browser events for the session, anonymously without a session cookie", async () => {
    const res = await post({ session_id: SID, events: [{ event: "landing_view", path: "/?utm_source=x" }, { event: "cta_click", props: { cta: "BAD cta" } }] });
    expect(res.status).toBe(204);
    expect(h.getUser).not.toHaveBeenCalled();
    expect(h.rpc).toHaveBeenCalledWith("record_client_events", {
      p_session_id: SID,
      p_user_id: null,
      p_events: [{ event: "landing_view", props: {}, path: "/" }],
    });
  });

  it("attaches the verified account and saves its first-touch source", async () => {
    const cookie = `sb-proj-auth-token=x; v3d_src=${encodeAttribution({ source: "newsletter" })}`;
    await post({ session_id: SID, events: [{ event: "pricing_view" }] }, { cookie });
    expect(h.rpc).toHaveBeenCalledWith("record_client_events", expect.objectContaining({ p_user_id: USER }));
    expect(h.rpc).toHaveBeenCalledWith("record_signup_source", { p_user_id: USER, p_source: { source: "newsletter" } });
  });

  it("refuses cross-origin, server event names and oversized bodies; rate-limits per IP", async () => {
    expect((await post({ session_id: SID, events: [{ event: "landing_view" }] }, { origin: "https://evil.example" })).status).toBe(403);
    expect((await post({ session_id: SID, events: [{ event: "checkout_complete" }] })).status).toBe(400);
    expect((await post({ session_id: SID, events: [{ event: "landing_view", path: "x".repeat(9000) }] })).status).toBe(413);
    h.limit.mockResolvedValue({ success: false });
    expect((await post({ session_id: SID, events: [{ event: "landing_view" }] })).status).toBe(429);
    expect(h.rpc).not.toHaveBeenCalled();
  });

  it("accepts and drops everything in Local mode, without spending the rate limit", async () => {
    h.config = null;
    expect((await post({ session_id: SID, events: [{ event: "landing_view" }] })).status).toBe(204);
    expect(h.limit).not.toHaveBeenCalled();
    expect(h.rpc).not.toHaveBeenCalled();
  });

  it("never fails the page when the database write fails", async () => {
    h.rpc.mockRejectedValue(new Error("db down"));
    expect((await post({ session_id: SID, events: [{ event: "landing_view" }] })).status).toBe(204);
  });
});
