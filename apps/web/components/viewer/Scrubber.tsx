"use client";

import { useEffect, useState } from "react";
import { Slider } from "@/components/ui";
import type { ScenePlan } from "@/lib/schema";
import { SHOT_LABEL, shotAt } from "./cameraPath";

export type ScrubberProps = {
  plan: ScenePlan;
  /** Absolute timeline time, or `null` when the orbit camera is showing. */
  seconds: number | null;
  onChange: (seconds: number | null) => void;
  disabled?: boolean;
  className?: string;
};

const fmt = (s: number) => `${s.toFixed(1)}s`;

/**
 * Timeline under the viewer. Dragging moves the preview camera along the path;
 * releasing (or Escape) returns to the orbit camera.
 */
export function Scrubber({ plan, seconds, onChange, disabled, className }: ScrubberProps) {
  const duration = plan.output.durationS;
  const previewing = seconds !== null;
  // The thumb stays where it was released; only the camera returns to orbit.
  const [last, setLast] = useState(0);
  const at = seconds ?? Math.min(last, duration);
  const { shot } = shotAt(plan, at);
  const shotIndex = plan.shots.findIndex((s) => s.id === shot.id);

  useEffect(() => {
    if (!previewing) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onChange(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [previewing, onChange]);

  return (
    <div
      className={`flex flex-col gap-2 border-t border-line bg-bg-1 px-4 py-3 ${className ?? ""}`}
      data-previewing={previewing ? "true" : undefined}
    >
      <div className="flex items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
          <span className={`inline-block size-1.5 rounded-full ${previewing ? "bg-accent" : "bg-fg-muted/50"}`} aria-hidden />
          <span className="text-fg">
            {plan.shots.length > 1 ? `Shot ${shotIndex + 1} · ` : ""}
            {SHOT_LABEL[shot.action]}
          </span>
          <span className="text-fg-muted">
            {plan.camera.lensMm}mm · {plan.camera.style === "handheld" ? "handheld" : "smooth"}
          </span>
        </div>
        <span className="text-fg-muted" aria-live="polite">
          {previewing ? "Previewing · release or press Esc for orbit" : "Drag to preview the camera path"}
        </span>
      </div>
      <Slider
        label="Timeline"
        min={0}
        max={duration}
        step={0.05}
        value={at}
        format={(v) => `${fmt(v)} / ${duration}s`}
        onChange={(v) => {
          setLast(v);
          onChange(v);
        }}
        onCommit={() => onChange(null)}
        disabled={disabled}
      />
    </div>
  );
}
