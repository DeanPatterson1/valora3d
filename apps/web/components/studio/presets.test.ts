import { describe, expect, it } from "vitest";
import { planFromPrompt } from "@/lib/scene/director/planFromPrompt";
import { PRESETS } from "./presets";

const byId = (id: (typeof PRESETS)[number]["id"]) => PRESETS.find((p) => p.id === id)!;

describe("PRESETS", () => {
  it("has five presets with unique ids", () => {
    expect(PRESETS).toHaveLength(5);
    expect(new Set(PRESETS.map((p) => p.id)).size).toBe(5);
  });

  it("Automotive Commercial → sunset road, two shots (orbit then push in), 10 s", () => {
    const p = planFromPrompt(byId("auto_commercial").prompt, "car");
    expect(p.scene.environment).toBe("outdoor_road");
    expect(p.lighting.style).toBe("sunset");
    expect(p.camera.style).toBe("smooth");
    expect(p.shots.map((s) => s.action)).toEqual(["slow_orbit", "hero_push_in"]);
    expect(p.output.durationS).toBe(10);
  });

  it("Rainy Night → urban night, rain on wet asphalt, handheld walk toward", () => {
    const p = planFromPrompt(byId("rainy_night").prompt, "car");
    expect(p.scene.environment).toBe("urban_night");
    expect(p.scene.time).toBe("night");
    expect(p.scene.ground).toBe("wet_asphalt");
    expect(p.effects.rain).toBeGreaterThan(0);
    expect(p.camera.style).toBe("handheld");
    expect(p.shots[0].action).toBe("handheld_walk_toward");
  });

  it("Luxury Studio → black studio, dramatic light, close orbit", () => {
    const p = planFromPrompt(byId("luxury_studio").prompt, "car");
    expect(p.scene.environment).toBe("studio_black");
    expect(p.lighting.style).toBe("dramatic_three_point");
    expect(p.camera.style).toBe("smooth");
    expect(p.shots[0].action).toBe("slow_orbit");
    expect(p.shots[0].distanceMultiplier).toBeLessThan(1);
  });

  it("Clean Product → white studio, soft light, 8 s orbit", () => {
    const p = planFromPrompt(byId("product_white").prompt, "product");
    expect(p.scene.environment).toBe("studio_white");
    expect(p.lighting.style).toBe("soft_studio");
    expect(p.camera.style).toBe("smooth");
    expect(p.shots[0].action).toBe("slow_orbit");
    expect(p.output.durationS).toBe(8);
  });

  it("Low Tracking → dusk road with a tracking shot", () => {
    const p = planFromPrompt(byId("tracking").prompt, "car");
    expect(p.scene.environment).toBe("outdoor_road");
    expect(p.scene.time).toBe("dusk");
    expect(p.camera.style).toBe("smooth");
    expect(p.shots[0].action).toBe("low_tracking");
  });
});
