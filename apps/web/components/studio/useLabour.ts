import { create } from "zustand";
import type { ModelAnalysis, ScenePlan } from "@/lib/schema";
import { useStudioStore } from "@/lib/stores/studio";

/**
 * UI-owned labour state (spec 9/10). The store may append a version (or an analysis)
 * the moment a fake service returns; while `labouring` the viewer keeps showing
 * `frozenPlan`, the analysis panel `frozenAnalysis` and the rail only the first
 * `frozenVersionCount` versions, so the result lands when the labour sequence
 * finishes rather than mid-animation.
 *
 * `planning` is the prompt dock's sequence: set by `beginPlanning`, marked done by
 * `planningDone`, cleared by `end`. Any surface that appends a version behind the
 * planning steps (prompt submit, start over, "Use this scene") goes through it.
 */
type LabourState = {
  labouring: boolean;
  frozenPlan: ScenePlan | null;
  frozenAnalysis: ModelAnalysis | null;
  frozenVersionCount: number;
  /** Non-null while the planning sequence should show in the dock. */
  planning: { done: boolean } | null;
  begin: () => void;
  beginPlanning: () => void;
  planningDone: () => void;
  end: () => void;
};

const snapshot = () => {
  const { currentPlan, analysis, versions } = useStudioStore.getState();
  return { labouring: true, frozenPlan: currentPlan, frozenAnalysis: analysis, frozenVersionCount: versions.length };
};

export const useLabourStore = create<LabourState>((set) => ({
  labouring: false,
  frozenPlan: null,
  frozenAnalysis: null,
  frozenVersionCount: 0,
  planning: null,
  begin: () => set(snapshot()),
  beginPlanning: () => set({ ...snapshot(), planning: { done: false } }),
  planningDone: () => set((s) => (s.planning ? { planning: { done: true } } : {})),
  end: () => set({ labouring: false, frozenPlan: null, frozenAnalysis: null, frozenVersionCount: 0, planning: null }),
}));

export function useLabour(): LabourState {
  return useLabourStore();
}

/**
 * Runs `work` behind the dock's planning sequence: begins labour synchronously
 * (Doherty: feedback before any await), marks the sequence done when the store call
 * resolves. `end()` is the dock's job, from `LabourSequence.onDone`.
 */
export async function runPlanning<T>(work: () => Promise<T>): Promise<T> {
  const { beginPlanning, planningDone } = useLabourStore.getState();
  beginPlanning();
  try {
    return await work();
  } finally {
    planningDone();
  }
}
