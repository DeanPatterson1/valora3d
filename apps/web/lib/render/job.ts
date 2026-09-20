import type { ScenePlan } from "@/lib/schema";

/**
 * Turning a directed scene into a render job.
 *
 * The studio's `ScenePlan` is the source of truth for what the video looks like: it
 * carries the shots, the lens, the effects and the output settings, and the server
 * reads them back off `job.plan`. The preset is only the quality ladder — which
 * engine, how many samples, whether the result is watermarked.
 */

/** Blender scenes the pipeline can build. */
export type RenderScene = "rainy_courtyard" | "turntable" | "night_garage";

/** Quality ladder, in ascending cost. Mirrors `jobs.PRESETS`. */
export type RenderPreset = "smoke" | "draft" | "film_preview" | "film_final" | "cinematic";

export type RenderJobRequest = {
  schema: 1;
  car: string;
  parts: string[];
  paint: { hex: string; finish: string };
  scene: RenderScene;
  preset: RenderPreset;
  aspect: "16:9" | "9:16";
  plan: ScenePlan;
};

/**
 * Rain is what makes a scene the courtyard: it is the only scene with weather, and by
 * far the most expensive. Otherwise night goes to the garage and everything else to
 * the studio turntable.
 */
export function sceneFor(plan: ScenePlan): RenderScene {
  if (plan.effects.rain > 0) return "rainy_courtyard";
  if (plan.scene.time === "night" || plan.scene.environment === "urban_night") return "night_garage";
  return "turntable";
}

const QUALITY_PRESET: Record<ScenePlan["output"]["quality"], RenderPreset> = {
  draft: "draft",
  standard: "film_preview",
  high: "film_final",
  ultra: "cinematic",
};

/** A preview is always the cheap EEVEE pass, whatever quality the plan asks for. */
export function presetFor(plan: ScenePlan, kind: "preview" | "final"): RenderPreset {
  return kind === "preview" ? "draft" : QUALITY_PRESET[plan.output.quality];
}

/**
 * Frames the pipeline will render. The server caps this per preset, so the UI can say
 * so before spending the upload.
 */
export function frameCount(plan: ScenePlan): number {
  return plan.output.durationS * plan.output.fps;
}

/** Mirrors `jobs.MAX_FRAMES`; kept here so the UI can refuse before uploading a GLB. */
export const MAX_FRAMES: Record<RenderPreset, number> = {
  smoke: 24,
  draft: 300,
  film_preview: 450,
  film_final: 900,
  cinematic: 900,
};

export function buildRenderJob(assetId: string, plan: ScenePlan, kind: "preview" | "final"): RenderJobRequest {
  return {
    schema: 1,
    // Only an identifier for the pipeline's own bookkeeping; the geometry and its
    // materials all travel in the snapshot.
    car: assetId,
    parts: [],
    paint: { hex: "#ffffff", finish: "gloss" },
    scene: sceneFor(plan),
    preset: presetFor(plan, kind),
    aspect: "16:9",
    plan,
  };
}
