import type { ModelAnalysis } from "@/lib/schema";

const FACTORS: Array<{ unitGuess: ModelAnalysis["unitGuess"]; scaleFactor: number }> = [
  { unitGuess: "m", scaleFactor: 1 },
  { unitGuess: "mm", scaleFactor: 0.001 },
  { unitGuess: "cm", scaleFactor: 0.01 },
  { unitGuess: "in", scaleFactor: 0.0254 },
];

export function sortedExtents(extents: [number, number, number]): [number, number, number] {
  const s = [...extents].sort((a, b) => b - a);
  return [s[0], s[1], s[2]];
}

export function inferUnits(
  extents: [number, number, number],
  carNameSignal: boolean,
): { unitGuess: ModelAnalysis["unitGuess"]; scaleFactor: number } {
  const [L] = sortedExtents(extents);
  const [lo, hi] = carNameSignal ? [3, 6] : [0.1, 12];
  for (const f of FACTORS) {
    const v = L * f.scaleFactor;
    if (v >= lo && v <= hi) return f;
  }
  return { unitGuess: "unknown", scaleFactor: 1 };
}
