import { useCallback } from "react";
import { create } from "zustand";
import { loadModel, validateFile, type Format } from "@/components/viewer/loadModel";
import { computeSceneStats } from "@/components/viewer/sceneStats";
import type { SceneStats } from "@/lib/schema";
import type { ServiceError } from "@/lib/services";
import { useStudioStore, type ModelInput } from "@/lib/stores/studio";
import { useLabourStore } from "./useLabour";

export const ACCEPT = ".glb,.gltf,.fbx,.obj";

export const SAMPLES = [
  { id: "car", name: "Sample car", title: "Car", hint: "Sports coupe", url: "/samples/car.glb", still: "/samples/car.jpg" },
  { id: "product", name: "Sample product", title: "Product", hint: "Tabletop object", url: "/samples/product.glb", still: "/samples/product.jpg" },
] as const;
export type Sample = (typeof SAMPLES)[number];

export type IngestPhase = { kind: "idle" } | { kind: "working"; fileName: string; done: boolean };

type IngestState = {
  phase: IngestPhase;
  error: ServiceError | null;
  setPhase: (phase: IngestPhase) => void;
  setError: (error: ServiceError | null) => void;
};

/** Shared so the upload card and the composer's `+` menu show one and the same progress. */
export const useIngestStore = create<IngestState>((set) => ({
  phase: { kind: "idle" },
  error: null,
  setPhase: (phase) => set({ phase }),
  setError: (error) => set({ error }),
}));

/**
 * Validate → load → stats → `modelLoaded`, behind the analysis labour sequence
 * (spec 6.1, 10, 11). Whoever mounts the sequence calls `onDone` when it ends.
 */
export function useModelIngest() {
  const phase = useIngestStore((s) => s.phase);
  const error = useIngestStore((s) => s.error);
  const setPhase = useIngestStore((s) => s.setPhase);
  const setError = useIngestStore((s) => s.setError);
  const modelLoaded = useStudioStore((s) => s.modelLoaded);
  const clearError = useStudioStore((s) => s.clearError);
  const working = phase.kind === "working";

  const fail = useCallback((e: ServiceError) => {
    useLabourStore.getState().end();
    setPhase({ kind: "idle" });
    setError(e);
  }, [setPhase, setError]);

  const ingest = useCallback(async (source: Blob, format: Format, input: Omit<ModelInput, "format" | "sizeBytes">) => {
    const loaded = await loadModel(source, format);
    if (!loaded.ok) return fail(loaded.error);
    let stats: SceneStats;
    try {
      stats = computeSceneStats(loaded.value.root);
    } catch {
      return fail({ code: "no_geometry", message: "No usable geometry in this file. Check the model has meshes with a real size." });
    }
    const r = await modelLoaded({ ...input, format, sizeBytes: source.size }, stats);
    if (!r.ok) {
      // The store keeps this error too; it is shown inline instead of as a floating alert.
      clearError();
      return fail(r.error);
    }
    const p = useIngestStore.getState().phase;
    if (p.kind === "working") setPhase({ ...p, done: true });
  }, [fail, modelLoaded, clearError, setPhase]);

  const startWork = useCallback((fileName: string) => {
    setError(null);
    useLabourStore.getState().begin();
    setPhase({ kind: "working", fileName, done: false });
  }, [setError, setPhase]);

  const onFile = useCallback((file: File) => {
    if (useIngestStore.getState().phase.kind === "working") return;
    const v = validateFile(file);
    if (!v.ok) { setError(v.error); return; }
    startWork(file.name);
    void ingest(file, v.value, { fileName: file.name, source: "upload", sampleUrl: null, blob: file });
  }, [ingest, setError, startWork]);

  const onSample = useCallback(async (sample: Sample) => {
    if (useIngestStore.getState().phase.kind === "working") return;
    const fileName = sample.url.split("/").pop() ?? sample.id;
    startWork(fileName);
    let blob: Blob;
    try {
      const res = await fetch(sample.url);
      if (!res.ok) throw new Error(String(res.status));
      blob = await res.blob();
    } catch {
      return fail({ code: "sample_unavailable", message: "The sample could not be fetched. Check your connection and try again." });
    }
    // Samples are referenced by URL and never stored, so the blob is only parsed here.
    await ingest(blob, "glb", { fileName, source: "sample", sampleUrl: sample.url, blob: null });
  }, [fail, ingest, startWork]);

  /** From `LabourSequence.onDone`: the sequence has held its minimum and the work is in. */
  const onDone = useCallback(() => {
    setPhase({ kind: "idle" });
    useLabourStore.getState().end();
  }, [setPhase]);

  return { phase, working, error, onFile, onSample, onDone, dismissError: () => setError(null) };
}
