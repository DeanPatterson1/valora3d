import { afterEach, describe, expect, it, vi } from "vitest";
import type { SupabaseClient } from "@supabase/supabase-js";
import { readPublicSupabaseConfig, readServerConfig } from "@/lib/env";
import { isProtectedPath, isSignedOutOnlyPath, safeNextPath } from "@/lib/supabase/proxy";
import { createServices } from "../index";
import { responseToResult } from "../http";
import { SupabaseAuthService } from "./auth";
import { SupabaseCreditService } from "./credits";
import { SupabaseProjectRepository } from "./projectRepository";
import { profileToUser, rowToTransaction, uploadToAsset, type UploadRow } from "./rows";

const CONFIG = { url: "https://example.supabase.co", anonKey: "anon" };

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("env", () => {
  it("needs both public halves", () => {
    expect(readPublicSupabaseConfig({})).toBeNull();
    expect(readPublicSupabaseConfig({ NEXT_PUBLIC_SUPABASE_URL: "u" })).toBeNull();
    expect(readPublicSupabaseConfig({ NEXT_PUBLIC_SUPABASE_URL: " u ", NEXT_PUBLIC_SUPABASE_ANON_KEY: "k" })).toEqual({ url: "u", anonKey: "k" });
  });
  it("fails closed without the service role; R2 only when all four vars exist", () => {
    const pub = { NEXT_PUBLIC_SUPABASE_URL: "u", NEXT_PUBLIC_SUPABASE_ANON_KEY: "k" };
    expect(readServerConfig(pub)).toBeNull();
    expect(readServerConfig({ ...pub, SUPABASE_SERVICE_ROLE_KEY: "s" })?.r2).toBeNull();
    const full = readServerConfig({
      ...pub,
      SUPABASE_SERVICE_ROLE_KEY: "s",
      R2_ACCOUNT_ID: "a",
      R2_BUCKET: "b",
      R2_ACCESS_KEY_ID: "i",
      R2_SECRET_ACCESS_KEY: "x",
    });
    expect(full?.r2).toEqual({ accountId: "a", bucket: "b", accessKeyId: "i", secretAccessKey: "x" });
  });
});

describe("service selection", () => {
  it("uses the local fakes without Supabase config (tests stay hermetic)", () => {
    const s = createServices(null);
    expect(s.backend).toBe("local");
    expect(s.auth.features.guest).toBe(true);
  });
  it("uses Supabase when configured, with no guest mode and no demo providers", () => {
    const s = createServices(CONFIG);
    expect(s.backend).toBe("supabase");
    expect(s.auth).toBeInstanceOf(SupabaseAuthService);
    expect(s.projects).toBeInstanceOf(SupabaseProjectRepository);
    expect(s.credits).toBeInstanceOf(SupabaseCreditService);
    expect(s.auth.features).toEqual({ guest: false, providers: ["google"], passwordReset: true, serverAccount: true });
  });
});

describe("proxy routing rules", () => {
  it("protects app routes only", () => {
    for (const p of ["/projects", "/projects/abc", "/profile", "/settings", "/dev/tokens"]) expect(isProtectedPath(p)).toBe(true);
    for (const p of ["/", "/login", "/signup", "/api/uploads", "/projectsx", "/forgot-password"]) expect(isProtectedPath(p)).toBe(false);
    expect(isSignedOutOnlyPath("/login")).toBe(true);
    expect(isSignedOutOnlyPath("/reset-password")).toBe(false);
  });
  it("only honours same-origin next paths", () => {
    expect(safeNextPath("/projects/1?x=2")).toBe("/projects/1?x=2");
    for (const bad of [null, "", "https://evil.com", "//evil.com", "/\\evil.com", "javascript:alert(1)", "/\t/evil.com", "/\n/evil.com", "/\u0000x"]) {
      expect(safeNextPath(bad)).toBe("/projects");
    }
  });
});

describe("responseToResult", () => {
  const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status });
  it("maps the transport taxonomy", async () => {
    expect(await responseToResult(json(200, { a: 1 }))).toEqual({ ok: true, value: { a: 1 } });
    const r401 = await responseToResult(json(401, {}));
    expect(!r401.ok && r401.error.code).toBe("unauthorized");
    const r429 = await responseToResult(json(429, {}));
    expect(!r429.ok && r429.error.code).toBe("rate_limited");
    const r500 = await responseToResult(json(500, { error: { code: "x", message: "leaky detail" } }));
    expect(!r500.ok && r500.error).toMatchObject({ code: "server" });
    const r402 = await responseToResult(json(402, { error: { code: "insufficient_credits", message: "You need 2 credits but have 1." } }));
    expect(!r402.ok && r402.error).toEqual({ code: "insufficient_credits", message: "You need 2 credits but have 1." });
  });
});

describe("row mappers", () => {
  it("fills a blank profile name from the email and repairs bad prefs", () => {
    const u = profileToUser({ id: "u1", email: "jane.doe@x.com", name: "", avatar_seed: "s", plan: "free", prefs: { defaultOutput: "junk" }, created_at: "2026-09-28T00:00:00Z" });
    expect(u.name).toBe("Jane");
    expect(u.prefs.localAgent).toBe("not_connected");
    expect(u.createdAt).toBe(Date.parse("2026-09-28T00:00:00Z"));
  });
  it("maps ledger reasons, signup grant included", () => {
    expect(rowToTransaction({ id: 7, amount: 50, reason: "signup_grant", project_id: null, created_at: "2026-09-28T00:00:00Z" }).reason).toBe("starting_balance");
    expect(rowToTransaction({ id: 8, amount: 30, reason: "render_refund", project_id: null, created_at: "2026-09-28T00:00:00Z" }).reason).toBe("render_refund");
  });
});

// ---- fakes -------------------------------------------------------------------------------------

type AuthStub = Record<string, ReturnType<typeof vi.fn>>;
function fakeDb(auth: AuthStub, profile: Record<string, unknown> | null = null): () => SupabaseClient {
  const query = {
    select: () => query,
    eq: () => query,
    maybeSingle: async () => ({ data: profile, error: null }),
  };
  const client = { auth, from: () => query } as unknown as SupabaseClient;
  return () => client;
}

const PROFILE = { id: "u1", email: "a@b.co", name: "Ann", avatar_seed: "s", plan: "free", prefs: {}, created_at: "2026-09-28T00:00:00Z" };

describe("SupabaseAuthService", () => {
  const origin = () => "https://valora3d.com";

  it("reports verification_sent when sign-up needs the emailed link, passing the CAPTCHA token to Supabase", async () => {
    const signUp = vi.fn(async () => ({ data: { user: { id: "u1" }, session: null }, error: null }));
    const svc = new SupabaseAuthService(fakeDb({ signUp }), origin);
    const r = await svc.signUp("A@B.co", "password123", "Ann", "challenge");
    expect(!r.ok && r.error.code).toBe("verification_sent");
    expect(signUp).toHaveBeenCalledWith(expect.objectContaining({
      email: "a@b.co",
      options: expect.objectContaining({ emailRedirectTo: "https://valora3d.com/auth/callback?next=/projects", captchaToken: "challenge" }),
    }));
  });

  it("surfaces a refused CAPTCHA on every protected auth call", async () => {
    const refused = vi.fn(async () => ({ data: {}, error: { status: 400, code: "captcha_failed", message: "captcha protection: request disallowed (no-captcha-response)" } }));
    const db = fakeDb({ signUp: refused, signInWithPassword: refused, resetPasswordForEmail: refused });
    const svc = new SupabaseAuthService(db, origin);
    for (const r of [await svc.signUp("a@b.co", "password123", "Ann"), await svc.signIn("a@b.co", "password123"), await svc.requestPasswordReset("a@b.co")]) {
      expect(!r.ok && r.error.code).toBe("verification_failed");
    }
  });

  it("signs in and returns the profile; wrong password is a plain credentials error", async () => {
    const ok = vi.fn(async () => ({ data: { user: { id: "u1" } }, error: null }));
    const signedIn = await new SupabaseAuthService(fakeDb({ signInWithPassword: ok }, PROFILE), origin).signIn("a@b.co", "password123", "challenge");
    expect(signedIn.ok && signedIn.value.name).toBe("Ann");
    expect(ok).toHaveBeenCalledWith({ email: "a@b.co", password: "password123", options: { captchaToken: "challenge" } });
    const bad = vi.fn(async () => ({ data: {}, error: { status: 400, code: "invalid_credentials", message: "Invalid login credentials" } }));
    const r = await new SupabaseAuthService(fakeDb({ signInWithPassword: bad }), origin).signIn("a@b.co", "password123");
    expect(!r.ok && r.error.code).toBe("invalid_credentials");
  });

  it("has no guest mode and refuses Apple", async () => {
    const svc = new SupabaseAuthService(fakeDb({}), origin);
    expect((await svc.continueAsGuest()).ok).toBe(false);
    const apple = await svc.signInWith("apple");
    expect(!apple.ok && apple.error.code).toBe("unsupported");
  });

  it("answers a reset request the same way for unknown emails", async () => {
    const reset = vi.fn(async () => ({ data: {}, error: { status: 400, message: "User not found" } }));
    const svc = new SupabaseAuthService(fakeDb({ resetPasswordForEmail: reset }), origin);
    expect(await svc.requestPasswordReset("nobody@x.co", "challenge")).toEqual({ ok: true, value: undefined });
    expect(reset).toHaveBeenCalledWith("nobody@x.co", { redirectTo: "https://valora3d.com/auth/callback?next=/reset-password", captchaToken: "challenge" });
    // Without a site key there is no widget and no token; local/dev projects run without CAPTCHA.
    await svc.requestPasswordReset("nobody@x.co");
    expect(reset).toHaveBeenLastCalledWith("nobody@x.co", { redirectTo: "https://valora3d.com/auth/callback?next=/reset-password" });
  });

  it("reports reset outages instead of claiming the link was sent", async () => {
    const reset = vi.fn(async () => ({ data: {}, error: { status: 500, message: "boom" } }));
    const r = await new SupabaseAuthService(fakeDb({ resetPasswordForEmail: reset }), origin).requestPasswordReset("a@b.co");
    expect(r.ok).toBe(false);
  });

  it("deletes the account through the server route", async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const signOut = vi.fn(async () => ({ error: null }));
    const r = await new SupabaseAuthService(fakeDb({ signOut }), origin).deleteAllData();
    expect(r.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith("/api/account/delete", expect.objectContaining({ method: "POST" }));
    expect(signOut).toHaveBeenCalled();
  });
});

describe("SupabaseCreditService", () => {
  it("never adds credits from the browser", async () => {
    const svc = new SupabaseCreditService(fakeDb({}));
    const r = await svc.post({ amount: 500, reason: "pack_purchase", projectId: null });
    expect(!r.ok && r.error.code).toBe("checkout_required");
  });

  it("spends through the API with an idempotency ref", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ transaction: { id: 3, amount: -2, reason: "scene_generation", project_id: "p", created_at: "2026-09-28T00:00:00Z" } }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const svc = new SupabaseCreditService(fakeDb({}), () => "ref-12345678");
    const r = await svc.post({ amount: -2, reason: "scene_generation", projectId: "p" });
    expect(r.ok && r.value).toMatchObject({ id: "3", amount: -2, reason: "scene_generation" });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/credits/spend");
    expect(JSON.parse(init.body as string)).toEqual({ reason: "scene_generation", amount: -2, projectId: "p", ref: "ref-12345678" });
  });

  it("surfaces the server's insufficient_credits", async () => {
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify({ error: { code: "insufficient_credits", message: "You need 2 credits but have 1." } }), { status: 402 }),
    ));
    const r = await new SupabaseCreditService(fakeDb({})).post({ amount: -2, reason: "prompt_edit", projectId: null });
    expect(!r.ok && r.error.code).toBe("insufficient_credits");
  });
});

describe("SupabaseProjectRepository uploads", () => {
  const row = (status: UploadRow["status"]): UploadRow => ({
    id: "11111111-2222-3333-4444-555555555555",
    user_id: "u1",
    project_id: "p1",
    source: "upload",
    file_name: "car.glb",
    format: "glb",
    r2_key: "u/u1/11111111-2222-3333-4444-555555555555.glb",
    sample_url: null,
    size_bytes: 4,
    sha256: null,
    status,
    reject_reason: null,
    created_at: "2026-09-28T00:00:00Z",
  });

  it("requests a URL, PUTs the bytes to R2, then completes", async () => {
    const calls: string[] = [];
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push(`${init?.method ?? "GET"} ${url}`);
      if (url === "/api/uploads") return new Response(JSON.stringify({ upload: row("pending"), putUrl: "https://r2.example/put", putHeaders: { "If-None-Match": "*" } }), { status: 201 });
      if (url.startsWith("https://r2.example")) {
        expect(init?.headers).toEqual({ "If-None-Match": "*" });
        return new Response(null, { status: 200 });
      }
      return new Response(JSON.stringify({ upload: row("ready") }), { status: 200 });
    }) as unknown as typeof fetch;
    const repo = new SupabaseProjectRepository(fakeDb({}), fetchImpl);
    const blob = new Blob(["glTF"]);
    const r = await repo.saveAsset(
      { projectId: "p1", fileName: "car.glb", format: "glb", sizeBytes: 4, source: "upload", blobKey: null, sampleUrl: null, thumbnailKey: null },
      blob,
    );
    expect(r.ok && r.value).toMatchObject({ id: row("ready").id, source: "upload", blobKey: row("ready").r2_key });
    expect(calls).toEqual([
      "POST /api/uploads",
      "PUT https://r2.example/put",
      `POST /api/uploads/${row("ready").id}/complete`,
    ]);
  });

  it("surfaces a rejected file", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/uploads") return new Response(JSON.stringify({ upload: row("pending"), putUrl: "https://r2.example/put" }), { status: 201 });
      if (url.startsWith("https://r2.example")) return new Response(null, { status: 200 });
      return new Response(JSON.stringify({ error: { code: "rejected", message: "The file is not a binary glTF (.glb)." } }), { status: 422 });
    }) as unknown as typeof fetch;
    const repo = new SupabaseProjectRepository(fakeDb({}), fetchImpl);
    const r = await repo.saveAsset(
      { projectId: "p1", fileName: "car.glb", format: "glb", sizeBytes: 4, source: "upload", blobKey: null, sampleUrl: null, thumbnailKey: null },
      new Blob(["nope"]),
    );
    expect(!r.ok && r.error).toEqual({ code: "rejected", message: "The file is not a binary glTF (.glb)." });
  });

  it("maps an upload row to an asset", () => {
    expect(uploadToAsset(row("ready"))).toMatchObject({ projectId: "p1", sizeBytes: 4, thumbnailKey: null });
  });
});
