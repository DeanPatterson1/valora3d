"use client";

import { motion, useReducedMotion } from "motion/react";
import { Button, cx } from "@/components/ui";
import { DUR, EASE } from "@/lib/motion/tokens";
import type { RenderJob, RenderJobStatus } from "@/lib/schema";

type Tone = "waiting" | "active" | "done" | "failed";

/** One line per status: a short label, a sentence for the person waiting, and the tone that colours the bar. */
export const JOB_STATUS: Record<RenderJobStatus, { label: string; copy: string; tone: Tone }> = {
  QUEUED: { label: "Queued", copy: "Waiting for a GPU.", tone: "waiting" },
  PREPARING: { label: "Preparing", copy: "Loading the model and building the scene.", tone: "active" },
  RENDERING: { label: "Rendering", copy: "Drawing each frame. You can leave this page; the job keeps going.", tone: "active" },
  ENCODING: { label: "Encoding", copy: "Frames are done. Packing them into a video.", tone: "active" },
  UPLOADING: { label: "Uploading", copy: "Almost there. Moving the file to your project.", tone: "active" },
  COMPLETE: { label: "Complete", copy: "Your render is ready.", tone: "done" },
  FAILED: { label: "Failed", copy: "The render stopped before it finished.", tone: "failed" },
};

/** Fraction of the bar to fill: frames done while rendering, full once past it, empty before it. */
export function jobFraction(job: RenderJob): number {
  switch (job.status) {
    case "QUEUED":
    case "PREPARING":
      return 0;
    case "RENDERING":
      return job.totalFrames > 0 ? Math.min(1, Math.max(0, job.frame / job.totalFrames)) : 0;
    case "ENCODING":
    case "UPLOADING":
    case "COMPLETE":
      return 1;
    case "FAILED":
      return job.totalFrames > 0 ? Math.min(1, Math.max(0, job.frame / job.totalFrames)) : 0;
  }
}

const BAR: Record<Tone, string> = {
  waiting: "bg-fg-muted/50",
  active: "bg-accent",
  done: "bg-success",
  failed: "bg-danger",
};

const DOT: Record<Tone, string> = {
  waiting: "bg-fg-muted/60",
  active: "bg-accent",
  done: "bg-success",
  failed: "bg-danger",
};

export type JobProgressProps = {
  job: RenderJob;
  /** Shown as a Retry button on FAILED. */
  onRetry?: () => void;
  className?: string;
};

/**
 * Presentational status for one render job. Driven purely by props: nothing here
 * ticks, polls or guesses — the renderer supplies every frame count.
 */
export function JobProgress({ job, onRetry, className }: JobProgressProps) {
  const rm = useReducedMotion() ?? false;
  const meta = JOB_STATUS[job.status];
  const fraction = jobFraction(job);
  const percent = Math.round(fraction * 100);
  const rendering = job.status === "RENDERING";
  const failed = job.status === "FAILED";
  const kind = job.kind === "preview" ? "Preview" : job.target === "cloud" ? "Cloud render" : "Local render";

  return (
    <div
      className={cx("flex flex-col gap-3 rounded-lg border border-line bg-bg-2 p-4", className)}
      data-status={job.status}
      aria-live="polite"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-0.5">
          <div className="flex items-center gap-2">
            <span aria-hidden className={cx("size-1.5 shrink-0 rounded-full", DOT[meta.tone])} />
            <span className={cx("text-sm font-medium", failed ? "text-danger" : "text-fg")}>{meta.label}</span>
            <span className="text-xs text-fg-muted">· {kind}</span>
          </div>
          <p className="text-sm text-fg-muted">{meta.copy}</p>
        </div>
        {rendering && (
          <span className="shrink-0 font-mono tabular text-sm text-fg" data-testid="frame-counter">
            Frame {job.frame} / {job.totalFrames}
          </span>
        )}
        {job.status === "COMPLETE" && (
          <span className="shrink-0 font-mono tabular text-sm text-fg-muted">{job.totalFrames} frames</span>
        )}
      </div>

      <div
        role="progressbar"
        aria-label={`${meta.label}${rendering ? `, frame ${job.frame} of ${job.totalFrames}` : ""}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-valuetext={rendering ? `Frame ${job.frame} of ${job.totalFrames}` : meta.label}
        className="h-1 w-full overflow-hidden rounded-full bg-bg-3"
      >
        <motion.div
          className={cx("h-full rounded-full", BAR[meta.tone])}
          initial={false}
          animate={{ width: `${percent}%` }}
          transition={rm ? { duration: 0 } : { duration: DUR.base, ease: EASE.standard }}
        />
      </div>

      {failed && (
        <div className="flex items-start justify-between gap-3">
          <p role="alert" className="min-w-0 flex-1 text-sm text-fg">
            {job.error ?? "No details were reported."}
          </p>
          {onRetry && (
            <Button size="sm" variant="secondary" onClick={onRetry}>
              Retry
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
