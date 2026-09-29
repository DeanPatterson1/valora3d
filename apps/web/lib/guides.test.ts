import { describe, expect, it } from "vitest";
import { GUIDES } from "./guides";

const onDomain = (url: string, domains: string[]) => {
  const host = new URL(url).hostname;
  return domains.some((d) => host === d || host.endsWith(`.${d}`));
};

describe("export guides", () => {
  it("cites at least one official vendor page for every guide, and only vendor pages", () => {
    for (const g of GUIDES) {
      expect(g.sources.length, g.slug).toBeGreaterThan(0);
      for (const s of g.sources) {
        expect(s.url.startsWith("https://"), s.url).toBe(true);
        expect(onDomain(s.url, g.vendorDomains), `${g.slug}: ${s.url}`).toBe(true);
      }
    }
  });

  it("uses unique slugs, titles and summaries", () => {
    for (const key of ["slug", "title", "summary", "app"] as const) {
      expect(new Set(GUIDES.map((g) => g[key])).size).toBe(GUIDES.length);
    }
    for (const g of GUIDES) expect(g.slug).toBe(`export-glb-from-${g.app.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`);
  });

  it("gives each guide app-specific steps, settings and pitfalls", () => {
    for (const g of GUIDES) {
      expect(g.steps.length, g.slug).toBeGreaterThanOrEqual(4);
      expect(g.settings.length, g.slug).toBeGreaterThan(0);
      expect(g.pitfalls.length, g.slug).toBeGreaterThan(0);
      expect(g.steps.join(" "), g.slug).toMatch(/\.glb|Binary|GLB/);
    }
    // No two guides share a step, apart from the closing checker step.
    const steps = GUIDES.flatMap((g) => g.steps.slice(0, -1));
    expect(new Set(steps).size).toBe(steps.length);
  });

  it("leaves out apps without an official glTF exporter", () => {
    expect(GUIDES.map((g) => g.app)).not.toContain("Maya");
    expect(GUIDES.map((g) => g.app)).not.toContain("Fusion");
  });
});
