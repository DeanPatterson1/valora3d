"use client";

import { create } from "zustand";
import type { RenderJob } from "@/lib/schema";
import { services, type ServiceError } from "@/lib/services";

/**
 * Render job state.
 *
 * It lives in a store rather than in `RenderPanel` because a render outlives the
 * drawer: closing the drawer unmounts the panel, and a subscription held there would
 * be torn down mid-render, leaving the job running with nothing watching it.
 */

export type Outcome =
  | null
  | { kind: "not_connected" }
  | { kind: "error"; error: ServiceError }
  | { kind: "job"; job: RenderJob };

type RenderState = {
  outcome: Outcome;
  pending: "preview" | "final" | null;
  /** Unsubscribe for the job currently being followed. */
  unsubscribe: (() => void) | null;

  request: (projectId: string, versionId: string, kind: "preview" | "final", target: "local" | "cloud") => Promise<void>;
  reset: () => void;
};

export const useRenderStore = create<RenderState>((set, get) => ({
  outcome: null,
  pending: null,
  unsubscribe: null,

  request: async (projectId, versionId, kind, target) => {
    if (get().pending) return;
    get().unsubscribe?.();
    set({ pending: kind, unsubscribe: null });
    try {
      const result =
        kind === "preview"
          ? await services.render.requestPreview(projectId, versionId)
          : await services.render.requestFinal(projectId, versionId, target);

      if (!result.ok) {
        set({
          outcome:
            result.error.code === "not_connected"
              ? { kind: "not_connected" }
              : { kind: "error", error: result.error },
        });
        return;
      }

      set({ outcome: { kind: "job", job: result.value } });
      const stop = services.render.subscribe(result.value.id, (job) => {
        // A later request may have replaced this job; ignore a straggler update.
        const current = get().outcome;
        if (current?.kind === "job" && current.job.id !== job.id) return;
        set({ outcome: { kind: "job", job } });
      });
      set({ unsubscribe: stop });
    } finally {
      set({ pending: null });
    }
  },

  reset: () => {
    get().unsubscribe?.();
    set({ outcome: null, pending: null, unsubscribe: null });
  },
}));
