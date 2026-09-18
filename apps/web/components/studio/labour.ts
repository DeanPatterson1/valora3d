/**
 * Labour illusion (spec 10): analysis and planning show named steps for at least
 * LABOUR_MIN_MS in total, however fast the fake services return.
 */
export const LABOUR_MIN_MS = 1200;

export const ANALYSIS_STEPS = ["Reading geometry", "Measuring dimensions", "Identifying parts", "Checking capabilities"];
export const PLANNING_STEPS = ["Reading your prompt", "Choosing environment", "Choosing lens and camera path", "Setting lights and effects"];

export type ScheduledStep = { label: string; at: number };

/** Spaces `labels` evenly from 0 across `minMs`, so the last step reveals before the minimum elapses. */
export function scheduleSteps(labels: readonly string[], minMs = LABOUR_MIN_MS): ScheduledStep[] {
  if (labels.length === 0) return [];
  const gap = minMs / labels.length;
  return labels.map((label, i) => ({ label, at: Math.round(i * gap) }));
}
