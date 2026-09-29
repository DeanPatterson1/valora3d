// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { POST as report } from "@/app/api/client-errors/route";
import { log } from "./log";

const { limit } = vi.hoisted(() => ({ limit: vi.fn() }));
vi.mock("@/lib/supabase/server", () => ({
  apiError: (status: number, code: string, message: string) => Response.json({ error: { code, message } }, { status }),
}));
vi.mock("@opennextjs/cloudflare", () => ({ getCloudflareContext: () => ({ env: { HYGIENE_RATE_LIMITER: { limit } } }) }));
const origin = "https://valora3d.com";
const request = (path: string, body: unknown, headers = {}) => new Request(`${origin}${path}`, {
  method: "POST", headers: { origin, "content-type": "application/json", ...headers }, body: JSON.stringify(body),
});

beforeEach(() => {
  limit.mockResolvedValue({ success: true });
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => { vi.restoreAllMocks(); vi.clearAllMocks(); vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe("private error reporting", () => {
  const REPORT = { kind: "segment", path: "/projects/3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f", name: "TypeError", digest: "123456", release: "abc1234" };
  it("logs only fixed fields (route template, class name, digest, build, browser family); rejects free text", async () => {
    const res = await report(request("/api/client-errors", REPORT, { "user-agent": "Mozilla/5.0 Chrome/140.0 Safari/537.36" }));
    expect(res.status).toBe(204);
    const entry = JSON.parse(vi.mocked(console.error).mock.calls[0][0]);
    expect(entry).toMatchObject({
      level: "error", route: "/api/client-errors", message: "client_error",
      kind: "segment", path: "/projects/[id]", name: "TypeError", code: "123456", release: "abc1234", browser: "chrome",
    });
    expect(entry.requestId).toMatch(/^[0-9a-f-]{36}$/);
    expect((await report(request("/api/client-errors", { ...REPORT, message: "a@example.com secret" }))).status).toBe(400);
    expect((await report(request("/api/client-errors", { event: "global_error" }))).status).toBe(400);
    expect(console.error).toHaveBeenCalledOnce();
  });
  it("rejects cross-origin, oversized streamed bodies, and rate-limited reports", async () => {
    expect((await report(request("/api/client-errors", {}, { origin: "https://evil.com" }))).status).toBe(403);
    expect((await report(request("/api/client-errors", { event: "x".repeat(3000) }))).status).toBe(413);
    limit.mockResolvedValue({ success: false });
    expect((await report(request("/api/client-errors", REPORT))).status).toBe(429);
    expect(console.error).not.toHaveBeenCalled();
  });
  it("does not copy untrusted context fields or non-UUID identifiers", () => {
    log("error", "/api/client-errors", "global_error", { requestId: "email@example.com", userId: "secret" });
    const entry = JSON.parse(vi.mocked(console.error).mock.calls[0][0]);
    expect(entry.userId).toBeUndefined();
    expect(entry.requestId).not.toBe("email@example.com");
  });
});
