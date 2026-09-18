import { create } from "zustand";
import type { ScenePlan } from "@/lib/schema";
import { useStudioStore } from "@/lib/stores/studio";

/**
 * UI-owned labour state (spec 9/10). The store may append a version the moment the
 * director returns; while `labouring` the viewer keeps showing `frozenPlan` and the rail
 * only the first `frozenVersionCount` versions, so the result lands when the labour
 * sequence finishes rather than mid-animation.
 */
type LabourState = {
  labouring: boolean;
  frozenPlan: ScenePlan | null;
  frozenVersionCount: number;
  begin: () => void;
  end: () => void;
};

export const useLabourStore = create<LabourState>((set) => ({
  labouring: false,
  frozenPlan: null,
  frozenVersionCount: 0,
  begin: () => {
    const { currentPlan, versions } = useStudioStore.getState();
    set({ labouring: true, frozenPlan: currentPlan, frozenVersionCount: versions.length });
  },
  end: () => set({ labouring: false, frozenPlan: null, frozenVersionCount: 0 }),
}));

export function useLabour(): LabourState {
  return useLabourStore();
}
