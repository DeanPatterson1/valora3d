import type { ScenePlanOutput } from "@/lib/schema";
import { EDIT_STEPS } from "../editSteps";

// Single source of truth for the words both directors understand (spec 6.3), so
// planFromPrompt and editFromPrompt cannot drift apart.
export const WORDS = {
  night: /\b(night|2 ?am|midnight)\b/i,
  dusk: /\b(sunset|golden hour|dusk)\b/i,
  day: /\bday(time)?\b/i,
  city: /\b(cit(y|ies)|urban|downtown|streets?)\b/i,
  road: /\b(roads?|highways?|mountain)\b/i,
  rain: /\b(rain|rainy|raining|rains)\b/i,
  fog: /\b(fog|foggy|haze|mist)\b/i,
  studioWhite: /\b(studio white|white studio)\b/i,
  studio: /\bstudio\b/i,
  handheld: /\b(handheld|hand-held)\b/i,
  smooth: /\b(smooth|steady)\b/i,
} as const;

export const SHOT_WORDS = {
  walkToward: /\b(walk(ing)? toward(s)?|approach(es|ing|ed)?)\b/i,
  pushIn: /\b(push[- ]?in|dolly in|move closer)\b/i,
  tracking: /\b(track(ing)?|drive by|alongside)\b/i,
  orbit: /\b(orbit(ing)?|circl(e|ing)|around)\b/i,
} as const;

export const OUTPUT_WORDS = {
  duration: /(\d+)\s*(s|sec|seconds?)\b/i,
  resolution: /\b(720|1080|1440)p?\b|\b4k\b/i,
  fps: /\b(24|30|60) ?fps\b/i,
} as const;

/** Case-insensitive union of several regexes. */
export function anyOf(...res: RegExp[]): RegExp {
  return new RegExp(res.map((r) => `(?:${r.source})`).join("|"), "i");
}

/** `prefix` followed by whitespace then `word` (e.g. "add rain"). */
export function after(prefix: RegExp, word: RegExp): RegExp {
  return new RegExp(`${prefix.source}\\s+${word.source}`, "i");
}

/** Duration, resolution and fps mentions; only the fields actually mentioned are set. */
export function parseOutputMentions(prompt: string): Partial<ScenePlanOutput> {
  const out: Partial<ScenePlanOutput> = {};
  const dur = prompt.match(OUTPUT_WORDS.duration);
  if (dur) {
    const n = Number(dur[1]);
    out.durationS = EDIT_STEPS.durations.reduce<ScenePlanOutput["durationS"]>(
      (best, d) => (Math.abs(d - n) < Math.abs(best - n) ? d : best),
      10,
    );
  }
  const res = prompt.match(OUTPUT_WORDS.resolution);
  if (res) out.resolution = res[1] ? (`${res[1]}p` as ScenePlanOutput["resolution"]) : "4k";
  const fps = prompt.match(OUTPUT_WORDS.fps);
  if (fps) out.fps = Number(fps[1]) as ScenePlanOutput["fps"];
  return out;
}
