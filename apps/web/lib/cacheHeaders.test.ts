import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/** public/_headers as { pathPattern: { header: value } }. */
function parseHeaders(text: string): Record<string, Record<string, string>> {
  const rules: Record<string, Record<string, string>> = {};
  let current: Record<string, string> | null = null;
  for (const raw of text.split("\n")) {
    if (!raw.trim() || raw.trim().startsWith("#")) continue;
    if (!/^\s/.test(raw)) {
      current = rules[raw.trim()] = {};
    } else if (current) {
      const i = raw.indexOf(":");
      current[raw.slice(0, i).trim().toLowerCase()] = raw.slice(i + 1).trim();
    }
  }
  return rules;
}

const rules = parseHeaders(readFileSync(join(import.meta.dirname, "..", "public", "_headers"), "utf8"));

describe("static asset caching (public/_headers, applied by Cloudflare Workers Assets)", () => {
  it("caches hashed build output forever", () => {
    expect(rules["/_next/static/*"]["cache-control"]).toBe("public, max-age=31536000, immutable");
  });

  it("caches unhashed media for a week with stale-while-revalidate, never immutable", () => {
    for (const path of ["/landing/*", "/samples/*", "/hdri/*", "/icons/*"]) {
      const cc = rules[path]?.["cache-control"];
      expect(cc, path).toContain("max-age=604800");
      expect(cc, path).toContain("stale-while-revalidate");
      expect(cc, path).not.toContain("immutable");
    }
  });

  it("never caches pages or API responses here (those come from the Worker)", () => {
    for (const path of Object.keys(rules)) {
      if (!rules[path]["cache-control"]) continue;
      expect(path).toMatch(/^\/(_next\/static|landing|samples|hdri|icons)\//);
    }
  });
});
