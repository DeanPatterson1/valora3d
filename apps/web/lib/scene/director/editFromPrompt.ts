import type { ScenePlan, ScenePatch } from "@/lib/schema";
import { EDIT_STEPS, nextLens, nextDuration } from "../editSteps";

export type EditResult =
  | { ok: true; patches: ScenePatch[] }
  | { ok: false; error: { code: "edit_not_understood" | "at_limit"; message: string; hints?: string[] } };

const HINTS = ['Try: "make it darker"', 'Try: "move the camera closer"', 'Try: "add rain"'];

type Intent = { re: RegExp; make: (p: ScenePlan) => ScenePatch | null | "limit" };

const S = EDIT_STEPS;
const INTENTS: Intent[] = [
  { re: /\b(darker|dimmer)\b/i, make: (p) => (p.lighting.exposure <= -3 ? "limit" : { operation: "update_lighting", exposureDelta: -S.exposureEv }) },
  { re: /\b(brighter|lighter)\b/i, make: (p) => (p.lighting.exposure >= 3 ? "limit" : { operation: "update_lighting", exposureDelta: S.exposureEv }) },
  { re: /\bcloser\b/i, make: (p) => (p.shots.every((s) => s.distanceMultiplier <= 0.4) ? "limit" : { operation: "modify_camera", distanceMultiplier: S.closerMultiplier }) },
  { re: /\b(further|farther|back off)\b/i, make: (p) => (p.shots.every((s) => s.distanceMultiplier >= 2.5) ? "limit" : { operation: "modify_camera", distanceMultiplier: S.furtherMultiplier }) },
  { re: /\blower\b/i, make: (p) => (p.camera.heightM <= 0.2 ? "limit" : { operation: "modify_camera", heightDelta: -S.heightM }) },
  { re: /\bhigher\b/i, make: (p) => (p.camera.heightM >= 3 ? "limit" : { operation: "modify_camera", heightDelta: S.heightM }) },
  { re: /\bwider\b/i, make: (p) => { const l = nextLens(p.camera.lensMm, -1); return l === null ? "limit" : { operation: "modify_camera", lensMm: l }; } },
  { re: /\b(tighter|zoom in)\b/i, make: (p) => { const l = nextLens(p.camera.lensMm, 1); return l === null ? "limit" : { operation: "modify_camera", lensMm: l }; } },
  { re: /\b(add|more) rain\b|\brainy\b/i, make: () => ({ operation: "set_effect", effect: "rain", value: S.effectOn }) },
  { re: /\b(remove|no|less) rain\b/i, make: () => ({ operation: "set_effect", effect: "rain", value: S.effectOff }) },
  { re: /\b(add|more) fog\b|\bfoggy\b/i, make: () => ({ operation: "set_scene", fogDensity: 0.03 }) },
  { re: /\b(remove|no|less) fog\b/i, make: () => ({ operation: "set_scene", fogDensity: 0 }) },
  { re: /\b(remove|no|less) wet (ground|road|street)\b/i, make: () => ({ operation: "set_effect", effect: "wetGround", value: S.effectOff }) },
  { re: /(?<!\b(?:remove|no|less) )\bwet (ground|road|street)\b/i, make: () => ({ operation: "set_effect", effect: "wetGround", value: S.effectOn }) },
  { re: /\bdry (ground|road|street)\b/i, make: () => ({ operation: "set_effect", effect: "wetGround", value: 0 }) },
  { re: /\bmore blur\b/i, make: () => ({ operation: "set_effect", effect: "motionBlur", value: S.effectOn }) },
  { re: /\b(less|no) blur\b/i, make: () => ({ operation: "set_effect", effect: "motionBlur", value: S.effectOff }) },
  { re: /\bhandheld\b/i, make: () => ({ operation: "modify_camera", style: "handheld", motionStrength: 0.18 }) },
  { re: /\b(smooth|steady)\b/i, make: () => ({ operation: "modify_camera", style: "smooth", motionStrength: 0 }) },
  { re: /\brim light on\b/i, make: () => ({ operation: "update_lighting", rim: true }) },
  { re: /\brim light off\b/i, make: () => ({ operation: "update_lighting", rim: false }) },
  { re: /\b(studio white|white studio)\b/i, make: () => ({ operation: "set_scene", environment: "studio_white", ground: "studio_floor" }) },
  { re: /(?<!white )\bstudio\b(?! white)/i, make: () => ({ operation: "set_scene", environment: "studio_black", ground: "studio_floor" }) },
  { re: /\b(cit(y|ies)|urban|streets?)\b/i, make: () => ({ operation: "set_scene", environment: "urban_night" }) },
  { re: /\b(roads?|highways?)\b/i, make: () => ({ operation: "set_scene", environment: "outdoor_road" }) },
  { re: /\bnight\b/i, make: () => ({ operation: "set_scene", time: "night" }) },
  { re: /\b(dusk|sunset)\b/i, make: () => ({ operation: "set_scene", time: "dusk" }) },
  { re: /\bday(time)?\b/i, make: () => ({ operation: "set_scene", time: "day" }) },
  { re: /\borbit\b/i, make: (p) => ({ operation: "set_shot_action", shotId: p.shots[p.shots.length - 1].id, action: "slow_orbit" }) },
  { re: /\bpush[- ]?in\b/i, make: (p) => ({ operation: "set_shot_action", shotId: p.shots[p.shots.length - 1].id, action: "hero_push_in" }) },
  { re: /\btracking\b/i, make: (p) => ({ operation: "set_shot_action", shotId: p.shots[p.shots.length - 1].id, action: "low_tracking" }) },
  { re: /\bwalk toward(s)?\b/i, make: (p) => ({ operation: "set_shot_action", shotId: p.shots[p.shots.length - 1].id, action: "handheld_walk_toward" }) },
  { re: /\blonger\b/i, make: (p) => { const d = nextDuration(p.output.durationS, 1); return d === null ? "limit" : { operation: "set_output", output: { durationS: d as 5 | 10 | 15 | 30 } }; } },
  { re: /\bshorter\b/i, make: (p) => { const d = nextDuration(p.output.durationS, -1); return d === null ? "limit" : { operation: "set_output", output: { durationS: d as 5 | 10 | 15 | 30 } }; } },
  { re: /\b4k\b/i, make: () => ({ operation: "set_output", output: { resolution: "4k" } }) },
  { re: /\b1440p?\b/i, make: () => ({ operation: "set_output", output: { resolution: "1440p" } }) },
  { re: /\b1080p?\b/i, make: () => ({ operation: "set_output", output: { resolution: "1080p" } }) },
  { re: /\b720p?\b/i, make: () => ({ operation: "set_output", output: { resolution: "720p" } }) },
  { re: /\b60 ?fps\b/i, make: () => ({ operation: "set_output", output: { fps: 60 } }) },
  { re: /\b30 ?fps\b/i, make: () => ({ operation: "set_output", output: { fps: 30 } }) },
  { re: /\b24 ?fps\b/i, make: () => ({ operation: "set_output", output: { fps: 24 } }) },
];

export function editFromPrompt(prompt: string, plan: ScenePlan): EditResult {
  const patches: ScenePatch[] = [];
  let matched = 0;
  let limited = 0;
  for (const intent of INTENTS) {
    if (!intent.re.test(prompt)) continue;
    matched++;
    const out = intent.make(plan);
    if (out === "limit") limited++;
    else if (out) patches.push(out);
  }
  if (matched === 0) {
    return { ok: false, error: { code: "edit_not_understood", message: "I didn't catch what to change.", hints: HINTS } };
  }
  if (patches.length === 0 && limited > 0) {
    return { ok: false, error: { code: "at_limit", message: "That's already as far as it goes." } };
  }
  return { ok: true, patches };
}
