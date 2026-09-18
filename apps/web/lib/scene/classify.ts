import type { Category } from "@/lib/schema";
import { sortedExtents } from "./inferUnits";

const CAR_WORDS = /wheel|tire|tyre|headlight|windshield|bumper|brake/i;

export function hasCarNameSignal(objectNames: string[], materialNames: string[]): boolean {
  return [...objectNames, ...materialNames].some((n) => CAR_WORDS.test(n));
}

export function carProportions(metres: [number, number, number]): boolean {
  const [L, M, S] = sortedExtents(metres);
  return L >= 3 && L <= 6 && M >= 1.5 && M <= 2.3 && S >= 1 && S <= 2;
}

export function classify(
  metres: [number, number, number],
  nameSignal: boolean,
): { category: Category; confidence: number } {
  const proportions = carProportions(metres);
  if (!nameSignal && !proportions) return { category: "product", confidence: 0.6 };
  const confidence = Math.min(0.97, 0.5 + (nameSignal ? 0.3 : 0) + (proportions ? 0.2 : 0));
  return { category: "car", confidence };
}
