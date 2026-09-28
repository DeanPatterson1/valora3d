import { describe, expect, it, vi } from "vitest";
import { readServerConfig } from "@/lib/env";
import { ResendNotifier, noopNotifier, renderReadyEmail } from "./notify";
import { R2Storage } from "./r2";
import { RunpodClient, RunpodError } from "./runpod";
import { hashWebhookToken, newWebhookToken, timingSafeEqualStr, verifyWebhookToken } from "./webhookToken";

describe("webhook token", () => {
  it("is 32 random bytes, stored only as its SHA-256", async () => {
    const a = newWebhookToken();
    const b = newWebhookToken();
    expect(a).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(a).not.toBe(b);
    const hash = await hashWebhookToken(a);
    expect(hash).toMatch(/^[0-9a-f]{64}$/);
    expect(hash).not.toContain(a);
  });

  it("verifies only the matching token", async () => {
    const t = newWebhookToken();
    const hash = await hashWebhookToken(t);
    expect(await verifyWebhookToken(t, hash)).toBe(true);
    expect(await verifyWebhookToken(`${t}x`, hash)).toBe(false);
    expect(await verifyWebhookToken(null, hash)).toBe(false);
    expect(await verifyWebhookToken(t, null)).toBe(false);
    expect(await verifyWebhookToken("x".repeat(300), hash)).toBe(false);
  });

  it("compares strings without an early exit on length", () => {
    expect(timingSafeEqualStr("abc", "abc")).toBe(true);
    expect(timingSafeEqualStr("abc", "abd")).toBe(false);
    expect(timingSafeEqualStr("abc", "ab")).toBe(false);
    expect(timingSafeEqualStr("", "")).toBe(true);
  });
});

describe("RunpodClient", () => {
  const config = { apiKey: "rp-key", endpointId: "ep123" };

  it("submits to /run with the API key and returns the id", async () => {
    const fetchImpl = vi.fn(async () => Response.json({ id: "abc-123", status: "IN_QUEUE" }));
    const c = new RunpodClient(config, fetchImpl as unknown as typeof fetch);
    const body = { input: { job_id: "j", glb_url: "u", output_put_urls: { video: "v", poster: "p" }, params: {} }, webhook: "w", policy: { executionTimeout: 1, ttl: 2 } };
    expect(await c.run(body)).toEqual({ id: "abc-123", status: "IN_QUEUE" });
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("https://api.runpod.ai/v2/ep123/run");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer rp-key");
    expect(JSON.parse(String(init.body))).toEqual(body);
  });

  it("reads /status and /cancel, maps 404 to null and other failures to RunpodError", async () => {
    const responses = [Response.json({ id: "a", status: "IN_PROGRESS" }), new Response("", { status: 404 }), new Response("", { status: 500 }), Response.json({ id: "a", status: "CANCELLED" })];
    const fetchImpl = vi.fn(async () => responses.shift()!);
    const c = new RunpodClient(config, fetchImpl as unknown as typeof fetch);
    expect(await c.status("a")).toEqual({ id: "a", status: "IN_PROGRESS" });
    expect(await c.status("a")).toBeNull();
    await expect(c.status("a")).rejects.toBeInstanceOf(RunpodError);
    expect(await c.cancel("a")).toEqual({ id: "a", status: "CANCELLED" });
    expect((fetchImpl.mock.calls[3] as unknown as [string])[0]).toBe("https://api.runpod.ai/v2/ep123/cancel/a");
  });

  it("refuses an id that could change the path, and a /run answer without an id", async () => {
    const c = new RunpodClient(config, (async () => Response.json({ status: "IN_QUEUE" })) as unknown as typeof fetch);
    await expect(c.status("../x")).rejects.toBeInstanceOf(RunpodError);
    await expect(c.run({ input: { job_id: "j", glb_url: "u", output_put_urls: { video: "v", poster: "p" }, params: {} }, webhook: "w", policy: { executionTimeout: 1, ttl: 1 } })).rejects.toBeInstanceOf(RunpodError);
  });

  it("wraps a network failure", async () => {
    const c = new RunpodClient(config, (async () => {
      throw new TypeError("fetch failed");
    }) as unknown as typeof fetch);
    await expect(c.status("a")).rejects.toThrow(/unreachable/);
  });
});

describe("R2 output URLs", () => {
  const r2 = new R2Storage({ accountId: "acct", bucket: "b", accessKeyId: "id", secretAccessKey: "secret" });

  it("signs the output PUT with its Content-Type, on the R2 host the worker allows", async () => {
    const url = new URL(await r2.presignOutputPut("r/u/j/video.mp4", "video/mp4", 7200));
    expect(url.host).toBe("acct.r2.cloudflarestorage.com");
    expect(url.pathname).toBe("/b/r/u/j/video.mp4");
    expect(url.searchParams.get("X-Amz-Expires")).toBe("7200");
    expect(url.searchParams.get("X-Amz-SignedHeaders")).toContain("content-type");
  });

  it("can sign a plain GET (for the worker) or one with response headers (for the browser)", async () => {
    const plain = new URL(await r2.presignGet("u/x/y.glb", 3600, null));
    expect(plain.searchParams.get("response-content-type")).toBeNull();
    const inline = new URL(await r2.presignGet("r/u/j/video.mp4", 60, { contentType: "video/mp4", disposition: "inline" }));
    expect(inline.searchParams.get("response-content-type")).toBe("video/mp4");
    // The model default is unchanged.
    const model = new URL(await r2.presignGet("u/x/y.glb"));
    expect(model.searchParams.get("response-content-type")).toBe("model/gltf-binary");
  });
});

describe("render-ready mail", () => {
  const ctx = { email: "a@example.com", name: "Ann <b>", projectId: "p1", projectName: "My <car>" };

  it("escapes user text and links to the project", () => {
    const mail = renderReadyEmail(ctx, "https://valora3d.com");
    expect(mail.html).toContain("My &lt;car&gt;");
    expect(mail.html).not.toContain("<car>");
    expect(mail.text).toContain("https://valora3d.com/projects/p1");
  });

  it("sends through Resend with an idempotency key per job", async () => {
    const fetchImpl = vi.fn(async () => Response.json({ id: "m1" }));
    const n = new ResendNotifier({ resendApiKey: "re_key", from: "Valora3D <r@valora3d.com>" }, async () => ctx, fetchImpl as unknown as typeof fetch);
    await n.notifyRenderReady("u1", "job-1");
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("https://api.resend.com/emails");
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer re_key");
    expect(headers["Idempotency-Key"]).toBe("render-ready-job-1");
    expect(JSON.parse(String(init.body))).toMatchObject({ to: ["a@example.com"], subject: "Your render is ready" });
  });

  it("sends nothing without an address, and is a no-op without RESEND_API_KEY", async () => {
    const fetchImpl = vi.fn();
    await new ResendNotifier({ resendApiKey: "k", from: "f" }, async () => null, fetchImpl as unknown as typeof fetch).notifyRenderReady("u", "j");
    expect(fetchImpl).not.toHaveBeenCalled();
    await expect(noopNotifier.notifyRenderReady("u", "j")).resolves.toBeUndefined();
    const base = { NEXT_PUBLIC_SUPABASE_URL: "u", NEXT_PUBLIC_SUPABASE_ANON_KEY: "k", SUPABASE_SERVICE_ROLE_KEY: "s" };
    expect(readServerConfig(base)?.email).toBeNull();
    expect(readServerConfig({ ...base, RESEND_API_KEY: "re" })?.email).toEqual({ resendApiKey: "re", from: "Valora3D <renders@valora3d.com>" });
  });
});

describe("server env for renders", () => {
  const base = { NEXT_PUBLIC_SUPABASE_URL: "u", NEXT_PUBLIC_SUPABASE_ANON_KEY: "k", SUPABASE_SERVICE_ROLE_KEY: "s" };
  it("needs both RunPod values (and a sane endpoint id) to connect the renderer", () => {
    expect(readServerConfig(base)?.runpod).toBeNull();
    expect(readServerConfig({ ...base, RUNPOD_API_KEY: "k" })?.runpod).toBeNull();
    expect(readServerConfig({ ...base, RUNPOD_API_KEY: "k", RUNPOD_ENDPOINT_ID: "a/b" })?.runpod).toBeNull();
    expect(readServerConfig({ ...base, RUNPOD_API_KEY: "k", RUNPOD_ENDPOINT_ID: "ep1" })?.runpod).toEqual({ apiKey: "k", endpointId: "ep1" });
  });
  it("keeps the sweep route closed without a long CRON_SECRET", () => {
    expect(readServerConfig({ ...base, CRON_SECRET: "short" })?.cronSecret).toBeNull();
    expect(readServerConfig({ ...base, CRON_SECRET: "x".repeat(32) })?.cronSecret).toBe("x".repeat(32));
  });
});
