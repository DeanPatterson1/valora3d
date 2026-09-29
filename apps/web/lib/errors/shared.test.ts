// @vitest-environment node
import { describe, expect, it } from "vitest";
import { ClientErrorReport, cleanReport, uaFamily } from "./shared";

describe("client error reports", () => {
  it("keeps only fixed fields: a route template, a class-like name, a digest-like code", () => {
    const r = ClientErrorReport.parse({
      kind: "segment",
      path: "/projects/3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f?x=1",
      name: "TypeError",
      digest: "1234567",
      release: "abc123",
    });
    expect(cleanReport(r)).toEqual({ kind: "segment", path: "/projects/[id]", name: "TypeError", code: "1234567", release: "abc123" });
    const odd = ClientErrorReport.parse({ kind: "global", path: "/", name: "Cannot read x of y@example.com", digest: "has spaces", release: "a b" });
    expect(cleanReport(odd)).toEqual({ kind: "global", path: "/", name: "Error", code: null, release: "unknown" });
    expect(ClientErrorReport.safeParse({ kind: "global", path: "/", name: "E", release: "r", message: "no" }).success).toBe(false);
  });

  it("buckets browsers into families", () => {
    const chrome = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36";
    expect(uaFamily(chrome)).toBe("chrome");
    expect(uaFamily(`${chrome} Edg/140.0`)).toBe("edge");
    expect(
      uaFamily("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"),
    ).toBe("safari_mobile");
    expect(uaFamily("Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0")).toBe("firefox");
    expect(uaFamily("Googlebot/2.1")).toBe("bot");
    expect(uaFamily(null)).toBe("unknown");
  });
});
