import type { ModelAnalysis, SceneStats } from "@/lib/schema";
import { inferUnits } from "./inferUnits";
import { classify, hasCarNameSignal } from "./classify";
import { capabilitiesFor } from "./capabilities";

const WHEEL = /(wheel|tire|tyre)/i;

// Spec 6.2: wheel roles from names *containing* FL|FR|RL|RR (any non-letter separator,
// so FL_Wheel, wheel.FL and Wheel_FL all count) or spelled-out front/rear + left/right.
function codeRe(code: string): RegExp {
  return new RegExp("(^|[^a-z])" + code + "([^a-z]|$)", "i");
}

function wheel(code: string, ...spelled: RegExp[]): (name: string) => boolean {
  const re = codeRe(code);
  return (name) => WHEEL.test(name) && (re.test(name) || spelled.some((s) => s.test(name)));
}

const ROLE_PATTERNS: Array<[string, (name: string) => boolean]> = [
  ["front_left_wheel", wheel("fl", /front.*left/i, /left.*front/i)],
  ["front_right_wheel", wheel("fr", /front.*right/i, /right.*front/i)],
  ["rear_left_wheel", wheel("rl", /rear.*left/i, /left.*rear/i)],
  ["rear_right_wheel", wheel("rr", /rear.*right/i, /right.*rear/i)],
  // "Body", "Body.001", "Body_Main" but not "Bodywork".
  ["body", (n) => /^body(\b|[._-])|car_?body|chassis/i.test(n)],
  ["windshield", (n) => /windshield|windscreen/i.test(n)],
  ["headlight_left", (n) => /headlight.*(l\b|left)/i.test(n)],
  ["headlight_right", (n) => /headlight.*(r\b|right)/i.test(n)],
];

export function detectParts(objectNames: string[]): Record<string, string> {
  const parts: Record<string, string> = {};
  for (const [role, matches] of ROLE_PATTERNS) {
    const hit = objectNames.find(matches);
    if (hit) parts[role] = hit;
  }
  return parts;
}

export function analyzeStats(stats: SceneStats): ModelAnalysis {
  const nameSignal = hasCarNameSignal(stats.objectNames, stats.materialNames);
  const units = inferUnits(stats.extents, nameSignal);
  const metres = stats.extents.map((e) => +(e * units.scaleFactor).toFixed(3)) as [number, number, number];
  const { category, confidence } = classify(metres, nameSignal);
  const parts = category === "car" ? detectParts(stats.objectNames) : {};
  const wheelCount = Object.keys(parts).filter((k) => k.endsWith("_wheel")).length;
  const rigged = stats.hasSkeleton;
  return {
    category,
    confidence,
    unitGuess: units.unitGuess,
    scaleFactor: units.scaleFactor,
    dimensionsMeters: metres,
    parts,
    capabilities: capabilitiesFor(category, wheelCount, rigged),
    rigged,
  };
}
