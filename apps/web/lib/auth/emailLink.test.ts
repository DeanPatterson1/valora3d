// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { EMAIL_FLOW_COOKIE, markEmailFlowStarted } from "./emailFlow";
import { continueUrl, parseConfirmLink } from "./emailLink";

/** Login CSRF on email links (security review L2): the token is only spent by a same-origin POST. */

const h = vi.hoisted(() => ({ verifyOtp: vi.fn(), configured: true }));
vi.mock("@/lib/env", () => ({
  serverConfig: () => (h.configured ? { supabase: { url: "https://x.supabase.co", anonKey: "a", serviceRoleKey: "s" } } : null),
}));
vi.mock("@/lib/supabase/server", () => ({
  createRequestSupabase: async () => ({ auth: { verifyOtp: h.verifyOtp } }),
  apiError: (status: number) => new Response(null, { status }),
}));

const route = await import("@/app/auth/confirm/route");
const ORIGIN = "https://valora3d.com";
const HASH = "pkce_0123456789abcdef0123456789abcdef";

function post(fields: Record<string, string>, headers: Record<string, string> = { origin: ORIGIN }) {
  return new NextRequest(`${ORIGIN}/auth/confirm`, { method: "POST", headers, body: new URLSearchParams(fields) });
}

beforeEach(() => {
  h.verifyOtp.mockReset().mockResolvedValue({ error: null });
  h.configured = true;
});

describe("parseConfirmLink", () => {
  const q = (s: string) => new URLSearchParams(s);
  it("accepts the types our templates send, and keeps next same-origin", () => {
    expect(parseConfirmLink((k) => q(`token_hash=${HASH}&type=email&next=/projects`).get(k))).toEqual({ tokenHash: HASH, type: "email", next: "/projects" });
    expect(parseConfirmLink((k) => q(`token_hash=${HASH}&type=email&next=//evil.example`).get(k))?.next).toBe("/projects");
    expect(parseConfirmLink((k) => q(`token_hash=${HASH}&type=recovery&next=/projects`).get(k))?.next).toBe("/reset-password");
  });
  it("refuses unknown types and malformed tokens", () => {
    expect(parseConfirmLink((k) => q(`token_hash=${HASH}&type=magiclink`).get(k))).toBeNull();
    expect(parseConfirmLink((k) => q(`token_hash=a%22b&type=email`).get(k))).toBeNull();
    expect(parseConfirmLink((k) => q(`type=email`).get(k))).toBeNull();
  });
  it("marks the browser that asked for an email", () => {
    const doc = { cookie: "" };
    markEmailFlowStarted(doc, true);
    expect(doc.cookie).toBe(`${EMAIL_FLOW_COOKIE}=1; Max-Age=86400; Path=/; SameSite=Lax; Secure`);
  });
});

describe("GET /auth/confirm", () => {
  it("never spends the token: it forwards to the click-to-continue page", async () => {
    const res = await route.GET(new NextRequest(`${ORIGIN}/auth/confirm?token_hash=${HASH}&type=email&next=/projects`));
    expect(res.status).toBe(303);
    expect(res.headers.get("location")).toBe(`${ORIGIN}${continueUrl({ tokenHash: HASH, type: "email", next: "/projects" })}`);
    expect(h.verifyOtp).not.toHaveBeenCalled();
  });
  it("sends a bad link to the login page", async () => {
    const res = await route.GET(new NextRequest(`${ORIGIN}/auth/confirm?token_hash=${HASH}&type=magiclink`));
    expect(res.headers.get("location")).toBe(`${ORIGIN}/login?error=link_invalid`);
  });
});

describe("POST /auth/confirm", () => {
  const fields = { token_hash: HASH, type: "email", next: "/projects" };

  it("refuses a cross-site or origin-less post without touching the token", async () => {
    for (const headers of [{ origin: "https://evil.example" }, {} as Record<string, string>]) {
      const res = await route.POST(post(fields, headers));
      expect(res.headers.get("location")).toBe(`${ORIGIN}/login?error=link_invalid`);
    }
    expect(h.verifyOtp).not.toHaveBeenCalled();
  });

  it("in the browser that asked: verifies and continues", async () => {
    const res = await route.POST(post(fields, { origin: ORIGIN, cookie: `${EMAIL_FLOW_COOKIE}=1` }));
    expect(h.verifyOtp).toHaveBeenCalledWith({ type: "email", token_hash: HASH });
    expect(res.status).toBe(303);
    expect(res.headers.get("location")).toBe(`${ORIGIN}/projects`);
  });

  it("anywhere else: verifies, then asks 'is this your account?' before going on", async () => {
    const res = await route.POST(post(fields));
    expect(h.verifyOtp).toHaveBeenCalledTimes(1);
    expect(res.headers.get("location")).toBe(`${ORIGIN}/auth/continue?done=1&next=%2Fprojects`);
  });

  it("a failed verification goes to the login page", async () => {
    h.verifyOtp.mockResolvedValue({ error: { message: "expired" } });
    const res = await route.POST(post(fields));
    expect(res.headers.get("location")).toBe(`${ORIGIN}/login?error=link_invalid`);
  });
});
