import { describe, it, expect } from "vitest";
import { ScenePlanSchema } from "./scene-plan";

const valid = {
  scene: { environment: "urban_night", time: "night", ground: "wet_asphalt", fogDensity: 0.025 },
  subject: { category: "car", position: [0, 0, 0], motion: "stationary" },
  camera: { style: "handheld", lensMm: 45, heightM: 1.45, motionStrength: 0.18 },
  shots: [
    { id: "s1", start: 0, end: 4, action: "handheld_walk_toward", distanceMultiplier: 1 },
    { id: "s2", start: 4, end: 10, action: "slow_orbit", distanceMultiplier: 1 },
  ],
  lighting: { style: "night_city", exposure: 0, rim: true, practicals: true },
  effects: { rain: 0.4, wetGround: 0.75, motionBlur: 0.18, depthOfField: 0.5 },
  output: { fps: 30, durationS: 10, resolution: "1080p", quality: "high" },
};

describe("ScenePlanSchema", () => {
  it("accepts a valid plan", () => {
    expect(ScenePlanSchema.safeParse(valid).success).toBe(true);
  });
  it("rejects unknown resolution", () => {
    expect(ScenePlanSchema.safeParse({ ...valid, output: { ...valid.output, resolution: "1920x1080" } }).success).toBe(false);
  });
  it("rejects shots that do not end at durationS", () => {
    expect(ScenePlanSchema.safeParse({ ...valid, output: { ...valid.output, durationS: 15 } }).success).toBe(false);
  });
  it("rejects non-contiguous shots", () => {
    expect(ScenePlanSchema.safeParse({ ...valid, shots: [{ ...valid.shots[0], end: 3 }, valid.shots[1]] }).success).toBe(false);
  });
  it("rejects more than two shots", () => {
    const bad = { ...valid, shots: [{ ...valid.shots[0], end: 2 }, { ...valid.shots[0], id: "x", start: 2, end: 4 }, valid.shots[1]] };
    expect(ScenePlanSchema.safeParse(bad).success).toBe(false);
  });
});
