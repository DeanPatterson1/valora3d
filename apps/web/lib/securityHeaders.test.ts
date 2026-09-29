import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import nextConfig from "../next.config";
import { goneResponse } from "@/lib/share/public";
import { contentSecurityPolicy, newNonce, r2Origin, R2_WILDCARD, securityHeaders, withSecurityHeaders } from "./securityHeaders";

const ACCOUNT = "0123456789abcdef0123456789abcdef";
const directive = (csp: string, name: string) => csp.split(";").map((d) => d.trim()).find((d) => d.startsWith(`${name} `)) ?? "";

const expectAll = (res: Response) => {
  for (const { key, value } of securityHeaders()) expect(res.headers.get(key), key).toBe(value);
  const csp = res.headers.get("Content-Security-Policy") ?? "";
  const nonce = /'nonce-([^']+)'/.exec(directive(csp, "script-src"))?.[1];
  expect(nonce, "script-src carries a nonce").toBeTruthy();
};

afterEach(() => vi.unstubAllEnvs());

describe("security headers: static list for next.config, nonce CSP from the proxy", () => {
  it("next.config sends exactly the static list on every path, and no CSP (a static CSP cannot carry a nonce)", async () => {
    const rules = await nextConfig.headers!();
    expect(rules).toEqual([{ source: "/:path*", headers: securityHeaders() }]);
    expect(securityHeaders().some((h) => h.key === "Content-Security-Policy")).toBe(false);
  });

  it("the 410 share page gets them", () => {
    const res = withSecurityHeaders(goneResponse("revoked"), contentSecurityPolicy({ nonce: newNonce() }));
    expect(res.status).toBe(410);
    expectAll(res);
    expect(res.headers.get("Cache-Control")).toBe("public, max-age=300");
  });

  it("the proxy's own responses carry them, with a fresh nonce each: the dev 404 rewrite and a local-mode pass-through", async () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "");
    const { proxy } = await import("../proxy");
    const first = await proxy(new NextRequest("https://valora3d.com/admin"));
    expectAll(first);
    const second = await proxy(new NextRequest("https://valora3d.com/admin"));
    expect(second.headers.get("Content-Security-Policy")).not.toBe(first.headers.get("Content-Security-Policy"));
    vi.stubEnv("NODE_ENV", "production");
    const rewritten = await proxy(new NextRequest("https://valora3d.com/dev/components"));
    expect(rewritten.headers.get("x-middleware-rewrite")).toContain("/__not-found");
    expectAll(rewritten);
  });

  it("the nonce reaches the render: the request headers forwarded to Next carry the same CSP and x-nonce", async () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "");
    const { proxy } = await import("../proxy");
    const res = await proxy(new NextRequest("https://valora3d.com/pricing"));
    const csp = res.headers.get("Content-Security-Policy")!;
    const nonce = /'nonce-([^']+)'/.exec(csp)![1];
    expect(res.headers.get("x-middleware-request-x-nonce")).toBe(nonce);
    expect(res.headers.get("x-middleware-request-content-security-policy")).toBe(csp);
  });
});

describe("script-src", () => {
  const prod = contentSecurityPolicy({ nonce: "abc", isDev: false });
  it("has no 'unsafe-inline' (production) and no eval", () => {
    const d = directive(prod, "script-src");
    expect(d).toContain("'nonce-abc'");
    expect(d).toContain("'strict-dynamic'");
    expect(d).not.toContain("'unsafe-inline'");
    expect(d).not.toContain("'unsafe-eval'");
  });
  it("dev adds eval and localhost sockets only", () => {
    const dev = contentSecurityPolicy({ nonce: "abc", isDev: true });
    expect(directive(dev, "script-src")).toContain("'unsafe-eval'");
    expect(directive(dev, "script-src")).not.toContain("'unsafe-inline'");
    expect(directive(dev, "connect-src")).toContain("ws://localhost:*");
    expect(directive(prod, "connect-src")).not.toContain("localhost");
  });
  it("keeps the Paddle, Turnstile and Cloudflare analytics allowances", () => {
    expect(directive(prod, "script-src")).toContain("https://cdn.paddle.com");
    expect(directive(prod, "script-src")).toContain("https://challenges.cloudflare.com");
    expect(directive(prod, "script-src")).toContain("https://static.cloudflareinsights.com");
    expect(directive(prod, "connect-src")).toContain("https://cloudflareinsights.com");
    expect(directive(prod, "frame-src")).toContain("https://challenges.cloudflare.com");
  });
  it("style-src keeps 'unsafe-inline' and no nonce (a nonce would switch it off)", () => {
    const d = directive(prod, "style-src");
    expect(d).toContain("'unsafe-inline'");
    expect(d).not.toContain("nonce");
  });
  it("nonces are unique, base64 and 128 bits", () => {
    const a = newNonce();
    expect(a).not.toBe(newNonce());
    expect(atob(a)).toHaveLength(16);
  });
});

describe("R2 hosts", () => {
  it("are narrowed to the configured account endpoint in img, media and connect", () => {
    const csp = contentSecurityPolicy({ nonce: "n", isDev: false, r2AccountId: ACCOUNT });
    for (const name of ["img-src", "media-src", "connect-src"]) {
      expect(directive(csp, name)).toContain(`https://${ACCOUNT}.r2.cloudflarestorage.com`);
      expect(directive(csp, name)).not.toContain("*.r2.cloudflarestorage.com");
    }
  });
  it("read R2_ACCOUNT_ID from the environment at request time", () => {
    vi.stubEnv("R2_ACCOUNT_ID", ACCOUNT.toUpperCase());
    expect(directive(contentSecurityPolicy({ nonce: "n", isDev: false }), "media-src")).toContain(`https://${ACCOUNT}.r2.cloudflarestorage.com`);
  });
  it("fall back to the wildcard only when unset or not an account id", () => {
    vi.stubEnv("R2_ACCOUNT_ID", "");
    expect(r2Origin()).toBe(R2_WILDCARD);
    expect(r2Origin("not an id; script-src *")).toBe(R2_WILDCARD);
    expect(r2Origin("  ")).toBe(R2_WILDCARD);
  });
});
