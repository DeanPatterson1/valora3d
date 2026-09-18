"use client";

import { motion, useReducedMotion, type Variants } from "motion/react";
import { Button, cx } from "@/components/ui";
import { DUR, EASE } from "@/lib/motion/tokens";
import { fadeRise, reduced } from "@/lib/motion/variants";
import type { RenderJob } from "@/lib/schema";

/** fadeRise plus a whisper of scale, so the finished frame settles into place. */
const reveal: Variants = {
  hidden: { ...fadeRise.hidden, scale: 0.98 },
  visible: {
    ...fadeRise.visible,
    scale: 1,
    transition: { duration: DUR.slow, ease: EASE.emphasized },
  },
};

export type RenderResultProps = {
  job: RenderJob;
  onRegenerate: () => void;
  className?: string;
};

function describe(job: RenderJob) {
  const what = job.kind === "preview" ? "Preview" : "Final render";
  const where = job.target === "cloud" ? "cloud GPU" : "your GPU";
  return `${what} · ${where} · ${job.totalFrames} frames`;
}

/**
 * The finished render. Designed as the product's best moment (spec 10, peak-end):
 * one wide frame with room around it, the file itself as the only thing that glows,
 * and two calm actions underneath. Nothing plays unless the renderer supplied a URL.
 */
export function RenderResult({ job, onRegenerate, className }: RenderResultProps) {
  const rm = useReducedMotion() ?? false;
  const url = job.resultUrl;
  const fileName = `render-${job.id}.mp4`;

  return (
    <motion.section
      aria-label="Render result"
      variants={rm ? reduced(reveal) : reveal}
      initial="hidden"
      animate="visible"
      className={cx("flex flex-col gap-6", className)}
    >
      <div
        className={cx(
          "relative aspect-video w-full overflow-hidden rounded-lg border bg-bg-0 shadow-overlay",
          url ? "border-line" : "border-dashed border-line",
        )}
      >
        {url ? (
          <video
            controls
            playsInline
            preload="metadata"
            src={url}
            className="absolute inset-0 size-full bg-bg-0 object-contain"
            aria-label="Rendered video"
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-6 text-center">
            <span
              aria-hidden
              className="mb-2 size-10 rounded-full border border-line"
              style={{
                background:
                  "radial-gradient(circle at 50% 40%, color-mix(in oklab, var(--color-accent) 30%, transparent), transparent 70%)",
              }}
            />
            <span className="text-sm text-fg-muted">Your render will appear here</span>
          </div>
        )}
        {/* Vignette keeps the frame reading as a screen, not a card. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-lg"
          style={{ boxShadow: "inset 0 0 80px rgba(0,0,0,0.45)" }}
        />
      </div>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-col gap-1">
          <h3 className="font-display text-xl font-semibold text-fg">
            {url ? "Your render is ready" : "Render"}
          </h3>
          <p className="text-sm text-fg-muted">{describe(job)}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" onClick={onRegenerate}>
            Regenerate
          </Button>
          {url ? (
            <a
              href={url}
              download={fileName}
              className="inline-flex h-10 shrink-0 cursor-pointer select-none items-center justify-center gap-2 whitespace-nowrap rounded-md bg-accent px-4 text-sm font-medium text-accent-fg transition-colors duration-fast ease-standard hover:brightness-110 focus-visible:focus-ring"
            >
              <DownloadIcon />
              Download
            </a>
          ) : (
            <Button variant="primary" disabled icon={<DownloadIcon />} title="Available once a render finishes">
              Download
            </Button>
          )}
        </div>
      </div>
    </motion.section>
  );
}

function DownloadIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 2v9M4.5 7.5 8 11l3.5-3.5M3 13.5h10" />
    </svg>
  );
}
