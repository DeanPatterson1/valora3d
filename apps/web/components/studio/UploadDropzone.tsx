"use client";

import Link from "next/link";
import { useId, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Button, cx } from "@/components/ui";
import { DUR, EASE } from "@/lib/motion/tokens";
import { MAX_UPLOAD_BYTES } from "@/lib/pricing";
import { useStudioStore } from "@/lib/stores/studio";
import { ANALYSIS_STEPS } from "./labour";
import { LabourSequence } from "./LabourSequence";
import { ACCEPT, SAMPLES, useModelIngest, type Sample } from "./useModelIngest";

const MAX_MB = Math.round(MAX_UPLOAD_BYTES / 1024 / 1024);

/**
 * Empty state over the viewer (spec 6.1, 10, 11): one centred card with the file
 * picker and two sample rows, so the studio works with nothing to upload. Also the
 * re-upload state when an uploaded model's blob is gone from this browser, and the
 * "Understanding your model" sequence for any load, including from the composer menu.
 */
export function UploadDropzone() {
  const rm = useReducedMotion() ?? false;
  const project = useStudioStore((s) => s.project);
  const asset = useStudioStore((s) => s.asset);
  const blobMissing = useStudioStore((s) => s.blobMissing);
  const { phase, working, error, onFile, onSample, onDone, dismissError } = useModelIngest();

  const [dragging, setDragging] = useState(false);
  const dragDepth = useRef(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const titleId = useId();

  const needsModel = project !== null && (asset === null || blobMissing);
  const visible = needsModel || working;

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
          className="absolute inset-0 z-10 flex flex-col items-center overflow-y-auto bg-bg-0/85 px-4 pb-28 pt-20 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: rm ? 0 : DUR.slow, ease: EASE.standard } }}
          transition={{ duration: rm ? 0 : DUR.base }}
          onDragEnter={onDragEnter}
          onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = working ? "none" : "copy"; }}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
        >
          {phase.kind === "working" ? (
            <motion.div
              key="sequence"
              className="my-auto w-full max-w-sm shrink-0 rounded-2xl bg-bg-2 p-5 shadow-raise"
              initial={{ opacity: 0, y: rm ? 0 : 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: rm ? 0 : DUR.base, ease: EASE.standard }}
            >
              <h2 id={titleId} className="text-base font-semibold text-fg">Understanding your model</h2>
              <p className="mt-0.5 truncate text-xs text-fg-muted" title={phase.fileName}>{phase.fileName}</p>
              <LabourSequence steps={ANALYSIS_STEPS} workDone={phase.done} onDone={onDone} className="mt-4" />
            </motion.div>
          ) : (
            <div
              data-upload-card
              className={cx(
                "my-auto flex w-full max-w-[520px] shrink-0 flex-col gap-5 rounded-[24px] border bg-bg-1 p-6 transition-colors duration-fast ease-standard sm:p-8",
                dragging ? "border-fg/60" : "border-line",
              )}
            >
              <div className="flex flex-col gap-1">
                <h2 id={titleId} className="text-2xl font-semibold tracking-tight text-fg">
                  {blobMissing ? "Model file missing" : dragging ? "Drop to upload" : "Drop a model to begin"}
                </h2>
                <p className="text-sm text-fg-muted">
                  {blobMissing
                    ? "This project's model file is no longer in this browser. Upload it again to continue; your scene history is kept."
                    : "Drag it anywhere here, or choose a file."}
                </p>
              </div>

              <div className="flex flex-col gap-2">
                <div>
                  <Button variant="primary" size="lg" onClick={() => inputRef.current?.click()}>Choose file</Button>
                </div>
                <p className="text-xs text-fg-muted">A single .glb file up to {MAX_MB} MB</p>
                <Link href="/help/preparing-your-model#blender" className="w-fit rounded-sm text-xs text-fg-muted underline underline-offset-4 hover:text-fg focus-visible:focus-ring">How to export a .glb</Link>
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
                          <Link href="/projects" className="rounded-sm underline underline-offset-2 hover:text-fg focus-visible:focus-ring">
                            Manage projects
                          </Link>
                        </>
                      )}
                    </span>
                    <button
                      type="button"
                      onClick={dismissError}
                      aria-label="Dismiss"
                      className="rounded-sm px-1 text-fg-muted hover:text-fg focus-visible:focus-ring"
                    >
                      ×
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="flex flex-col gap-1 border-t border-line pt-4">
                <p className="mb-1 text-xs text-fg-muted">{blobMissing ? "Or switch to a sample" : "Or start with a sample"}</p>
                {SAMPLES.map((s) => (
                  <SampleRow key={s.id} sample={s} onPick={() => void onSample(s)} />
                ))}
              </div>
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function SampleRow({ sample, onPick }: { sample: Sample; onPick: () => void }) {
  const [imgFailed, setImgFailed] = useState(false);
  return (
    <button
      type="button"
      aria-label={sample.name}
      onClick={onPick}
      className="-mx-2 flex cursor-pointer items-center gap-3 rounded-md px-2 py-1.5 text-left transition-colors duration-fast ease-standard hover:bg-bg-3 focus-visible:focus-ring"
    >
      <span className="relative h-10 w-14 shrink-0 overflow-hidden rounded-sm bg-[radial-gradient(ellipse_at_50%_80%,_#3a3a3a_0%,_#242424_55%,_#1a1a1a_100%)]">
        {!imgFailed && (
          // Stills are produced separately; a missing file leaves the gradient.
          // eslint-disable-next-line @next/next/no-img-element
          <img src={sample.still} alt="" loading="lazy" onError={() => setImgFailed(true)} className="size-full object-cover" />
        )}
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
        <span className="text-sm text-fg">{sample.title}</span>
        <span className="text-xs text-fg-muted">{sample.hint}</span>
      </span>
    </button>
  );
}
