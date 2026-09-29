import { describe, expect, it } from "vitest";
import { CREDIT_COSTS } from "@/lib/pricing";
import { applyPatch } from "@/lib/scene/applyPatch";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import { sliderPatches, type SliderKey } from "@/lib/stores/studio";
import { isFreeAdjustment, resolveVersionAction, VERSION_ACTION_COST } from "./versionAction";

describe("version actions", () => {
  it("prices from CREDIT_COSTS", () => {
    expect(VERSION_ACTION_COST).toEqual({ generate: CREDIT_COSTS.scene_generation, edit: CREDIT_COSTS.prompt_edit, adjust: 0 });
  });

  it("makes a project's first version a generation whatever was declared", () => {
    expect(resolveVersionAction("adjust", 0)).toBe("generate");
    expect(resolveVersionAction("edit", 0)).toBe("generate");
    expect(resolveVersionAction("edit", 3)).toBe("edit");
    expect(resolveVersionAction("adjust", 1)).toBe("adjust");
  });
});

describe("isFreeAdjustment", () => {
  const base = defaultPlan("car");

  it.each<[SliderKey, number]>([["handheld", 0.6], ["depthOfField", 0.8], ["motionBlur", 0.4], ["fog", 0.05], ["light", 1.2]])(
    "accepts the %s slider",
    (key, value) => {
      expect(isFreeAdjustment(base, sliderPatches(key, value, base).reduce(applyPatch, base))).toBe(true);
    },
  );

  it("accepts output changes, including a new length that rescales the shots", () => {
    expect(isFreeAdjustment(base, applyPatch(base, { operation: "set_output", output: { tier: "final", aspect: "16:9" } }))).toBe(true);
    const longer = applyPatch(base, { operation: "set_output", output: { durationS: 12 } });
    expect(longer.shots.at(-1)?.end).toBe(12);
    expect(isFreeAdjustment(base, longer)).toBe(true);
  });

  it("refuses anything a prompt edit would change", () => {
    const paid = [
      applyPatch(base, { operation: "set_scene", environment: "urban_night" }),
      applyPatch(base, { operation: "update_lighting", style: "night_city" }),
      applyPatch(base, { operation: "modify_camera", lensMm: 85 }),
      applyPatch(base, { operation: "set_effect", effect: "rain", value: 0.8 }),
      applyPatch(base, { operation: "set_shot_action", shotId: base.shots[0].id, action: "low_tracking" }),
      { ...base, shots: base.shots.map((s) => ({ ...s, distanceMultiplier: 2 })) },
    ];
    for (const p of paid) expect(isFreeAdjustment(base, p)).toBe(false);
  });
});
