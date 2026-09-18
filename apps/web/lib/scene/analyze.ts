import type { ModelAnalysis, SceneStats } from "@/lib/schema";
import { inferUnits } from "./inferUnits";
import { classify, hasCarNameSignal } from "./classify";
import { capabilitiesFor } from "./capabilities";

const ROLE_PATTERNS: Array<[string, RegExp]> = [
  ["front_left_wheel", /(wheel|tire|tyre).*(fl\b|front.*left|left.*front)|(fl\b|front.*left).*(wheel|tire|tyre)/i],
  ["front_right_wheel", /(wheel|tire|tyre).*(fr\b|front.*right|right.*front)|(fr\b|front.*right).*(wheel|tire|tyre)/i],
  ["rear_left_wheel", /(wheel|tire|tyre).*(rl\b|rear.*left|left.*rear)|(rl\b|rear.*left).*(wheel|tire|tyre)/i],
  ["rear_right_wheel", /(wheel|tire|tyre).*(rr\b|rear.*right|right.*rear)|(rr\b|rear.*right).*(wheel|tire|tyre)/i],
  ["body", /^body$|car_?body|chassis/i],
  ["windshield", /windshield|windscreen/i],
  ["headlight_left", /headlight.*(l\b|left)/i],
  ["headlight_right", /headlight.*(r\b|right)/i],
];

export function detectParts(objectNames: string[]): Record<string, string> {
  const parts: Record<string, string> = {};
  for (const [role, re] of ROLE_PATTERNS) {
    const hit = objectNames.find((n) => re.test(n));
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
