import { CREDIT_COSTS } from "@/lib/pricing";
import type { ScenePlan } from "@/lib/schema";

/**
 * What saving a scene version does, and so what it costs. The browser declares one; the server prices it
 * (`public.scene_action_cost`, mirrored here) and overrides it where the project says otherwise:
 *   generate  a new scene from a prompt (also every project's first version)   CREDIT_COSTS.scene_generation
 *   edit      a prompt edit of an existing version                              CREDIT_COSTS.prompt_edit
 *   adjust    a slider / output change of an existing version (free)            CREDIT_COSTS.slider_change
 */
export const VERSION_ACTIONS = ["generate", "edit", "adjust"] as const;
export type VersionAction = (typeof VERSION_ACTIONS)[number];

export const VERSION_ACTION_COST: Record<VersionAction, number> = {
  generate: CREDIT_COSTS.scene_generation,
  edit: CREDIT_COSTS.prompt_edit,
  adjust: CREDIT_COSTS.slider_change,
};

export const VERSION_ACTION_REASON: Record<VersionAction, "scene_generation" | "prompt_edit" | null> = {
  generate: "scene_generation",
  edit: "prompt_edit",
  adjust: null,
};

/** Versions one user may save per rolling hour. Mirrored by `public.scene_version_hourly_cap()`. */
export const VERSION_HOURLY_CAP = 120;

/** The action a save really is: a project's first version is always a generation (mirrors save_scene_version). */
export function resolveVersionAction(declared: VersionAction, existingVersions: number): VersionAction {
  return existingVersions === 0 ? "generate" : declared;
}

/**
 * True when `next` differs from `parent` only in what the free controls change: the handheld slider (camera style
 * and motion strength), depth of field, motion blur, fog, exposure, and the output (length, tier, aspect; a new
 * length rescales the shot timings). Anything else is a paid edit, so a free "adjust" cannot smuggle one in.
 */
export function isFreeAdjustment(parent: ScenePlan, next: ScenePlan): boolean {
  const strip = (p: ScenePlan) => ({
    ...p,
    scene: { ...p.scene, fogDensity: 0 },
    camera: { ...p.camera, style: "smooth", motionStrength: 0 },
    lighting: { ...p.lighting, exposure: 0 },
    effects: { ...p.effects, motionBlur: 0, depthOfField: 0 },
    shots: p.shots.map((s) => ({ ...s, start: 0, end: 0 })),
    output: null,
  });
  return stableJson(strip(parent)) === stableJson(strip(next));
}

function stableJson(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(stableJson).join(",")}]`;
  if (v && typeof v === "object") {
    const o = v as Record<string, unknown>;
    return `{${Object.keys(o).filter((k) => o[k] !== undefined).sort().map((k) => `${JSON.stringify(k)}:${stableJson(o[k])}`).join(",")}}`;
  }
  return JSON.stringify(v);
}
