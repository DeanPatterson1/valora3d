"use client";

import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Button, cx } from "@/components/ui";
import { loadModel, validateFile, type Format } from "@/components/viewer/loadModel";
import { computeSceneStats } from "@/components/viewer/sceneStats";
import { DUR, EASE } from "@/lib/motion/tokens";
import { MAX_UPLOAD_BYTES } from "@/lib/pricing";
import type { SceneStats } from "@/lib/schema";
import type { ServiceError } from "@/lib/services";
import { useStudioStore, type ModelInput } from "@/lib/stores/studio";
import { ANALYSIS_STEPS } from "./labour";
import { LabourSequence } from "./LabourSequence";
import { useLabour } from "./useLabour";

const ACCEPT = ".glb,.gltf,.fbx,.obj";
const MAX_MB = Math.round(MAX_UPLOAD_BYTES / 1024 / 1024);

const SAMPLES = [
  { id: "car", name: "Sample car", title: "Car", hint: "Sports coupe", url: "/samples/car.glb", still: "/samples/car.jpg" },
  { id: "product", name: "Sample product", title: "Product", hint: "Tabletop object", url: "/samples/product.glb", still: "/samples/product.jpg" },
] as const;
type Sample = (typeof SAMPLES)[number];

type Phase = { kind: "idle" } | { kind: "working"; fileName: string; done: boolean };

/**
 * Empty state over the viewer (spec 6.1, 10, 11): drop target, file picker and two
 * sample cards so the studio works with nothing to upload. Also the re-upload state
 * when an uploaded model's blob is gone from this browser. Runs validate → load →
 * stats → `modelLoaded` behind the analysis labour sequence.
 */
export function UploadDropzone() {
  const rm = useReducedMotion() ?? false;
  const project = useStudioStore((s) => s.project);
  const asset = useStudioStore((s) => s.asset);
  const blobMissing = useStudioStore((s) => s.blobMissing);
  const modelLoaded = useStudioStore((s) => s.modelLoaded);
  const clearError = useStudioStore((s) => s.clearError);
  const { begin, end } = useLabour();

  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [error, setError] = useState<ServiceError | null>(null);
  const [dragging, setDragging] = useState(false);
  const dragDepth = useRef(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const titleId = useId();
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const needsModel = project !== null && (asset === null || blobMissing);
  const working = phase.kind === "working";
  const visible = needsModel || working;

  const fail = useCallback((e: ServiceError) => {
    end();
    if (!mounted.current) return;
    setPhase({ kind: "idle" });
    setError(e);
  }, [end]);

  /** Shared tail of both paths: parse, measure, hand to the store. The sequence is already showing. */
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
      // The store keeps this error too; it is shown inline here instead of as a floating alert.
      clearError();
      return fail(r.error);
    }
    if (mounted.current) setPhase((p) => (p.kind === "working" ? { ...p, done: true } : p));
  }, [fail, modelLoaded, clearError]);

  const startWork = (fileName: string) => {
    setError(null);
    begin();
    setPhase({ kind: "working", fileName, done: false });
  };

  const onFile = (file: File) => {
    if (working) return;
    const v = validateFile(file);
    if (!v.ok) { setError(v.error); return; }
    startWork(file.name);
    void ingest(file, v.value, { fileName: file.name, source: "upload", sampleUrl: null, blob: file });
  };

  const onSample = async (sample: Sample) => {
    if (working) return;
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
  };

  const onDone = () => {
    setPhase({ kind: "idle" });
    end();
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    dragDepth.current = 0;
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) onFile(file);
  };
  const onDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    dragDepth.current += 1;
    if (!working) setDragging(true);
  };
  const onDragLeave = () => {
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setDragging(false);
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="dropzone"
          role="region"
          aria-labelledby={titleId}
          data-upload-dropzone
          className="absolute inset-0 z-10 flex items-center justify-center overflow-y-auto bg-bg-0/85 p-4 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: rm ? 0 : DUR.slow, ease: EASE.standard } }}
          transition={{ duration: rm ? 0 : DUR.base }}
          onDragEnter={onDragEnter}
          onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = working ? "none" : "copy"; }}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
        >
          <div className="w-full max-w-xl">
            {working ? (
              <motion.div
                key="sequence"
                className="mx-auto max-w-sm rounded-lg border border-line bg-bg-1 p-5 shadow-raise"
                initial={{ opacity: 0, y: rm ? 0 : 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: rm ? 0 : DUR.base, ease: EASE.standard }}
              >
                <h2 id={titleId} className="font-display text-lg font-semibold text-fg">Understanding your model</h2>
                <p className="mt-0.5 truncate font-mono text-xs text-fg-muted" title={phase.fileName}>{phase.fileName}</p>
                <LabourSequence steps={ANALYSIS_STEPS} workDone={phase.done} onDone={onDone} className="mt-4" />
              </motion.div>
            ) : (
              <div className="flex flex-col gap-4">
                <div className="text-center">
                  <h2 id={titleId} className="font-display text-2xl font-semibold text-fg">
                    {blobMissing ? "Model file missing" : "Drop a model to begin"}
                  </h2>
                  <p className="mx-auto mt-1 max-w-md text-sm text-fg-muted">
                    {blobMissing
                      ? "This project's model file is no longer in this browser. Upload it again to continue; your scene history is kept."
                      : "— or start with a sample"}
                  </p>
                </div>

                <div
                  className={cx(
                    "flex flex-col items-center gap-3 rounded-lg border border-dashed px-6 py-7 text-center transition-colors duration-fast ease-standard",
                    dragging ? "border-accent bg-accent/10" : "border-line bg-bg-1/70",
                  )}
                >
                  <div className="flex size-11 items-center justify-center rounded-md border border-line bg-bg-2 text-fg-muted">
                    <svg aria-hidden viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 16V4m0 0l-4 4m4-4l4 4" />
                      <path d="M4 15v3a2 2 0 002 2h12a2 2 0 002-2v-3" />
                    </svg>
                  </div>
                  <p className="text-sm text-fg">
                    {dragging ? "Drop to upload" : "Drag a model here"}
                    <span className="block text-xs text-fg-muted">GLB, GLTF, FBX or OBJ · single file · up to {MAX_MB} MB</span>
                  </p>
                  <Button variant="primary" onClick={() => inputRef.current?.click()}>Choose file</Button>
                  <input
                    ref={inputRef}
                    type="file"
                    accept={ACCEPT}
                    className="sr-only"
                    aria-label="Choose a model file"
                    tabIndex={-1}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      e.target.value = "";
                      if (file) onFile(file);
                    }}
                  />
                </div>

                <AnimatePresence initial={false}>
                  {error && (
                    <motion.div
                      key={error.code}
                      role="alert"
                      className="flex items-start gap-3 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-fg"
                      initial={{ opacity: 0, y: rm ? 0 : -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: rm ? 0 : DUR.fast }}
                    >
                      <span className="flex-1">
                        {error.message}
                        {error.code === "quota_exceeded" && (
                          <>
                            {" "}
                            <Link href="/projects" className="underline underline-offset-2 hover:text-accent focus-visible:focus-ring rounded-sm">
                              Manage projects
                            </Link>
                          </>
                        )}
                      </span>
                      <button
                        type="button"
                        onClick={() => setError(null)}
                        aria-label="Dismiss"
                        className="rounded-sm px-1 text-fg-muted hover:text-fg focus-visible:focus-ring"
                      >
                        ×
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>

                <div>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-fg-muted">
                    {blobMissing ? "Or switch to a sample" : "Start with a sample"}
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    {SAMPLES.map((s) => (
                      <SampleCard key={s.id} sample={s} onPick={() => void onSample(s)} />
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function SampleCard({ sample, onPick }: { sample: Sample; onPick: () => void }) {
  const [imgFailed, setImgFailed] = useState(false);
  return (
    <motion.button
      type="button"
      aria-label={sample.name}
      onClick={onPick}
      whileTap={{ scale: 0.98 }}
      transition={{ duration: DUR.fast, ease: EASE.standard }}
      className="group flex cursor-pointer flex-col overflow-hidden rounded-lg border border-line bg-bg-1 text-left transition-colors duration-fast ease-standard hover:border-fg-muted/60 hover:bg-bg-2 focus-visible:focus-ring"
    >
      <div className="relative aspect-[16/10] w-full overflow-hidden bg-[radial-gradient(ellipse_at_50%_80%,_#3a342c_0%,_#201d19_55%,_#171512_100%)]">
        {!imgFailed && (
          // Stills are produced separately; a missing file leaves the gradient.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={sample.still}
            alt=""
            loading="lazy"
            onError={() => setImgFailed(true)}
            className="size-full object-cover transition-transform duration-slow ease-emphasized group-hover:scale-[1.03] motion-reduce:transition-none motion-reduce:group-hover:scale-100"
          />
        )}
      </div>
      <div className="flex items-baseline justify-between gap-2 px-3 py-2">
        <span className="text-sm font-medium text-fg">{sample.title}</span>
        <span className="text-xs text-fg-muted">{sample.hint}</span>
      </div>
    </motion.button>
  );
}
