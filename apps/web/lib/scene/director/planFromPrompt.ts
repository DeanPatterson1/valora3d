import type { Category, ScenePlan, Shot } from "@/lib/schema";
import { defaultPlan } from "../defaultPlan";
import { WORDS, SHOT_WORDS, anyOf, parseOutputMentions } from "./vocabulary";

type Rule = { re: RegExp; apply: (p: ScenePlan, prompt: string) => void };

// Order matters: environment rules run before wet/rain so wet ground can override dry asphalt.
const RULES: Rule[] = [
  { re: WORDS.night, apply: (p) => { p.scene.time = "night"; p.lighting.style = "night_city"; p.lighting.practicals = true; } },
  { re: WORDS.dusk, apply: (p) => { p.scene.time = "dusk"; p.lighting.style = "sunset"; } },
  { re: /\b(overcast|cloudy)\b/i, apply: (p) => { p.lighting.style = "overcast"; } },
  { re: WORDS.city, apply: (p) => { p.scene.environment = "urban_night"; p.scene.ground = "dry_asphalt"; } },
  { re: WORDS.studio, apply: (p, prompt) => { p.scene.environment = WORDS.studioWhite.test(prompt) ? "studio_white" : "studio_black"; p.scene.ground = "studio_floor"; p.lighting.style = "soft_studio"; } },
  { re: WORDS.road, apply: (p) => { p.scene.environment = "outdoor_road"; p.scene.ground = "dry_asphalt"; } },
  { re: /\bwet\b/i, apply: (p) => { p.effects.wetGround = 0.75; if (p.scene.ground === "dry_asphalt") p.scene.ground = "wet_asphalt"; } },
  { re: WORDS.rain, apply: (p) => { p.effects.rain = 0.4; p.effects.wetGround = 0.75; if (p.scene.ground === "dry_asphalt") p.scene.ground = "wet_asphalt"; } },
  { re: WORDS.fog, apply: (p) => { p.scene.fogDensity = 0.03; } },
  { re: anyOf(WORDS.handheld, /\bwalking\b/), apply: (p) => { p.camera.style = "handheld"; p.camera.motionStrength = 0.18; } },
  { re: /\bcinematic\b/i, apply: (p) => { p.camera.lensMm = 45; p.effects.depthOfField = 0.5; p.lighting.rim = true; } },
  { re: /\bdramatic\b/i, apply: (p) => { p.lighting.style = "dramatic_three_point"; } },
  // "close up" / "close-up" / bare "close", but not the verb in "close the door".
  { re: /\bclose(-| )?up\b|\bclose\b(?! the)/i, apply: (p) => { for (const s of p.shots) s.distanceMultiplier = 0.7; } },
  // Only camera placement: "low angle", not "low light" or "low key".
  { re: /\blow[- ](angle|camera|shot)\b|\bfrom below\b/i, apply: (p) => { p.camera.heightM = 0.5; } },
];

const SHOT_ACTIONS: Array<[RegExp, Shot["action"]]> = [
  [SHOT_WORDS.walkToward, "handheld_walk_toward"],
  [SHOT_WORDS.pushIn, "hero_push_in"],
  [SHOT_WORDS.tracking, "low_tracking"],
  [SHOT_WORDS.orbit, "slow_orbit"],
];

function detectShotActions(prompt: string): Shot["action"][] {
  const seq = prompt.split(/\b(?:then|after that)\b/i);
  const actions: Shot["action"][] = [];
  for (const part of seq) {
    const hit = SHOT_ACTIONS.find(([re]) => re.test(part));
    if (hit) actions.push(hit[1]);
  }
  return actions.slice(0, 2);
}

export function planFromPrompt(prompt: string, category: Category): ScenePlan {
  const p = defaultPlan(category);
  for (const rule of RULES) if (rule.re.test(prompt)) rule.apply(p, prompt);
  p.output = { ...p.output, ...parseOutputMentions(prompt) };

  const actions = detectShotActions(prompt);
  const D = p.output.durationS;
  const dm = p.shots[0].distanceMultiplier;
  if (actions.length === 2) {
    p.shots = [
      { id: "shot-1", start: 0, end: D * 0.4, action: actions[0], distanceMultiplier: dm },
      { id: "shot-2", start: D * 0.4, end: D, action: actions[1], distanceMultiplier: dm },
    ];
  } else {
    p.shots = [
      {
        id: "shot-1",
        start: 0,
        end: D,
        action: actions[0] ?? (p.camera.style === "handheld" ? "handheld_walk_toward" : "slow_orbit"),
        distanceMultiplier: dm,
      },
    ];
  }
  return p;
}
