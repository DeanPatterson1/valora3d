"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { DUR, EASE } from "@/lib/motion/tokens";
import { cx } from "@/components/ui";
import { LABOUR_MIN_MS, scheduleSteps } from "./labour";

export type LabourSequenceProps = {
  steps: readonly string[];
  /** True once the real work has finished; `onDone` still waits for the minimum. */
  workDone: boolean;
  /** Fired exactly once, at max(LABOUR_MIN_MS, the moment `workDone` became true). */
  onDone: () => void;
  className?: string;
};

/**
 * Labour illusion (spec 10): named steps reveal on a schedule for at least
 * LABOUR_MIN_MS, so even an instant result reads as considered work. Mount it
 * when work starts; unmount it in `onDone`. Under reduced motion every step
 * lists at once but the minimum hold still applies.
 */
export function LabourSequence({ steps, workDone, onDone, className }: LabourSequenceProps) {
  const rm = useReducedMotion() ?? false;
  const [start] = useState(() => performance.now());
  const [revealed, setRevealed] = useState(0);
  const onDoneRef = useRef(onDone);
  const fired = useRef(false);
  useEffect(() => { onDoneRef.current = onDone; });

  const stepKey = steps.join("|");

  // Reveal steps on the schedule, measured from mount so a late effect never bunches them up.
  useEffect(() => {
    if (rm) return; // every step is shown at render under reduced motion
    const elapsed = performance.now() - start;
    const timers = scheduleSteps(steps).map((s, i) =>
      window.setTimeout(() => setRevealed((n) => Math.max(n, i + 1)), Math.max(0, s.at - elapsed)),
    );
    return () => timers.forEach((t) => window.clearTimeout(t));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- steps identity is tracked by stepKey
  }, [stepKey, rm, start]);

  // Finish at max(minimum, work done): the parent unmounts this in onDone.
  useEffect(() => {
    if (!workDone || fired.current) return;
    const remaining = Math.max(0, LABOUR_MIN_MS - (performance.now() - start));
    const t = window.setTimeout(() => {
      if (fired.current) return;
      fired.current = true;
      onDoneRef.current();
    }, remaining);
    return () => window.clearTimeout(t);
  }, [workDone, start]);

  return (
    <ol aria-live="polite" className={cx("flex flex-col gap-2", className)}>
      {steps.map((label, i) => {
        const shown = rm || i < revealed;
        return (
          <li key={label} className="flex h-6 items-center gap-2.5 text-sm" aria-hidden={!shown || undefined}>
            <motion.span
              className="flex size-5 shrink-0 items-center justify-center rounded-full border border-line bg-bg-2"
              initial={false}
              animate={{ borderColor: shown ? "var(--color-primary)" : "var(--color-line)", opacity: shown ? 1 : 0.35 }}
              transition={{ duration: rm ? 0 : DUR.fast }}
            >
              <svg aria-hidden viewBox="0 0 16 16" className="size-3 text-primary" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <motion.path
                  d="M3.5 8.5l3 3 6-7"
                  initial={false}
                  animate={{ pathLength: shown ? 1 : 0, opacity: shown ? 1 : 0 }}
                  transition={{ duration: rm ? 0 : DUR.base, ease: EASE.emphasized }}
                />
              </svg>
            </motion.span>
            <motion.span
              className="text-fg"
              initial={false}
              animate={{ opacity: shown ? 1 : 0, x: shown || rm ? 0 : -6 }}
              transition={{ duration: rm ? 0 : DUR.base, ease: EASE.standard }}
            >
              {label}
            </motion.span>
          </li>
        );
      })}
    </ol>
  );
}
