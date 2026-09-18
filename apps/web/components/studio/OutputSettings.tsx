"use client";

import { useEffect, useId, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { cx } from "@/components/ui";
import { DUR, EASE } from "@/lib/motion/tokens";
import type { ScenePlan } from "@/lib/schema";
import { useStudioStore } from "@/lib/stores/studio";

type Output = ScenePlan["output"];

const DURATIONS: readonly Output["durationS"][] = [5, 10, 15, 30];
const RESOLUTIONS: readonly Output["resolution"][] = ["720p", "1080p", "1440p", "4k"];
const FPS: readonly Output["fps"][] = [24, 30, 60];
const QUALITIES: readonly Output["quality"][] = ["draft", "standard", "high", "ultra"];

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** "10s · 1080p · 30fps · High" */
export function summariseOutput(o: Output): string {
  return `${o.durationS}s · ${o.resolution} · ${o.fps}fps · ${cap(o.quality)}`;
}

/**
 * Output settings (spec 6.3, 10): collapsed behind a summary chip; expands to four
 * segmented controls. Every change appends a free `manual: output` version through
 * `commitOutput`. Rendered in the composer's second row only when a plan exists.
 */
export function OutputSettings({ disabled, className }: { disabled?: boolean; className?: string }) {
  const rm = useReducedMotion() ?? false;
  const plan = useStudioStore((s) => s.currentPlan);
  const commitOutput = useStudioStore((s) => s.commitOutput);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  // Close on outside click or Escape; Escape returns focus to the chip.
  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setOpen(false); buttonRef.current?.focus(); }
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!plan) return null;
  const o = plan.output;
  const set = (patch: Partial<Output>) => void commitOutput(patch);

  return (
    <div ref={rootRef} className={cx("relative", className)}>
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={`Output settings: ${summariseOutput(o)}`}
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className={cx(
          "inline-flex h-8 cursor-pointer select-none items-center gap-1.5 whitespace-nowrap rounded-full px-3 text-xs tabular transition-colors duration-fast ease-standard focus-visible:focus-ring disabled:cursor-not-allowed disabled:opacity-40",
          open ? "bg-bg-3 text-fg" : "text-fg-muted hover:bg-bg-3 hover:text-fg",
        )}
      >
        <svg aria-hidden viewBox="0 0 16 16" className="size-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
          <path d="M2 4h12M2 8h8M2 12h5" />
        </svg>
        {summariseOutput(o)}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            key="panel"
            id={panelId}
            role="group"
            aria-label="Output settings"
            initial={{ opacity: 0, y: rm ? 0 : 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: rm ? 0 : 8, transition: { duration: rm ? 0 : DUR.fast } }}
            transition={{ duration: rm ? 0 : DUR.base, ease: EASE.emphasized }}
            className="absolute bottom-full left-0 z-20 mb-3 flex w-[min(20rem,calc(100vw-2rem))] flex-col gap-3 rounded-2xl bg-bg-2 p-3 shadow-overlay"
          >
            <Segmented label="Duration" name="duration" value={o.durationS} options={DURATIONS} format={(d) => `${d}s`} onChange={(durationS) => set({ durationS })} />
            <Segmented label="Resolution" name="resolution" value={o.resolution} options={RESOLUTIONS} format={String} onChange={(resolution) => set({ resolution })} />
            <Segmented label="Frame rate" name="fps" value={o.fps} options={FPS} format={(f) => `${f} fps`} onChange={(fps) => set({ fps })} />
            <Segmented label="Quality" name="quality" value={o.quality} options={QUALITIES} format={cap} onChange={(quality) => set({ quality })} />
            <p className="text-[11px] leading-snug text-fg-muted">Free to change. Each change is saved as a version.</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

type SegmentedProps<T extends string | number> = {
  label: string;
  name: string;
  value: T;
  options: readonly T[];
  format: (v: T) => string;
  onChange: (v: T) => void;
};

/** Radio-group semantics with roving tabindex: arrows move and select, the chosen option is the tab stop. */
function Segmented<T extends string | number>({ label, name, value, options, format, onChange }: SegmentedProps<T>) {
  const ref = useRef<HTMLDivElement>(null);
  const labelId = useId();

  const pick = (i: number) => {
    const j = (i + options.length) % options.length;
    onChange(options[j]);
    ref.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[j]?.focus();
  };
  const onKeyDown = (e: React.KeyboardEvent, i: number) => {
    switch (e.key) {
      case "ArrowRight": case "ArrowDown": e.preventDefault(); pick(i + 1); break;
      case "ArrowLeft": case "ArrowUp": e.preventDefault(); pick(i - 1); break;
      case "Home": e.preventDefault(); pick(0); break;
      case "End": e.preventDefault(); pick(options.length - 1); break;
    }
  };

  return (
    <div className="flex flex-col gap-1.5">
      <span id={labelId} className="text-xs text-fg-muted">{label}</span>
      <div ref={ref} role="radiogroup" aria-labelledby={labelId} data-segment={name} className="grid auto-cols-fr grid-flow-col rounded-md border border-line bg-bg-0 p-0.5">
        {options.map((opt, i) => {
          const selected = opt === value;
          return (
            <button
              key={String(opt)}
              type="button"
              role="radio"
              aria-checked={selected}
              tabIndex={selected ? 0 : -1}
              onClick={() => { if (!selected) onChange(opt); }}
              onKeyDown={(e) => onKeyDown(e, i)}
              className={cx(
                "h-8 cursor-pointer rounded-sm px-1 text-xs tabular transition-colors duration-fast ease-standard focus-visible:focus-ring",
                selected ? "bg-bg-3 text-fg" : "text-fg-muted hover:text-fg",
              )}
            >
              {format(opt)}
            </button>
          );
        })}
      </div>
    </div>
  );
}
