import { describe, expect, it } from "vitest";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import type { ScenePlan } from "@/lib/schema";
import { MAX_FRAMES, buildRenderJob, frameCount, presetFor, sceneFor } from "./job";

function plan(over: Partial<ScenePlan> = {}): ScenePlan {
  return { ...defaultPlan("car"), ...over };
}

const withEffects = (rain: number) => plan({ effects: { ...defaultPlan("car").effects, rain } });
const at = (time: ScenePlan["scene"]["time"]) => plan({ scene: { ...defaultPlan("car").scene, time } });

describe("sceneFor", () => {
  it("sends any rain to the courtyard", () => {
    expect(sceneFor(withEffects(0.4))).toBe("rainy_courtyard");
  });

  it("prefers rain over the time of day", () => {
    const wet = plan({
      effects: { ...defaultPlan("car").effects, rain: 1 },
      scene: { ...defaultPlan("car").scene, time: "night" },
    });
    expect(sceneFor(wet)).toBe("rainy_courtyard");
  });

  it("sends a dry night to the garage", () => {
    expect(sceneFor(at("night"))).toBe("night_garage");
  });

  it("sends an urban night scene to the garage", () => {
    expect(sceneFor(plan({ scene: { ...defaultPlan("car").scene, environment: "urban_night" } }))).toBe("night_garage");
  });

  it("sends everything else to the turntable", () => {
    expect(sceneFor(at("day"))).toBe("turntable");
  });
});

describe("presetFor", () => {
  it("keeps a preview cheap whatever the plan asks for", () => {
    const ultra = plan({ output: { ...defaultPlan("car").output, quality: "ultra" } });
    expect(presetFor(ultra, "preview")).toBe("draft");
  });

  it("climbs the ladder with quality", () => {
    const at = (quality: ScenePlan["output"]["quality"]) =>
      presetFor(plan({ output: { ...defaultPlan("car").output, quality } }), "final");
    expect(at("draft")).toBe("draft");
    expect(at("standard")).toBe("film_preview");
    expect(at("high")).toBe("film_final");
    expect(at("ultra")).toBe("cinematic");
  });
});

describe("frameCount", () => {
  it("is duration times frame rate", () => {
    const ten = plan({ output: { ...defaultPlan("car").output, durationS: 10, fps: 30 } });
    expect(frameCount(ten)).toBe(300);
  });

  it("stays inside the cap for every preset at the default plan", () => {
    const base = defaultPlan("car");
    expect(frameCount(base)).toBeLessThanOrEqual(MAX_FRAMES[presetFor(base, "final")]);
  });
});

describe("buildRenderJob", () => {
  it("carries the plan through untouched", () => {
    const source = plan();
    expect(buildRenderJob("asset-1", source, "final").plan).toBe(source);
  });

  it("names the asset, not a catalogue car", () => {
    expect(buildRenderJob("asset-1", plan(), "final").car).toBe("asset-1");
  });

  it("asks for schema 1, which is what the server validates", () => {
    expect(buildRenderJob("asset-1", plan(), "final").schema).toBe(1);
  });
});
