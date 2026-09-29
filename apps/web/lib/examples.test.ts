import { describe, expect, it } from "vitest";
import { EXAMPLES, EXAMPLES_UPLOAD_DATE, exampleText, exampleVideoSchema, relatedExamples, wordCount } from "./examples";
import { WORLD_IDS } from "./render/worlds";
import manifest from "@/public/landing/gallery/manifest.json";

/**
 * Brand and maker names that must not appear in example copy. Built from the gallery manifest: the car makes and
 * models its file names and licensed-car clips stand for, and the organizations named in its credits (those stay in
 * the credit line, which is shown as-is, but not in our own copy).
 */
const DENYLIST = [
  "porsche", "gt3", "gt3rs", "911", "manthey", "mclaren", "720s",
  "microsoft", "khronos", "poly haven", "eames", "herman miller", "leica", "rolex",
];

describe("example pages", () => {
  it("has an entry for every clip in the gallery manifest, and nothing else", () => {
    const clips = manifest.map((item) => item.video).sort();
    expect(EXAMPLES.map((e) => e.video).sort()).toEqual(clips);
  });

  it("gives every example at least 150 words of its own copy", () => {
    for (const e of EXAMPLES) expect(wordCount(exampleText(e)), e.slug).toBeGreaterThanOrEqual(150);
  });

  it("uses unique slugs, titles and descriptions", () => {
    for (const key of ["slug", "title", "description"] as const) {
      expect(new Set(EXAMPLES.map((e) => e[key])).size).toBe(EXAMPLES.length);
    }
    for (const e of EXAMPLES) expect(e.slug).toMatch(/^[a-z0-9]+(-[a-z0-9]+)*$/);
  });

  it("names no car or product brands in the copy, slug or the prompt it shows", () => {
    for (const e of EXAMPLES) {
      const text = [e.slug, e.title, e.description, exampleText(e), e.item.prompt, e.item.caption].join(" ").toLowerCase();
      for (const word of DENYLIST) expect(text, `${e.slug}: ${word}`).not.toMatch(new RegExp(`(^|[^a-z0-9])${word}([^a-z0-9]|$)`));
    }
  });

  it("uses worlds that exist and real durations", () => {
    for (const e of EXAMPLES) {
      expect(WORLD_IDS).toContain(e.world);
      expect(e.durationSeconds).toBeGreaterThan(0);
    }
  });

  it("describes each clip as a VideoObject with absolute media URLs and a fixed upload date", () => {
    for (const e of EXAMPLES) {
      const s = exampleVideoSchema(e) as Record<string, unknown>;
      expect(s["@type"]).toBe("VideoObject");
      expect(s.contentUrl).toBe(`https://valora3d.com/landing/gallery/${e.video}`);
      expect(s.uploadDate).toBe(EXAMPLES_UPLOAD_DATE);
      expect(s.duration).toBe(`PT${e.durationSeconds}S`);
      expect(JSON.stringify(s)).not.toMatch(/aggregateRating|interactionStatistic/);
    }
  });

  it("links related examples, never the page itself", () => {
    for (const e of EXAMPLES) {
      const related = relatedExamples(e);
      expect(related).toHaveLength(3);
      expect(related.map((r) => r.slug)).not.toContain(e.slug);
    }
  });
});
