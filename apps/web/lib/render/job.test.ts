import { describe, expect, it } from "vitest";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import type { ScenePlan } from "@/lib/schema";
import { planFromPrompt } from "@/lib/scene/director/planFromPrompt";
import { PRESETS } from "@/components/studio/presets";
import { MAX_FRAMES, buildRenderJob, cameraProgrammeFor, frameCount, presetFor, sceneFor } from "./job";

function plan(over: Partial<ScenePlan> = {}): ScenePlan {
  return { ...defaultPlan("car"), ...over };
}

const withEffects = (rain: number) => plan({ effects: { ...defaultPlan("car").effects, rain } });

const inStudio = (over: Partial<ScenePlan["scene"]> = {}) =>
  plan({ scene: { ...defaultPlan("car").scene, environment: "studio_black", ground: "studio_floor", ...over } });

describe("sceneFor", () => {
  it("sends any rain to the courtyard", () => {
    expect(sceneFor(withEffects(0.4))).toBe("rainy_courtyard");
  });

  it("sends wet ground to the courtyard even without falling rain", () => {
    const damp = plan({ effects: { ...defaultPlan("car").effects, wetGround: 0.5 } });
    expect(sceneFor(damp)).toBe("rainy_courtyard");
  });

  it("sends the default car plan outdoors, not into a studio box", () => {
    // `defaultPlan` is an outdoor road at dusk; the turntable is a grey floor and
    // four lights, which is not what that plan describes.
    expect(sceneFor(defaultPlan("car"))).toBe("rainy_courtyard");
  });

  it("keeps an outdoor night scene outdoors", () => {
    expect(sceneFor(plan({ scene: { ...defaultPlan("car").scene, environment: "urban_night", time: "night" } }))).toBe(
      "rainy_courtyard",
    );
  });

  it("uses the garage only for a studio asked for at night", () => {
    expect(sceneFor(inStudio({ time: "night" }))).toBe("night_garage");
  });

  it("uses the turntable only for a studio asked for by day", () => {
    expect(sceneFor(inStudio({ time: "day" }))).toBe("turntable");
  });

  it("sends a wet studio outdoors, because no studio has weather", () => {
    expect(sceneFor(inStudio({ ground: "wet_asphalt" }))).toBe("rainy_courtyard");
  });
});

describe("cameraProgrammeFor", () => {
  it("hands a handheld courtyard shot to the scene's own operator", () => {
    const handheld = plan({ camera: { ...defaultPlan("car").camera, style: "handheld" } });
    expect(cameraProgrammeFor(handheld)).toBe("film");
  });

  it("hands a walk-toward shot to the operator too", () => {
    const walk = plan({
      shots: [{ id: "a", start: 0, end: 10, action: "handheld_walk_toward", distanceMultiplier: 1 }],
    });
    expect(cameraProgrammeFor(walk)).toBe("film");
  });

  it("traces the viewer's path for a smooth courtyard shot", () => {
    expect(cameraProgrammeFor(defaultPlan("car"))).toBe("plan");
  });

  it("never uses the operator outside the courtyard", () => {
    const handheldStudio = plan({
      scene: { ...defaultPlan("car").scene, environment: "studio_black", ground: "studio_floor" },
      camera: { ...defaultPlan("car").camera, style: "handheld" },
    });
    expect(cameraProgrammeFor(handheldStudio)).toBe("plan");
  });
});

describe("presetFor", () => {
  it("previews the courtyard with the same renderer as the final, just noisier", () => {
    // EEVEE cannot path-trace rain or wet ground, so a draft preview of the courtyard
    // would look nothing like what the final produces.
    const ultra = plan({ output: { ...defaultPlan("car").output, quality: "ultra" } });
    expect(presetFor(ultra, "preview")).toBe("film_preview");
  });

  it("keeps the EEVEE draft for the studio boxes", () => {
    const studio = plan({ scene: { ...defaultPlan("car").scene, environment: "studio_black", ground: "studio_floor" } });
    expect(presetFor(studio, "preview")).toBe("draft");
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

  it("names the camera programme the pipeline should run", () => {
    expect(buildRenderJob("asset-1", defaultPlan("car"), "final").camera_programme).toBe("plan");
  });
});

describe("the prompts the composer offers", () => {
  // The bug this covers: `sceneFor` used to need `effects.rain > 0`, so every preset
  // except the rainy one rendered in a grey studio box regardless of what it asked for.
  const sceneOf = (prompt: string) => sceneFor(planFromPrompt(prompt, "car"));

  it("puts the rainy night preset in the courtyard, handheld", () => {
    const rainy = planFromPrompt(PRESETS[1].prompt, "car");
    expect(sceneFor(rainy)).toBe("rainy_courtyard");
    expect(cameraProgrammeFor(rainy)).toBe("film");
  });

  it("keeps the automotive commercial outdoors", () => {
    expect(sceneOf(PRESETS[0].prompt)).toBe("rainy_courtyard");
  });

  it("keeps the low tracking highway shot outdoors", () => {
    expect(sceneOf(PRESETS[4].prompt)).toBe("rainy_courtyard");
  });

  it("gives the luxury studio preset an actual studio", () => {
    expect(sceneOf(PRESETS[2].prompt)).toBe("turntable");
  });

  it("gives the clean product preset an actual studio", () => {
    expect(sceneOf(PRESETS[3].prompt)).toBe("turntable");
  });
});
