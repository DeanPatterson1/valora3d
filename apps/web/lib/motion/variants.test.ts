import { describe, expect, it } from "vitest";
import type { Variants } from "motion/react";
import { fadeRise, reduced, staggerList } from "./variants";

describe("reduced", () => {
  it("strips transforms and keeps opacity and transition", () => {
    const r = reduced(fadeRise);
    expect(r.hidden).toEqual({ opacity: 0 });
    expect(r.visible).toMatchObject({ opacity: 1 });
    expect(r.visible).not.toHaveProperty("y");
    expect(r.visible).toHaveProperty("transition");
  });

  it("strips x as well as y", () => {
    const slide: Variants = { hidden: { opacity: 0, x: 24 }, exit: { opacity: 0, x: 24 } };
    const r = reduced(slide);
    expect(r.hidden).toEqual({ opacity: 0 });
    expect(r.exit).not.toHaveProperty("x");
  });

  it("leaves transform-free variants unchanged in shape", () => {
    expect(reduced(staggerList)).toEqual(staggerList);
  });

  it("does not mutate the input", () => {
    reduced(fadeRise);
    expect(fadeRise.hidden).toHaveProperty("y", 12);
  });
});
