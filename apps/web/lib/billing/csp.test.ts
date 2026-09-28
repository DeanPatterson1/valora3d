import { describe, expect, it } from "vitest";
import nextConfig from "../../next.config";

async function csp(): Promise<Record<string, string>> {
  const rules = await nextConfig.headers!();
  const value = rules[0].headers.find((h) => h.key === "Content-Security-Policy")!.value;
  return Object.fromEntries(value.split(";").map((d) => d.trim().split(/\s+/)).map(([k, ...v]) => [k, v.join(" ")]));
}

describe("CSP allows Paddle checkout", () => {
  it("loads Paddle.js, frames the overlay and talks to Paddle", async () => {
    const p = await csp();
    expect(p["script-src"]).toContain("https://cdn.paddle.com");
    // buy.paddle.com and sandbox-buy.paddle.com host the overlay iframe.
    expect(p["frame-src"]).toContain("https://*.paddle.com");
    expect(p["connect-src"]).toContain("https://*.paddle.com");
    expect(p["frame-ancestors"]).toBe("'none'");
  });
});
