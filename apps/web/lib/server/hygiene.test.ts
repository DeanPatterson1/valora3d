// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { POST as signup } from "@/app/api/auth/signup/route";
import { POST as reset } from "@/app/api/auth/forgot-password/route";
import { POST as report } from "@/app/api/client-errors/route";
import { log } from "./log";

const { signUp, resetPasswordForEmail, limit } = vi.hoisted(() => ({
  signUp: vi.fn(), resetPasswordForEmail: vi.fn(), limit: vi.fn(),
}));
vi.mock("@/lib/supabase/server", () => ({
  createRequestSupabase: async () => ({ auth: { signUp, resetPasswordForEmail } }),
  apiError: (status: number, code: string, message: string) => Response.json({ error: { code, message } }, { status }),
}));
vi.mock("@opennextjs/cloudflare", () => ({ getCloudflareContext: () => ({ env: { HYGIENE_RATE_LIMITER: { limit } } }) }));
const origin = "https://valora3d.com";
const request = (path: string, body: unknown, headers = {}) => new Request(`${origin}${path}`, {
  method: "POST", headers: { origin, "content-type": "application/json", ...headers }, body: JSON.stringify(body),
});
const credentials = { email: "a@example.com", password: "password123", name: "Ada" };

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co");
  vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon");
  vi.stubEnv("SUPABASE_SERVICE_ROLE_KEY", "secret");
  vi.stubEnv("NEXT_PUBLIC_TURNSTILE_SITE_KEY", "site");
  vi.stubEnv("TURNSTILE_SECRET_KEY", "secret");
  limit.mockResolvedValue({ success: true });
  signUp.mockResolvedValue({ data: { session: null, user: { id: "u1" } }, error: null });
  resetPasswordForEmail.mockResolvedValue({ error: null });
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => { vi.restoreAllMocks(); vi.clearAllMocks(); vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe("protected auth routes", () => {
  for (const [action, handler] of [["signup", signup], ["forgot-password", reset]] as const) {
    it(`${action}: rejects missing or invalid tokens before Supabase`, async () => {
      const fetcher = vi.fn().mockResolvedValue(Response.json({ success: false }));
      vi.stubGlobal("fetch", fetcher);
      expect((await handler(request(`/api/auth/${action}`, credentials))).status).toBe(400);
      expect(fetcher).not.toHaveBeenCalled();
      expect((await handler(request(`/api/auth/${action}`, { ...credentials, turnstileToken: "invalid" }))).status).toBe(400);
      expect(signUp).not.toHaveBeenCalled();
      expect(resetPasswordForEmail).not.toHaveBeenCalled();
    });
    it(`${action}: verifies action and hostname, then calls Supabase`, async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ success: true, action, hostname: "valora3d.com" })));
      const response = await handler(request(`/api/auth/${action}`, { ...credentials, turnstileToken: "valid" }));
      expect(response.status).toBe(200);
      expect(action === "signup" ? signUp : resetPasswordForEmail).toHaveBeenCalledOnce();
    });
    it(`${action}: fails closed on partial config and verification outages`, async () => {
      vi.stubEnv("TURNSTILE_SECRET_KEY", "");
      expect((await handler(request(`/api/auth/${action}`, { ...credentials, turnstileToken: "valid" }))).status).toBe(503);
      vi.stubEnv("TURNSTILE_SECRET_KEY", "secret");
      vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("secret a@example.com")));
      expect((await handler(request(`/api/auth/${action}`, { ...credentials, turnstileToken: "valid" }))).status).toBe(503);
      expect(signUp).not.toHaveBeenCalled();
      expect(resetPasswordForEmail).not.toHaveBeenCalled();
    });
    it(`${action}: works without Turnstile configuration`, async () => {
      vi.stubEnv("NEXT_PUBLIC_TURNSTILE_SITE_KEY", ""); vi.stubEnv("TURNSTILE_SECRET_KEY", "");
      expect((await handler(request(`/api/auth/${action}`, credentials))).status).toBe(200);
    });
  }
  it("rejects wrong action, hostname and replay without calling Supabase", async () => {
    for (const result of [{ success: true, action: "forgot-password", hostname: "valora3d.com" }, { success: true, action: "signup", hostname: "evil.com" }, { success: false, "error-codes": ["timeout-or-duplicate"] }]) {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(result)));
      expect((await signup(request("/api/auth/signup", { ...credentials, turnstileToken: "token" }))).status).toBe(400);
    }
    expect(signUp).not.toHaveBeenCalled();
  });
  it("refuses cross-origin and oversized auth requests", async () => {
    expect((await signup(request("/api/auth/signup", credentials, { origin: "https://evil.com" }))).status).toBe(403);
    expect((await signup(request("/api/auth/signup", { ...credentials, name: "x".repeat(17000) }))).status).toBe(413);
    expect(signUp).not.toHaveBeenCalled();
  });
  it("does not reveal whether a reset address exists, but surfaces outages", async () => {
    vi.stubEnv("NEXT_PUBLIC_TURNSTILE_SITE_KEY", ""); vi.stubEnv("TURNSTILE_SECRET_KEY", "");
    resetPasswordForEmail.mockResolvedValue({ error: { status: 400, message: "Unknown email" } });
    expect((await reset(request("/api/auth/forgot-password", credentials))).status).toBe(200);
    resetPasswordForEmail.mockResolvedValue({ error: { status: 500, message: "secret" } });
    expect((await reset(request("/api/auth/forgot-password", credentials))).status).toBe(503);
  });
});

describe("private error reporting", () => {
  it("logs only a fixed event and route; rejects arbitrary client fields", async () => {
    expect((await report(request("/api/client-errors", { event: "global_error" }))).status).toBe(204);
    const entry = JSON.parse(vi.mocked(console.error).mock.calls[0][0]);
    expect(entry).toMatchObject({ level: "error", route: "/api/client-errors", message: "global_error" });
    expect(entry.requestId).toMatch(/^[0-9a-f-]{36}$/);
    expect((await report(request("/api/client-errors", { event: "global_error", message: "a@example.com secret" }))).status).toBe(400);
    expect(console.error).toHaveBeenCalledOnce();
  });
  it("rejects cross-origin, oversized streamed bodies, and rate-limited reports", async () => {
    expect((await report(request("/api/client-errors", {}, { origin: "https://evil.com" }))).status).toBe(403);
    expect((await report(request("/api/client-errors", { event: "x".repeat(3000) }))).status).toBe(413);
    limit.mockResolvedValue({ success: false });
    expect((await report(request("/api/client-errors", { event: "global_error" }))).status).toBe(429);
    expect(console.error).not.toHaveBeenCalled();
  });
  it("does not copy untrusted context fields or non-UUID identifiers", () => {
    log("error", "/api/client-errors", "global_error", { requestId: "email@example.com", userId: "secret" });
    const entry = JSON.parse(vi.mocked(console.error).mock.calls[0][0]);
    expect(entry.userId).toBeUndefined();
    expect(entry.requestId).not.toBe("email@example.com");
  });
});
