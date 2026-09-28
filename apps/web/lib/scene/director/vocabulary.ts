import { nearestDuration, type ScenePlanOutput } from "@/lib/schema";

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
  /** Size words map to the tier that renders nearest: 540p/720p -> Preview, 1080p and above (4K too) -> Final. */
  resolution: /\b(540|720|1080|1440|2160)p?\b|\b[48]k\b|\b(?:uhd|full hd)\b/i,
  vertical: /\bvertical\b|\b9 ?[:x/] ?16\b|\btik ?tok\b|\breels?\b/i,
  landscape: /\blandscape\b|\bhorizontal\b|\bwidescreen\b|\b16 ?[:x/] ?9\b|\byoutube\b/i,
} as const;

/** Case-insensitive union of several regexes. */
export function anyOf(...res: RegExp[]): RegExp {
  return new RegExp(res.map((r) => `(?:${r.source})`).join("|"), "i");
}

/** `prefix` followed by whitespace then `word` (e.g. "add rain"). */
export function after(prefix: RegExp, word: RegExp): RegExp {
  return new RegExp(`${prefix.source}\\s+${word.source}`, "i");
}

/**
 * Length, size and format mentions; only the fields actually mentioned are set. There is no 4K: a size word
 * picks the tier that renders nearest (Final = 1080p). Frame rate is not a choice (the worker decides it).
 */
export function parseOutputMentions(prompt: string): Partial<ScenePlanOutput> {
  const out: Partial<ScenePlanOutput> = {};
  const dur = prompt.match(OUTPUT_WORDS.duration);
  if (dur) {
    const n = Number(dur[1]);
    out.durationS = nearestDuration(n);
  }
  const res = prompt.match(OUTPUT_WORDS.resolution);
  if (res) out.tier = res[1] && Number(res[1]) < 1080 ? "preview" : "final";
  if (OUTPUT_WORDS.vertical.test(prompt)) out.aspect = "9:16";
  else if (OUTPUT_WORDS.landscape.test(prompt)) out.aspect = "16:9";
  return out;
}
