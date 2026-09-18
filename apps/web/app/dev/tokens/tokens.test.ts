import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { COLOURS, RADII, SURFACES, TEXT, TYPE_SCALE } from "./tokens";

const css = readFileSync(join(import.meta.dirname, "../../globals.css"), "utf8");

function cssVar(name: string): string {
  const m = css.match(new RegExp(`--${name}:\\s*([^;]+);`));
  if (!m) throw new Error(`--${name} not found in globals.css`);
  return m[1].trim();
}

describe("/dev/tokens mirrors globals.css", () => {
  it("colours", () => {
    for (const t of [...SURFACES, ...TEXT, ...COLOURS]) {
      expect(cssVar(`color-${t.name}`)).toBe(t.hex);
    }
  });
  it("radii", () => {
    for (const r of RADII) expect(cssVar(`radius-${r.name}`)).toBe(`${r.px}px`);
  });
  it("type scale", () => {
    for (const t of TYPE_SCALE) {
      expect(cssVar(`text-${t.name}`)).toBe(`${t.rem}rem`);
      expect(cssVar(`text-${t.name}--line-height`)).toBe(String(t.lh));
    }
  });
});
