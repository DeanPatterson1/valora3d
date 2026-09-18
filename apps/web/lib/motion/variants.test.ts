import { describe, expect, it } from "vitest";
import { fadeRise, panelSlide, reduced, staggerList } from "./variants";

describe("reduced", () => {
  it("strips transforms and keeps opacity and transition", () => {
    const r = reduced(fadeRise);
    expect(r.hidden).toEqual({ opacity: 0 });
    expect(r.visible).toMatchObject({ opacity: 1 });
    expect(r.visible).not.toHaveProperty("y");
    expect(r.visible).toHaveProperty("transition");
  });

  it("strips x from panelSlide", () => {
    const r = reduced(panelSlide);
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
