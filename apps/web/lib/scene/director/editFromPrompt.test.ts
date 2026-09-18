import { describe, it, expect } from "vitest";
import { editFromPrompt } from "./editFromPrompt";
import { defaultPlan } from "../defaultPlan";

const base = defaultPlan("car");

describe("editFromPrompt", () => {
  it("returns two patches for two intents", () => {
    const r = editFromPrompt("darker and add rain", base);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.patches).toEqual([
      { operation: "update_lighting", exposureDelta: -0.7 },
      { operation: "set_effect", effect: "rain", value: 0.5 },
    ]);
  });
  it("maps closer to a distance multiplier", () => {
    const r = editFromPrompt("move the camera closer", base);
    expect(r.ok && r.patches[0]).toEqual({ operation: "modify_camera", distanceMultiplier: 0.75 });
  });
  it("steps lenses", () => {
    const r = editFromPrompt("tighter lens", base); // base 50 -> 85
    expect(r.ok && r.patches[0]).toEqual({ operation: "modify_camera", lensMm: 85 });
  });
  it("targets the last shot for actions", () => {
    const r = editFromPrompt("orbit instead", base);
    expect(r.ok && r.patches[0]).toEqual({ operation: "set_shot_action", shotId: "shot-1", action: "slow_orbit" });
  });
  it("reports not understood with hints", () => {
    const r = editFromPrompt("make it pop", base);
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.error.code).toBe("edit_not_understood");
    expect(r.error.hints?.length).toBe(3);
  });
  it("reports at_limit when nothing can change", () => {
    const dark = { ...base, lighting: { ...base.lighting, exposure: -3 } };
    const r = editFromPrompt("darker", dark);
    expect(!r.ok && r.error.code).toBe("at_limit");
  });
  it("longer steps duration", () => {
    const r = editFromPrompt("make it longer", base); // 10 -> 15
    expect(r.ok && r.patches[0]).toEqual({ operation: "set_output", output: { durationS: 15 } });
  });
});
