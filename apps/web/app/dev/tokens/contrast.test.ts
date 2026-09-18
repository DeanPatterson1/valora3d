import { describe, expect, it } from "vitest";
import { contrast, luminance } from "./contrast";

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
  it("token text meets 4.5:1 on every surface", () => {
    const surfaces = ["#0d0d0d", "#171717", "#212121", "#2f2f2f"];
    for (const bg of surfaces) {
      expect(contrast("#ececec", bg)).toBeGreaterThanOrEqual(4.5);
      expect(contrast("#b4b4b4", bg)).toBeGreaterThanOrEqual(4.5);
    }
  });
});
