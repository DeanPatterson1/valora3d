import { describe, it, expect } from "vitest";
import { applyPatch } from "./applyPatch";
import { defaultPlan } from "./defaultPlan";
import { ScenePlanSchema } from "@/lib/schema";

const base = defaultPlan("car");

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
    const two = {
      ...base,
      shots: [
        { id: "a", start: 0, end: 4, action: "hero_push_in" as const, distanceMultiplier: 1 },
        { id: "b", start: 4, end: 10, action: "slow_orbit" as const, distanceMultiplier: 1 },
      ],
    };
    const p = applyPatch(two, { operation: "set_output", output: { durationS: 5 } });
    expect(p.shots.map((s) => [s.start, s.end])).toEqual([[0, 2], [2, 5]]);
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
