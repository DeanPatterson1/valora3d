"use client";

import { motion, useReducedMotion } from "motion/react";
import { SPRING } from "@/lib/motion/tokens";
import { cx } from "@/components/ui";

export type StepState = "done" | "current" | "next";
export type Step = { id: string; label: string; state: StepState; tag?: string };

/** Studio progress: Upload → Understand → Direct → Render (spec 7, goal gradient in spec 10). */
export function deriveSteps(input: { hasAsset: boolean; hasAnalysis: boolean; versionCount: number }): Step[] {
  const flags = [input.hasAsset, input.hasAnalysis, input.versionCount > 0];
  const firstOpen = flags.indexOf(false);
  const state = (i: number): StepState => (flags[i] ? "done" : i === firstOpen ? "current" : "next");
  return [
    { id: "upload", label: "Upload", state: state(0) },
    { id: "understand", label: "Understand", state: state(1) },
    { id: "direct", label: "Direct", state: state(2) },
    // Rendering is not connected in the prototype; it is always the step after "Scene ready".
    { id: "render", label: "Render", state: "next", tag: "not connected" },
  ];
}

export function StepIndicator({ steps, className }: { steps: Step[]; className?: string }) {
  const rm = useReducedMotion();
  const done = steps.filter((s) => s.state === "done").length;
  const current = steps.find((s) => s.state === "current") ?? steps[steps.length - 1];
  return (
    <ol
      aria-label={`Progress: step ${Math.min(done + 1, steps.length)} of ${steps.length}, ${current.label}`}
      className={cx("flex items-center gap-2", className)}
    >
      {steps.map((s) => {
        const fill = s.state === "done" ? 1 : s.state === "current" ? 0.5 : 0;
        return (
          <li key={s.id} className="flex items-center gap-2" aria-current={s.state === "current" ? "step" : undefined}>
            <span className="flex flex-col gap-1">
              <span className="flex items-center gap-1.5 text-xs leading-none">
                <span className={s.state === "next" ? "text-fg-muted" : "text-fg"}>{s.label}</span>
                {s.tag && (
                  <span className="rounded-sm border border-line px-1 py-px text-[10px] leading-none text-fg-muted">{s.tag}</span>
                )}
                {s.state === "done" && <span className="sr-only">(done)</span>}
              </span>
              <span className="relative h-0.5 w-14 overflow-hidden rounded-full bg-bg-3 sm:w-16" aria-hidden>
                <motion.span
                  className="absolute inset-y-0 left-0 rounded-full bg-accent"
                  initial={false}
                  animate={{ width: `${fill * 100}%` }}
                  transition={rm ? { duration: 0 } : SPRING.gentle}
                />
              </span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
