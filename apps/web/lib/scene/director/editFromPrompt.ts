import type { ScenePlan, ScenePatch } from "@/lib/schema";
import { EDIT_STEPS, nextLens, nextDuration } from "../editSteps";
import { WORDS, SHOT_WORDS, OUTPUT_WORDS, anyOf, after, parseOutputMentions } from "./vocabulary";

export type EditResult =
  | { ok: true; patches: ScenePatch[] }
  | { ok: false; error: { code: "edit_not_understood" | "at_limit"; message: string; hints?: string[] } };

const HINTS = ['Try: "make it darker"', 'Try: "move the camera closer"', 'Try: "add rain"'];

type Intent = { re: RegExp; make: (p: ScenePlan, prompt: string) => ScenePatch | null | "limit" };

const ADD = /\b(?:add|more)/;
const REMOVE = /\b(?:remove|no|less)/;
const lastShot = (p: ScenePlan) => p.shots[p.shots.length - 1].id;

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
  { re: anyOf(after(ADD, WORDS.rain), /\brainy\b/), make: () => ({ operation: "set_effect", effect: "rain", value: S.effectOn }) },
  { re: after(REMOVE, WORDS.rain), make: () => ({ operation: "set_effect", effect: "rain", value: S.effectOff }) },
  { re: anyOf(after(ADD, WORDS.fog), /\bfoggy\b/), make: () => ({ operation: "set_scene", fogDensity: 0.03 }) },
  { re: after(REMOVE, WORDS.fog), make: () => ({ operation: "set_scene", fogDensity: 0 }) },
  { re: /\b(remove|no|less) wet (ground|road|street)\b/i, make: () => ({ operation: "set_effect", effect: "wetGround", value: S.effectOff }) },
  { re: /(?<!\b(?:remove|no|less) )\bwet (ground|road|street)\b/i, make: () => ({ operation: "set_effect", effect: "wetGround", value: S.effectOn }) },
  { re: /\bdry (ground|road|street)\b/i, make: () => ({ operation: "set_effect", effect: "wetGround", value: 0 }) },
  { re: /\bmore blur\b/i, make: () => ({ operation: "set_effect", effect: "motionBlur", value: S.effectOn }) },
  { re: /\b(less|no) blur\b/i, make: () => ({ operation: "set_effect", effect: "motionBlur", value: S.effectOff }) },
  { re: WORDS.handheld, make: () => ({ operation: "modify_camera", style: "handheld", motionStrength: 0.18 }) },
  { re: WORDS.smooth, make: () => ({ operation: "modify_camera", style: "smooth", motionStrength: 0 }) },
  { re: /\brim light on\b/i, make: () => ({ operation: "update_lighting", rim: true }) },
  { re: /\brim light off\b/i, make: () => ({ operation: "update_lighting", rim: false }) },
  { re: WORDS.studio, make: (_p, prompt) => ({ operation: "set_scene", environment: WORDS.studioWhite.test(prompt) ? "studio_white" : "studio_black", ground: "studio_floor" }) },
  { re: WORDS.city, make: () => ({ operation: "set_scene", environment: "urban_night" }) },
  { re: WORDS.road, make: () => ({ operation: "set_scene", environment: "outdoor_road" }) },
  { re: WORDS.night, make: () => ({ operation: "set_scene", time: "night" }) },
  { re: WORDS.dusk, make: () => ({ operation: "set_scene", time: "dusk" }) },
  { re: WORDS.day, make: () => ({ operation: "set_scene", time: "day" }) },
  { re: SHOT_WORDS.orbit, make: (p) => ({ operation: "set_shot_action", shotId: lastShot(p), action: "slow_orbit" }) },
  { re: SHOT_WORDS.pushIn, make: (p) => ({ operation: "set_shot_action", shotId: lastShot(p), action: "hero_push_in" }) },
  { re: SHOT_WORDS.tracking, make: (p) => ({ operation: "set_shot_action", shotId: lastShot(p), action: "low_tracking" }) },
  { re: SHOT_WORDS.walkToward, make: (p) => ({ operation: "set_shot_action", shotId: lastShot(p), action: "handheld_walk_toward" }) },
  { re: /\blonger\b/i, make: (p) => { const d = nextDuration(p.output.durationS, 1); return d === null ? "limit" : { operation: "set_output", output: { durationS: d as 5 | 10 | 15 | 30 } }; } },
  { re: /\bshorter\b/i, make: (p) => { const d = nextDuration(p.output.durationS, -1); return d === null ? "limit" : { operation: "set_output", output: { durationS: d as 5 | 10 | 15 | 30 } }; } },
  { re: anyOf(OUTPUT_WORDS.duration, OUTPUT_WORDS.resolution, OUTPUT_WORDS.fps), make: (_p, prompt) => ({ operation: "set_output", output: parseOutputMentions(prompt) }) },
];

export function editFromPrompt(prompt: string, plan: ScenePlan): EditResult {
  const patches: ScenePatch[] = [];
  let matched = 0;
  let limited = 0;
  for (const intent of INTENTS) {
    if (!intent.re.test(prompt)) continue;
    matched++;
    const out = intent.make(plan, prompt);
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
