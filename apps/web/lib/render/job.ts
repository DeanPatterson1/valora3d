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

/**
 * Which camera the pipeline runs.
 *
 * `film` is the rain scene's own five-shot operator: a simulated human walking in,
 * with footfalls, reframes and a rack-focus macro. It is a large part of why that
 * scene reads as cinematic, so a handheld plan hands over to it rather than trying to
 * reproduce it. `plan` traces the path drawn in the viewer.
 */
export type CameraProgramme = "film" | "plan";

export type RenderJobRequest = {
  schema: 1;
  car: string;
  parts: string[];
  paint: { hex: string; finish: string };
  scene: RenderScene;
  preset: RenderPreset;
  aspect: "16:9" | "9:16";
  camera_programme: CameraProgramme;
  plan: ScenePlan;
};

/**
 * Picking the Blender scene.
 *
 * The courtyard is the only built environment there is — HDRI sky, wet asphalt,
 * trees, weather and a full film grade. The turntable and night garage are bare
 * studio boxes: a floor and a few area lights. So anything set outdoors belongs in
 * the courtyard, and only a plan that explicitly asks for a studio gets one.
 */
export function sceneFor(plan: ScenePlan): RenderScene {
  const { environment, ground } = plan.scene;
  const studio = environment === "studio_black" || environment === "studio_white";
  const wet = plan.effects.rain > 0 || plan.effects.wetGround > 0 || ground === "wet_asphalt";

  // Weather has nowhere else to go.
  if (wet) return "rainy_courtyard";
  if (!studio) return "rainy_courtyard";
  return plan.scene.time === "night" ? "night_garage" : "turntable";
}

/**
 * A handheld plan in the courtyard hands the camera to that scene's own operator.
 * Everywhere else the viewer's path is traced, so the video is the shot that was
 * previewed.
 */
export function cameraProgrammeFor(plan: ScenePlan): CameraProgramme {
  if (sceneFor(plan) !== "rainy_courtyard") return "plan";
  const handheld = plan.camera.style === "handheld" || plan.shots.some((s) => s.action === "handheld_walk_toward");
  return handheld ? "film" : "plan";
}

const QUALITY_PRESET: Record<ScenePlan["output"]["quality"], RenderPreset> = {
  draft: "draft",
  standard: "film_preview",
  high: "film_final",
  ultra: "cinematic",
};

/**
 * A preview is the same renderer as the final, at fewer samples and 720p — a noisier
 * version of the real thing. The EEVEE draft is kept only for the studio boxes, where
 * there is no path-traced rain or wet ground for it to get wrong.
 */
export function presetFor(plan: ScenePlan, kind: "preview" | "final"): RenderPreset {
  if (kind === "final") return QUALITY_PRESET[plan.output.quality];
  return sceneFor(plan) === "rainy_courtyard" ? "film_preview" : "draft";
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
    camera_programme: cameraProgrammeFor(plan),
    plan,
  };
}
