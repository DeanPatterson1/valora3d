import { describe, expect, it } from "vitest";
import { contrast, luminance } from "./contrast";

describe("contrast", () => {
  it("black on white is 21:1", () => {
    expect(contrast("#000000", "#ffffff")).toBeCloseTo(21, 5);
  });
  it("is symmetric", () => {
    expect(contrast("#f2a83b", "#0f0e0c")).toBeCloseTo(contrast("#0f0e0c", "#f2a83b"), 10);
  });
  it("white luminance is 1", () => {
    expect(luminance("#fff")).toBeCloseTo(1, 10);
  });
  it("token text meets 4.5:1 on every surface", () => {
    const surfaces = ["#0f0e0c", "#171512", "#201d19", "#2b2723"];
    for (const bg of surfaces) {
      expect(contrast("#f4f0e9", bg)).toBeGreaterThanOrEqual(4.5);
      expect(contrast("#ada599", bg)).toBeGreaterThanOrEqual(4.5);
    }
  });
});
