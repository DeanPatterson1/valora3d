import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import nextConfig from "../next.config";
import { goneResponse } from "@/lib/share/public";
import { securityHeaders, withSecurityHeaders } from "./securityHeaders";

const expectAll = (res: Response) => {
  for (const { key, value } of securityHeaders()) expect(res.headers.get(key), key).toBe(value);
};

afterEach(() => vi.unstubAllEnvs());

describe("security headers: one list for next.config and the proxy", () => {
  it("next.config sends exactly the shared list on every path", async () => {
    const rules = await nextConfig.headers!();
    expect(rules).toEqual([{ source: "/:path*", headers: securityHeaders() }]);
  });

  it("the 410 share page gets them", () => {
    const res = withSecurityHeaders(goneResponse("revoked"));
    expect(res.status).toBe(410);
    expectAll(res);
    expect(res.headers.get("Cache-Control")).toBe("public, max-age=300");
  });

  it("the proxy's own responses carry them: the dev 404 rewrite and a local-mode admin pass-through", async () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "");
    const { proxy } = await import("../proxy");
    expectAll(await proxy(new NextRequest("https://valora3d.com/admin")));
    vi.stubEnv("NODE_ENV", "production");
    const rewritten = await proxy(new NextRequest("https://valora3d.com/dev/components"));
    expect(rewritten.headers.get("x-middleware-rewrite")).toContain("/__not-found");
    for (const { key } of securityHeaders()) expect(rewritten.headers.get(key), key).not.toBeNull();
  });
});
