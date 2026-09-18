import { describe, it, expect } from "vitest";
import { defaultPlan } from "./defaultPlan";
import { ScenePlanSchema } from "@/lib/schema";
import { capabilitiesFor } from "./capabilities";

describe("defaultPlan", () => {
  it("produces valid plans for both categories", () => {
    expect(ScenePlanSchema.safeParse(defaultPlan("car")).success).toBe(true);
    expect(ScenePlanSchema.safeParse(defaultPlan("product")).success).toBe(true);
  });
  it("car defaults to outdoor road, product to studio", () => {
    expect(defaultPlan("car").scene.environment).toBe("outdoor_road");
    expect(defaultPlan("product").scene.environment).toBe("studio_black");
  });
});

describe("capabilitiesFor", () => {
  it("follows the capability table", () => {
    expect(capabilitiesFor("car", 4, false)).toEqual(["drive", "brake", "steer", "wheel_rotation"]);
    expect(capabilitiesFor("car", 2, false)).toEqual(["static", "rotate"]);
    expect(capabilitiesFor("product", 0, true)).toEqual(["rotate", "pedestal", "rigged_motion"]);
  });
});
