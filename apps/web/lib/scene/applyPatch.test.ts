import { describe, it, expect } from "vitest";
import { applyPatch } from "./applyPatch";
import { defaultPlan } from "./defaultPlan";
import { ScenePlanSchema } from "@/lib/schema";

const base = defaultPlan("car");
const two = {
  ...base,
  shots: [
    { id: "a", start: 0, end: 4, action: "hero_push_in" as const, distanceMultiplier: 1 },
    { id: "b", start: 4, end: 10, action: "slow_orbit" as const, distanceMultiplier: 1 },
  ],
};

describe("applyPatch", () => {
  it("does not mutate the input", () => {
    const copy = structuredClone(base);
    applyPatch(base, { operation: "set_effect", effect: "rain", value: 0.5 });
    expect(base).toEqual(copy);
  });
  it("clamps exposure to schema range", () => {
    const p = applyPatch(base, { operation: "update_lighting", exposureDelta: -10 });
    expect(p.lighting.exposure).toBe(-3);
  });
  it("multiplies distance and clamps", () => {
    let p = applyPatch(base, { operation: "modify_camera", distanceMultiplier: 0.75 });
    expect(p.shots[0].distanceMultiplier).toBeCloseTo(0.75);
    p = applyPatch(p, { operation: "modify_camera", distanceMultiplier: 0.1 });
    expect(p.shots[0].distanceMultiplier).toBe(0.4);
  });
  it("rescales shots when duration changes", () => {
    const p = applyPatch(two, { operation: "set_output", output: { durationS: 8 } });
    expect(p.shots.map((s) => [s.start, s.end])).toEqual([[0, 3.2], [3.2, 8]]);
    expect(ScenePlanSchema.safeParse(p).success).toBe(true);
  });
  it("modify_camera with a shotId changes only that shot's distance", () => {
    const p = applyPatch(two, { operation: "modify_camera", shotId: "b", distanceMultiplier: 0.5 });
    expect(p.shots.map((s) => s.distanceMultiplier)).toEqual([1, 0.5]);
  });
  it("set_shot_action with an unknown id is a no-op", () => {
    const p = applyPatch(base, { operation: "set_shot_action", shotId: "nope", action: "low_tracking" });
    expect(p).toEqual(base);
  });
  it("set_output with only a tier / format does not rescale shots", () => {
    const p = applyPatch(two, { operation: "set_output", output: { tier: "final", aspect: "16:9" } });
    expect(p.shots).toEqual(two.shots);
    expect(p.output).toEqual({ durationS: 10, tier: "final", aspect: "16:9" });
  });
  it("upscaling 10 -> 12 keeps two shots contiguous and ending at the new duration", () => {
    const p = applyPatch(two, { operation: "set_output", output: { durationS: 12 } });
    expect(p.shots.map((s) => [s.start, s.end])).toEqual([[0, 4.8], [4.8, 12]]);
    expect(ScenePlanSchema.safeParse(p).success).toBe(true);
  });
  it("ignores an explicit undefined durationS in set_output", () => {
    const p = applyPatch(base, { operation: "set_output", output: { durationS: undefined, tier: "final" } });
    expect(p.shots).toEqual(base.shots);
    expect(p.output.durationS).toBe(10);
    expect(p.output.tier).toBe("final");
    expect(ScenePlanSchema.safeParse(p).success).toBe(true);
  });
  it("sets scene fields and clamps fog", () => {
    const p = applyPatch(base, { operation: "set_scene", time: "night", fogDensity: 0.5 });
    expect(p.scene.time).toBe("night");
    expect(p.scene.fogDensity).toBe(0.1);
  });
  it("targets a specific shot for action", () => {
    const p = applyPatch(base, { operation: "set_shot_action", shotId: "shot-1", action: "low_tracking" });
    expect(p.shots[0].action).toBe("low_tracking");
  });
  it("always returns a schema-valid plan", () => {
    const p = applyPatch(base, {
      operation: "modify_camera",
      lensMm: 500,
      heightDelta: 99,
      motionStrength: 3,
      style: "handheld",
    });
    expect(ScenePlanSchema.safeParse(p).success).toBe(true);
    expect(p.camera.lensMm).toBe(135);
  });
});
