"use client";

import { create } from "zustand";
import type { RenderJob } from "@/lib/schema";
import { services, type RenderRequestInput, type ServiceError } from "@/lib/services";
import { useCreditsStore } from "./credits";

/**
 * Render jobs for the open project. They live here, not in RenderPanel, because a render outlives the
 * drawer: closing it unmounts the panel, and a subscription held there would stop following a running job.
 * Job state itself is server-side, so `load` after a reload finds every job again and resumes live ones.
 */

export type RenderOutcome = null | { kind: "not_connected" } | { kind: "error"; error: ServiceError };

const TERMINAL = new Set<RenderJob["status"]>(["COMPLETE", "FAILED", "CANCELLED"]);

type RenderState = {
  projectId: string | null;
  /** Newest first. */
  jobs: RenderJob[];
  loaded: boolean;
  pending: boolean;
  /** The last request's outcome when it did not produce a job. */
  outcome: RenderOutcome;
  load: (projectId: string) => Promise<void>;
  request: (input: RenderRequestInput) => Promise<RenderJob | null>;
  cancel: (jobId: string) => Promise<void>;
  clearOutcome: () => void;
  reset: () => void;
};

const subscriptions = new Map<string, () => void>();

function stopAll() {
  for (const stop of subscriptions.values()) stop();
  subscriptions.clear();
}

const newKey = () => (globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`).replace(/[^A-Za-z0-9_-]/g, "");

export const useRenderStore = create<RenderState>((set, get) => {
  const upsert = (job: RenderJob) => {
    // A straggler for another project (the user moved on) is dropped.
    if (get().projectId !== job.projectId) return;
    set((s) => {
      const i = s.jobs.findIndex((j) => j.id === job.id);
      const jobs = i < 0 ? [job, ...s.jobs] : s.jobs.map((j) => (j.id === job.id ? job : j));
      return { jobs };
    });
    if (TERMINAL.has(job.status)) {
      subscriptions.get(job.id)?.();
      subscriptions.delete(job.id);
      // A failure or early cancel refunded credits; a success may be followed by a plan change. Either way
      // the balance shown should be the server's.
      void useCreditsStore.getState().refresh();
    }
  };

  const follow = (job: RenderJob) => {
    if (TERMINAL.has(job.status) || subscriptions.has(job.id)) return;
    subscriptions.set(job.id, services.render.subscribe(job.id, upsert));
  };

  return {
    projectId: null,
    jobs: [],
    loaded: false,
    pending: false,
    outcome: null,

    load: async (projectId) => {
      if (get().projectId !== projectId) {
        stopAll();
        set({ projectId, jobs: [], loaded: false, outcome: null, pending: false });
      }
      const r = await services.render.list(projectId);
      if (get().projectId !== projectId) return;
      if (!r.ok) {
        set({ loaded: true });
        return;
      }
      set({ jobs: r.value, loaded: true });
      r.value.forEach(follow);
    },

    request: async (input) => {
      if (get().pending) return null;
      const projectId = input.projectId;
      if (get().projectId !== projectId) {
        stopAll();
        set({ projectId, jobs: [], loaded: false });
      }
      set({ pending: true, outcome: null });
      try {
        const r = await services.render.request({ ...input, idempotencyKey: newKey() });
        if (get().projectId !== projectId) return null;
        if (!r.ok) {
          set({ outcome: r.error.code === "not_connected" ? { kind: "not_connected" } : { kind: "error", error: r.error } });
          return null;
        }
        upsert(r.value);
        follow(r.value);
        void useCreditsStore.getState().refresh();
        return r.value;
      } finally {
        if (get().projectId === projectId) set({ pending: false });
      }
    },

    cancel: async (jobId) => {
      const r = await services.render.cancel(jobId);
      if (r.ok) upsert(r.value);
      else set({ outcome: { kind: "error", error: r.error } });
    },

    clearOutcome: () => set({ outcome: null }),

    reset: () => {
      stopAll();
      set({ projectId: null, jobs: [], loaded: false, pending: false, outcome: null });
    },
  };
});
