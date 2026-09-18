import type { Category, ScenePlan, Shot } from "@/lib/schema";
import { defaultPlan } from "../defaultPlan";

type Rule = { re: RegExp; apply: (p: ScenePlan, prompt: string) => void };

// Order matters: environment rules run before rain so wet ground can override dry asphalt.
const RULES: Rule[] = [
  { re: /\b(night|2 ?am|midnight)\b/i, apply: (p) => { p.scene.time = "night"; p.lighting.style = "night_city"; p.lighting.practicals = true; } },
  { re: /\b(sunset|golden hour|dusk)\b/i, apply: (p) => { p.scene.time = "dusk"; p.lighting.style = "sunset"; } },
  { re: /\b(overcast|cloudy)\b/i, apply: (p) => { p.lighting.style = "overcast"; } },
  { re: /\b(city|urban|downtown|street)\b/i, apply: (p) => { p.scene.environment = "urban_night"; p.scene.ground = "dry_asphalt"; } },
  { re: /\bstudio\b/i, apply: (p, prompt) => { p.scene.environment = /\bwhite\b/i.test(prompt) ? "studio_white" : "studio_black"; p.scene.ground = "studio_floor"; p.lighting.style = "soft_studio"; } },
  { re: /\b(road|highway|mountain)\b/i, apply: (p) => { p.scene.environment = "outdoor_road"; p.scene.ground = "dry_asphalt"; } },
  { re: /\b(rain|rainy|wet)\b/i, apply: (p, prompt) => { p.effects.rain = /\brain(y)?\b/i.test(prompt) ? 0.4 : 0; p.effects.wetGround = 0.75; if (p.scene.ground === "dry_asphalt") p.scene.ground = "wet_asphalt"; } },
  { re: /\b(fog|foggy|haze|mist)\b/i, apply: (p) => { p.scene.fogDensity = 0.03; } },
  { re: /\b(handheld|hand-held|walking)\b/i, apply: (p) => { p.camera.style = "handheld"; p.camera.motionStrength = 0.18; } },
  { re: /\bcinematic\b/i, apply: (p) => { p.camera.lensMm = 45; p.effects.depthOfField = 0.5; p.lighting.rim = true; } },
  { re: /\bdramatic\b/i, apply: (p) => { p.lighting.style = "dramatic_three_point"; } },
  { re: /\b(close|close-up|closeup)\b/i, apply: (p) => { for (const s of p.shots) s.distanceMultiplier = 0.7; } },
  { re: /\b(low angle|low camera|low)\b/i, apply: (p) => { p.camera.heightM = 0.5; } },
];

const SHOT_WORDS: Array<[RegExp, Shot["action"]]> = [
  [/\b(walk(ing)? toward|approach(es|ing|ed)?)\b/i, "handheld_walk_toward"],
  [/\b(push[- ]?in|dolly in|move closer)\b/i, "hero_push_in"],
  [/\b(track(ing)?|drive by|alongside)\b/i, "low_tracking"],
  [/\b(orbit|circle|around)\b/i, "slow_orbit"],
];

const DURATIONS = [5, 10, 15, 30] as const;

function detectShotActions(prompt: string): Shot["action"][] {
  const seq = prompt.split(/\b(?:then|after that)\b|,\s*(?=then)/i);
  const actions: Shot["action"][] = [];
  for (const part of seq) {
    const hit = SHOT_WORDS.find(([re]) => re.test(part));
    if (hit) actions.push(hit[1]);
  }
  return actions.slice(0, 2);
}

export function planFromPrompt(prompt: string, category: Category): ScenePlan {
  const p = defaultPlan(category);
  for (const rule of RULES) if (rule.re.test(prompt)) rule.apply(p, prompt);

  const dur = prompt.match(/(\d+)\s*(s|sec|seconds?)\b/i);
  if (dur) {
    const n = Number(dur[1]);
    p.output.durationS = DURATIONS.reduce((best, d) => (Math.abs(d - n) < Math.abs(best - n) ? d : best), 10);
  }
  if (/\b4k\b/i.test(prompt)) p.output.resolution = "4k";
  else if (/\b1440p?\b/i.test(prompt)) p.output.resolution = "1440p";
  else if (/\b720p?\b/i.test(prompt)) p.output.resolution = "720p";

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
