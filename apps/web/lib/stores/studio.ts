import { create } from "zustand";
import { services, type Result, type ServiceError, type Warning } from "@/lib/services";
import { CREDIT_COSTS } from "@/lib/pricing";
import { applyPatch } from "@/lib/scene/applyPatch";
import type { Asset, ModelAnalysis, Project, ScenePatch, ScenePlan, SceneStats, SceneVersion } from "@/lib/schema";

export type SliderKey = "handheld" | "depthOfField" | "motionBlur" | "fog" | "light";
export type ModelInput = { fileName: string; format: Asset["format"]; sizeBytes: number; source: Asset["source"]; sampleUrl: string | null; blob: Blob | null };
export type Busy = null | "loading" | "analyzing" | "planning" | "editing";

type StudioState = {
  project: Project | null;
  asset: Asset | null;
  blobMissing: boolean;
  stats: SceneStats | null;
  analysis: ModelAnalysis | null;
  versions: SceneVersion[];
  selectedVersionId: string | null;
  /** current plan = selected version's plan, or the live slider preview */
  currentPlan: ScenePlan | null;
  pendingWarning: (Warning & { plan: ScenePlan; prompt: string }) | null;
  busy: Busy;
  error: ServiceError | null;
  notFound: boolean;

  reset: () => void;
  open: (projectId: string) => Promise<void>;
  modelLoaded: (input: ModelInput, stats: SceneStats) => Promise<Result<Asset>>;
  submitPrompt: (prompt: string) => Promise<Result<SceneVersion | null>>;
  startOver: (prompt: string) => Promise<Result<SceneVersion | null>>;
  acceptPending: () => Promise<Result<SceneVersion | null>>;
  dismissPending: () => void;
  previewSlider: (key: SliderKey, value: number) => void;
  commitSlider: (key: SliderKey, value: number) => Promise<Result<SceneVersion | null>>;
  commitOutput: (output: Partial<ScenePlan["output"]>) => Promise<Result<SceneVersion | null>>;
  selectVersion: (id: string) => Promise<void>;
  clearError: () => void;
};

const initial = { project: null, asset: null, blobMissing: false, stats: null, analysis: null, versions: [], selectedVersionId: null,
  currentPlan: null, pendingWarning: null, busy: null as Busy, error: null, notFound: false };

const BUSY_ERROR: ServiceError = { code: "busy", message: "Hold on, still working on the last change." };

export function sliderPatches(key: SliderKey, value: number, plan: ScenePlan): ScenePatch[] {
  switch (key) {
    case "handheld": return [{ operation: "modify_camera", motionStrength: value, style: value > 0.15 ? "handheld" : "smooth" }];
    case "depthOfField": return [{ operation: "set_effect", effect: "depthOfField", value }];
    case "motionBlur": return [{ operation: "set_effect", effect: "motionBlur", value }];
    case "fog": return [{ operation: "set_scene", fogDensity: value }];
    case "light": return [{ operation: "update_lighting", exposureDelta: value - plan.lighting.exposure }];
  }
}

export const useStudioStore = create<StudioState>((set, get) => {
  const selectedPlan = () => {
    const { versions, selectedVersionId } = get();
    return versions.find((v) => v.id === selectedVersionId)?.plan ?? null;
  };

  /** Runs `fn` inside the busy window; a second call while busy is refused so a double click cannot create two versions or two charges. */
  const guarded = async <T>(kind: Exclude<Busy, null>, fn: () => Promise<Result<T>>): Promise<Result<T>> => {
    if (get().busy) return { ok: false, error: BUSY_ERROR };
    set({ busy: kind, error: null });
    try {
      const r = await fn();
      if (!r.ok) set({ error: r.error });
      return r;
    } finally {
      set({ busy: null });
    }
  };

  const append = async (prompt: string, plan: ScenePlan, cost: number, reason: "scene_generation" | "prompt_edit" | null): Promise<Result<SceneVersion | null>> => {
    const { project, selectedVersionId } = get();
    if (!project) return { ok: false, error: { code: "no_project", message: "No project open." } };
    if (cost > 0) {
      const b = await services.credits.balance();
      if (!b.ok) return b;
      if (b.value < cost) return { ok: false, error: { code: "insufficient_credits", message: `You need ${cost} credits but have ${b.value}.` } };
    }
    const v = await services.projects.appendVersion({ projectId: project.id, prompt, parentId: selectedVersionId, plan });
    if (!v.ok) return v;
    if (cost > 0 && reason) {
      // Charge only once the version exists; if the debit itself fails the version is kept and the error surfaced.
      const c = await services.credits.post({ amount: -cost, reason, projectId: project.id });
      if (!c.ok) set({ error: c.error });
    }
    await services.projects.updateProject(project.id, { selectedVersionId: v.value.id });
    set((s) => ({ versions: [...s.versions, v.value], selectedVersionId: v.value.id, currentPlan: plan, pendingWarning: null }));
    return v;
  };

  const planFresh = (prompt: string): Promise<Result<SceneVersion | null>> => guarded("planning", async () => {
    const { analysis } = get();
    if (!analysis) return { ok: false, error: { code: "no_model", message: "Load a model first." } };
    const r = await services.director.plan(prompt, analysis);
    if (!r.ok) return r;
    const warning = r.warnings?.[0];
    if (warning) { set({ pendingWarning: { ...warning, plan: r.value, prompt } }); return { ok: true, value: null, warnings: r.warnings }; }
    return append(prompt, r.value, CREDIT_COSTS.scene_generation, "scene_generation");
  });

  return {
    ...initial,
    reset: () => set({ ...initial }),
    clearError: () => set({ error: null }),

    open: async (projectId) => {
      set({ ...initial, busy: "loading" });
      const p = await services.projects.getProject(projectId);
      if (!p.ok) { set({ notFound: true, busy: null }); return; }
      const vs = await services.projects.listVersions(projectId);
      const versions = vs.ok ? vs.value : [];
      let asset: Asset | null = null;
      let blobMissing = false;
      if (p.value.assetId) {
        const a = await services.projects.getAsset(p.value.assetId);
        if (a.ok) {
          asset = a.value;
          if (asset.source === "upload") { const b = await services.projects.getAssetBlob(asset); blobMissing = !b.ok || b.value === null; }
        }
      }
      const selectedVersionId = p.value.selectedVersionId ?? versions[versions.length - 1]?.id ?? null;
      set({ project: p.value, asset, blobMissing, analysis: p.value.analysis, versions, selectedVersionId,
        currentPlan: versions.find((v) => v.id === selectedVersionId)?.plan ?? null, busy: null });
    },

    modelLoaded: (input, stats) => guarded("analyzing", async () => {
      const { project } = get();
      if (!project) return { ok: false, error: { code: "no_project", message: "No project open." } };
      set({ stats });
      const a = await services.projects.saveAsset({ projectId: project.id, fileName: input.fileName, format: input.format, sizeBytes: input.sizeBytes,
        source: input.source, blobKey: null, sampleUrl: input.sampleUrl, thumbnailKey: null }, input.blob);
      if (!a.ok) return a;
      const an = await services.analysis.analyze(stats);
      const analysis = an.ok ? an.value : null;
      const up = await services.projects.updateProject(project.id, { assetId: a.value.id, analysis });
      // Asset saved but not linked to the project is an error the UI must show.
      if (!up.ok) return up;
      set({ asset: a.value, blobMissing: false, analysis, project: up.value });
      return a;
    }),

    submitPrompt: (prompt) => {
      const plan = selectedPlan();
      if (!plan) return planFresh(prompt);
      return guarded("editing", async () => {
        const r = await services.director.edit(prompt, plan);
        if (!r.ok) return r;
        return append(prompt, r.value.reduce(applyPatch, plan), CREDIT_COSTS.prompt_edit, "prompt_edit");
      });
    },

    startOver: (prompt) => planFresh(prompt),

    acceptPending: () => guarded("planning", async () => {
      const pw = get().pendingWarning;
      if (!pw) return { ok: true, value: null };
      return append(pw.prompt, pw.plan, CREDIT_COSTS.scene_generation, "scene_generation");
    }),
    dismissPending: () => set({ pendingWarning: null }),

    previewSlider: (key, value) => {
      const base = selectedPlan();
      if (!base) return;
      set({ currentPlan: sliderPatches(key, value, base).reduce(applyPatch, base) });
    },
    commitSlider: (key, value) => guarded("editing", async () => {
      const base = selectedPlan();
      if (!base) return { ok: false, error: { code: "no_plan", message: "Generate a scene first." } };
      return append(`manual: ${key}`, sliderPatches(key, value, base).reduce(applyPatch, base), 0, null);
    }),
    commitOutput: (output) => guarded("editing", async () => {
      const base = selectedPlan();
      if (!base) return { ok: false, error: { code: "no_plan", message: "Generate a scene first." } };
      return append("manual: output", applyPatch(base, { operation: "set_output", output }), 0, null);
    }),

    selectVersion: async (id) => {
      const { project, versions } = get();
      const v = versions.find((x) => x.id === id);
      if (!v || !project) return;
      await services.projects.updateProject(project.id, { selectedVersionId: id });
      set({ selectedVersionId: id, currentPlan: v.plan });
    },
  };
});
