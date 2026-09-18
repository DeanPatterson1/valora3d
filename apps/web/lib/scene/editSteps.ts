export const EDIT_STEPS = {
  exposureEv: 0.7,
  closerMultiplier: 0.75,
  furtherMultiplier: 1.33,
  heightM: 0.3,
  lenses: [24, 35, 50, 85] as const,
  durations: [5, 10, 15, 30] as const,
  effectOn: 0.5,
  effectOff: 0,
} as const;

export function nextLens(current: number, dir: 1 | -1): number | null {
  const L = EDIT_STEPS.lenses;
  const idx = L.findIndex((l) => (dir === 1 ? l > current : l < current));
  if (dir === 1) return idx === -1 ? null : L[idx];
  const lower = L.filter((l) => l < current);
  return lower.length ? lower[lower.length - 1] : null;
}

export function nextDuration(current: number, dir: 1 | -1): number | null {
  const D = EDIT_STEPS.durations;
  const i = D.indexOf(current as (typeof D)[number]);
  const j = i + dir;
  return j < 0 || j >= D.length ? null : D[j];
}
