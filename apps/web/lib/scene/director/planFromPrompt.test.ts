import { describe, it, expect } from "vitest";
import { planFromPrompt } from "./planFromPrompt";
import { ScenePlanSchema } from "@/lib/schema";
import { defaultPlan } from "../defaultPlan";

describe("planFromPrompt", () => {
  it("returns the default for an unknown prompt", () => {
    const p = planFromPrompt("asdf qwerty", "car");
    expect(ScenePlanSchema.safeParse(p).success).toBe(true);
    expect(p.scene.environment).toBe("outdoor_road");
  });
  it("maps a rainy night handheld prompt", () => {
    const p = planFromPrompt("Cinematic rainy night city commercial, handheld camera walking toward the car", "car");
    expect(p.scene.environment).toBe("urban_night");
    expect(p.scene.time).toBe("night");
    expect(p.scene.ground).toBe("wet_asphalt");
    expect(p.effects.rain).toBeGreaterThan(0);
    expect(p.camera.style).toBe("handheld");
    expect(p.shots[0].action).toBe("handheld_walk_toward");
    expect(p.lighting.style).toBe("night_city");
  });
  it("splits two shots 40/60 on a sequence word", () => {
    const p = planFromPrompt("push in on the car, then orbit around it for 10 seconds", "car");
    expect(p.shots.map((s) => [s.start, s.end, s.action])).toEqual([
      [0, 4, "hero_push_in"],
      [4, 10, "slow_orbit"],
    ]);
    expect(ScenePlanSchema.safeParse(p).success).toBe(true);
  });
  it("reads duration and resolution", () => {
    const p = planFromPrompt("studio shot, 15 seconds, 4k", "product");
    expect(p.output.durationS).toBe(15);
    expect(p.output.resolution).toBe("4k");
    expect(p.scene.environment).toBe("studio_black");
  });
  it("does not treat 'train' as rain", () => {
    const p = planFromPrompt("train at the station", "car");
    expect(p.effects.rain).toBe(0);
    expect(p.scene.ground).toBe(planFromPrompt("", "car").scene.ground);
  });
  it("keeps rain inflections: 'raining' and 'rains' set rain", () => {
    expect(planFromPrompt("raining at night", "car").effects.rain).toBe(0.4);
    expect(planFromPrompt("it rains on the road", "car").effects.rain).toBe(0.4);
  });
  it("keeps orbit and circle inflections for shot actions", () => {
    const p = planFromPrompt("orbiting the car, then push in", "car");
    expect(p.shots.map((s) => s.action)).toEqual(["slow_orbit", "hero_push_in"]);
    expect(planFromPrompt("circling the product", "product").shots[0].action).toBe("slow_orbit");
  });
  it("accepts plural streets, roads, highways and cities", () => {
    expect(planFromPrompt("city streets", "car").scene.environment).toBe("urban_night");
    expect(planFromPrompt("through the cities", "car").scene.environment).toBe("urban_night");
    expect(planFromPrompt("studio then roads", "product").scene.environment).toBe("outdoor_road");
    expect(planFromPrompt("studio then highways", "product").scene.environment).toBe("outdoor_road");
  });
  it("accepts 'walking towards'", () => {
    const p = planFromPrompt("walking towards the car, then orbit", "car");
    expect(p.shots.map((s) => s.action)).toEqual(["handheld_walk_toward", "slow_orbit"]);
  });
  it("maps 'white studio' to studio_white", () => {
    const p = planFromPrompt("white studio, slow orbit", "product");
    expect(p.scene.environment).toBe("studio_white");
  });
  it("honours fps and resolution mentions in a first prompt", () => {
    const p = planFromPrompt("studio, 24 fps, 1080p", "product");
    expect(p.output.fps).toBe(24);
    expect(p.output.resolution).toBe("1080p");
    expect(p.output.durationS).toBe(10);
  });
  it("'low' only lowers the camera as an angle, not as light or key", () => {
    const def = defaultPlan("product").camera.heightM;
    expect(planFromPrompt("low light studio", "product").camera.heightM).toBe(def);
    expect(planFromPrompt("low key lighting", "product").camera.heightM).toBe(def);
    expect(planFromPrompt("low angle shot", "product").camera.heightM).toBe(0.5);
    expect(planFromPrompt("low-angle", "product").camera.heightM).toBe(0.5);
    expect(planFromPrompt("shot from below", "product").camera.heightM).toBe(0.5);
  });
  it("'close' means a close-up unless it is the verb 'close the'", () => {
    expect(planFromPrompt("close the door", "product").shots[0].distanceMultiplier).toBe(1);
    expect(planFromPrompt("close up", "product").shots[0].distanceMultiplier).toBe(0.7);
    expect(planFromPrompt("close-up of the badge", "car").shots[0].distanceMultiplier).toBe(0.7);
    expect(planFromPrompt("get close", "car").shots[0].distanceMultiplier).toBe(0.7);
  });
  it("shares vocabulary with edit: downtown is a city, mountain is a road", () => {
    expect(planFromPrompt("downtown at night", "car").scene.environment).toBe("urban_night");
    expect(planFromPrompt("mountain pass", "product").scene.environment).toBe("outdoor_road");
  });
});
