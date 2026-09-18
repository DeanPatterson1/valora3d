import type { ScenePlan, ScenePatch } from "@/lib/schema";
import { EDIT_STEPS, nextLens, nextDuration } from "../editSteps";
import { WORDS, SHOT_WORDS, OUTPUT_WORDS, anyOf, after, parseOutputMentions } from "./vocabulary";

export type EditResult =
  | { ok: true; patches: ScenePatch[]; limited?: string[] }
  | { ok: false; error: { code: "edit_not_understood" | "at_limit"; message: string; hints?: string[] } };

const HINTS = ['Try: "make it darker"', 'Try: "move the camera closer"', 'Try: "add rain"'];

type DurationS = ScenePlan["output"]["durationS"];
type Intent = { name: string; re: RegExp; make: (p: ScenePlan, prompt: string) => ScenePatch | "limit" };

const ADD = /\b(?:add|more)/;
const REMOVE = /\b(?:remove|no|less)/;
const lastShot = (p: ScenePlan) => p.shots[p.shots.length - 1].id;

const S = EDIT_STEPS;
const INTENTS: Intent[] = [
  { name: "darker", re: /\b(darker|dimmer)\b/i, make: (p) => (p.lighting.exposure <= -3 ? "limit" : { operation: "update_lighting", exposureDelta: -S.exposureEv }) },
  { name: "brighter", re: /\b(brighter|lighter)\b/i, make: (p) => (p.lighting.exposure >= 3 ? "limit" : { operation: "update_lighting", exposureDelta: S.exposureEv }) },
  { name: "closer", re: /\bcloser\b/i, make: (p) => (p.shots.every((s) => s.distanceMultiplier <= 0.4) ? "limit" : { operation: "modify_camera", distanceMultiplier: S.closerMultiplier }) },
  { name: "further", re: /\b(further|farther|back off)\b/i, make: (p) => (p.shots.every((s) => s.distanceMultiplier >= 2.5) ? "limit" : { operation: "modify_camera", distanceMultiplier: S.furtherMultiplier }) },
  { name: "lower", re: /\blower\b/i, make: (p) => (p.camera.heightM <= 0.2 ? "limit" : { operation: "modify_camera", heightDelta: -S.heightM }) },
  { name: "higher", re: /\bhigher\b/i, make: (p) => (p.camera.heightM >= 3 ? "limit" : { operation: "modify_camera", heightDelta: S.heightM }) },
  { name: "wider", re: /\bwider\b/i, make: (p) => { const l = nextLens(p.camera.lensMm, -1); return l === null ? "limit" : { operation: "modify_camera", lensMm: l }; } },
  { name: "tighter", re: /\b(tighter|zoom in)\b/i, make: (p) => { const l = nextLens(p.camera.lensMm, 1); return l === null ? "limit" : { operation: "modify_camera", lensMm: l }; } },
  { name: "add rain", re: anyOf(after(ADD, WORDS.rain), /\brainy\b/), make: () => ({ operation: "set_effect", effect: "rain", value: S.effectOn }) },
  { name: "remove rain", re: after(REMOVE, WORDS.rain), make: () => ({ operation: "set_effect", effect: "rain", value: S.effectOff }) },
  { name: "add fog", re: anyOf(after(ADD, WORDS.fog), /\bfoggy\b/), make: () => ({ operation: "set_scene", fogDensity: 0.03 }) },
  { name: "remove fog", re: after(REMOVE, WORDS.fog), make: () => ({ operation: "set_scene", fogDensity: 0 }) },
  { name: "remove wet ground", re: /\b(remove|no|less) wet (ground|road|street)\b/i, make: () => ({ operation: "set_effect", effect: "wetGround", value: S.effectOff }) },
  { name: "wet ground", re: /(?<!\b(?:remove|no|less) )\bwet (ground|road|street)\b/i, make: () => ({ operation: "set_effect", effect: "wetGround", value: S.effectOn }) },
  { name: "dry ground", re: /\bdry (ground|road|street)\b/i, make: () => ({ operation: "set_effect", effect: "wetGround", value: 0 }) },
  { name: "more blur", re: /\bmore blur\b/i, make: () => ({ operation: "set_effect", effect: "motionBlur", value: S.effectOn }) },
  { name: "less blur", re: /\b(less|no) blur\b/i, make: () => ({ operation: "set_effect", effect: "motionBlur", value: S.effectOff }) },
  { name: "handheld", re: WORDS.handheld, make: () => ({ operation: "modify_camera", style: "handheld", motionStrength: 0.18 }) },
  { name: "smooth", re: WORDS.smooth, make: () => ({ operation: "modify_camera", style: "smooth", motionStrength: 0 }) },
  { name: "rim light on", re: /\brim light on\b/i, make: () => ({ operation: "update_lighting", rim: true }) },
  { name: "rim light off", re: /\brim light off\b/i, make: () => ({ operation: "update_lighting", rim: false }) },
  { name: "studio", re: WORDS.studio, make: (_p, prompt) => ({ operation: "set_scene", environment: WORDS.studioWhite.test(prompt) ? "studio_white" : "studio_black", ground: "studio_floor" }) },
  { name: "city", re: WORDS.city, make: () => ({ operation: "set_scene", environment: "urban_night" }) },
  { name: "road", re: WORDS.road, make: () => ({ operation: "set_scene", environment: "outdoor_road" }) },
  { name: "night", re: WORDS.night, make: () => ({ operation: "set_scene", time: "night" }) },
  { name: "dusk", re: WORDS.dusk, make: () => ({ operation: "set_scene", time: "dusk" }) },
  { name: "day", re: WORDS.day, make: () => ({ operation: "set_scene", time: "day" }) },
  { name: "orbit", re: SHOT_WORDS.orbit, make: (p) => ({ operation: "set_shot_action", shotId: lastShot(p), action: "slow_orbit" }) },
  { name: "push in", re: SHOT_WORDS.pushIn, make: (p) => ({ operation: "set_shot_action", shotId: lastShot(p), action: "hero_push_in" }) },
  { name: "tracking", re: SHOT_WORDS.tracking, make: (p) => ({ operation: "set_shot_action", shotId: lastShot(p), action: "low_tracking" }) },
  { name: "walk toward", re: SHOT_WORDS.walkToward, make: (p) => ({ operation: "set_shot_action", shotId: lastShot(p), action: "handheld_walk_toward" }) },
  { name: "longer", re: /\blonger\b/i, make: (p) => { const d: DurationS | null = nextDuration(p.output.durationS, 1); return d === null ? "limit" : { operation: "set_output", output: { durationS: d } }; } },
  { name: "shorter", re: /\bshorter\b/i, make: (p) => { const d: DurationS | null = nextDuration(p.output.durationS, -1); return d === null ? "limit" : { operation: "set_output", output: { durationS: d } }; } },
  { name: "output", re: anyOf(OUTPUT_WORDS.duration, OUTPUT_WORDS.resolution, OUTPUT_WORDS.fps), make: (_p, prompt) => ({ operation: "set_output", output: parseOutputMentions(prompt) }) },
];

export function editFromPrompt(prompt: string, plan: ScenePlan): EditResult {
  const patches: ScenePatch[] = [];
  const limited: string[] = [];
  let matched = 0;
  for (const intent of INTENTS) {
    if (!intent.re.test(prompt)) continue;
    matched++;
    const out = intent.make(plan, prompt);
    if (out === "limit") limited.push(intent.name);
    else patches.push(out);
  }
  if (matched === 0) {
    return { ok: false, error: { code: "edit_not_understood", message: "I didn't catch what to change.", hints: HINTS } };
  }
  if (patches.length === 0) {
    return { ok: false, error: { code: "at_limit", message: "That's already as far as it goes." } };
  }
  return limited.length ? { ok: true, patches, limited } : { ok: true, patches };
}
