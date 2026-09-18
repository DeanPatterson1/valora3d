import { describe, expect, it } from "vitest";
import { contrast, luminance } from "./contrast";
import { COLOURS, SURFACES, TEXT } from "./tokens";

describe("contrast", () => {
  it("black on white is 21:1", () => {
    expect(contrast("#000000", "#ffffff")).toBeCloseTo(21, 5);
  });
  it("is symmetric", () => {
    expect(contrast("#ffffff", "#0d0d0d")).toBeCloseTo(contrast("#0d0d0d", "#ffffff"), 10);
  });
  it("white luminance is 1", () => {
    expect(luminance("#fff")).toBeCloseTo(1, 10);
  });
  it("token text meets 4.5:1 on every surface (bg-0..3)", () => {
    // tokens.ts mirrors globals.css (tokens.test.ts fails on drift), so this covers the real palette.
    expect(SURFACES.map((s) => s.name)).toEqual(["bg-0", "bg-1", "bg-2", "bg-3"]);
    expect(TEXT.map((t) => t.name)).toEqual(["fg", "fg-muted"]);
    for (const text of TEXT) {
      for (const surface of SURFACES) {
        expect(contrast(text.hex, surface.hex), `${text.name} on ${surface.name}`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it("primary-fg on the primary button and danger text on panels meet 4.5:1", () => {
    const primary = COLOURS.find((c) => c.name === "primary")!;
    const primaryFg = COLOURS.find((c) => c.name === "primary-fg")!;
    const danger = COLOURS.find((c) => c.name === "danger")!;
    expect(contrast(primaryFg.hex, primary.hex)).toBeGreaterThanOrEqual(4.5);
    for (const surface of SURFACES) expect(contrast(danger.hex, surface.hex), `danger on ${surface.name}`).toBeGreaterThanOrEqual(4.5);
  });
});
