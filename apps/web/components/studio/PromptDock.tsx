"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Button, cx } from "@/components/ui";
import { DUR } from "@/lib/motion/tokens";
import { CREDIT_COSTS } from "@/lib/pricing";
import type { ServiceError } from "@/lib/services";
import { useCreditsStore } from "@/lib/stores/credits";
import { useStudioStore } from "@/lib/stores/studio";
import { PLANNING_STEPS } from "./labour";
import { LabourSequence } from "./LabourSequence";
import { OutputSettings } from "./OutputSettings";
import { PresetChips } from "./PresetChips";
import { PRESETS } from "./presets";
import { PromptErrors } from "./PromptErrors";
import { runPlanning, useLabour, useLabourStore } from "./useLabour";

const PLACEHOLDER_MS = 5000;

type Props = {
  /** Owned by the shell so the warning banner can refocus the input. */
  promptRef?: React.RefObject<HTMLTextAreaElement | null>;
};

/**
 * Bottom dock (spec 8, 9, 10): preset chips, the prompt textarea, output settings and
 * the primary action. Submitting runs the store call behind the planning labour
 * sequence; the input and buttons stay disabled until the sequence finishes, and the
 * viewer/rail (frozen by `useLabour`) reveal the new version at that same moment.
 */
export function PromptDock({ promptRef }: Props) {
  const rm = useReducedMotion() ?? false;
  const ownRef = useRef<HTMLTextAreaElement>(null);
  const textareaRef = promptRef ?? ownRef;

  const analysis = useStudioStore((s) => s.analysis);
  const versionCount = useStudioStore((s) => s.versions.length);
  const busy = useStudioStore((s) => s.busy);
  const submitPrompt = useStudioStore((s) => s.submitPrompt);
  const startOver = useStudioStore((s) => s.startOver);
  const balance = useCreditsStore((s) => s.balance);
  const creditsLoaded = useCreditsStore((s) => s.loaded);
  const { labouring, planning, end } = useLabour();

  const [text, setText] = useState("");
  const [localError, setLocalError] = useState<ServiceError | null>(null);

  const hasVersion = versionCount > 0;
  const nextCost = hasVersion ? CREDIT_COSTS.prompt_edit : CREDIT_COSTS.scene_generation;
  const trimmed = text.trim();
  const locked = labouring || busy !== null;
  const canSubmit = !locked && analysis !== null && trimmed.length > 0;
  const lowCredits = creditsLoaded && analysis !== null && balance < nextCost;
  const activePreset = PRESETS.find((p) => p.prompt === trimmed)?.id ?? null;

  // Example placeholder rotates through the presets while the box is empty.
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  useEffect(() => {
    if (text) return;
    const t = window.setInterval(() => setPlaceholderIdx((i) => (i + 1) % PRESETS.length), PLACEHOLDER_MS);
    return () => window.clearInterval(t);
  }, [text]);

  const fill = (value: string) => {
    setText(value);
    const el = textareaRef.current;
    if (el) {
      el.focus();
      // Caret at the end so the user can keep typing.
      requestAnimationFrame(() => el.setSelectionRange(el.value.length, el.value.length));
    }
  };

  const run = (work: () => ReturnType<typeof submitPrompt>) => {
    setLocalError(null);
    void runPlanning(work).then((r) => {
      if (!r.ok && r.error.code === "busy") setLocalError(r.error);
    });
  };
  const onSubmit = () => { if (canSubmit) run(() => submitPrompt(trimmed)); };
  const onStartOver = () => { if (canSubmit) run(() => startOver(trimmed)); };

  const onDone = () => {
    // The prompt became a version (submit, start over or "Use this scene"): clear the box for the next one.
    if (useStudioStore.getState().versions.length > useLabourStore.getState().frozenVersionCount) setText("");
    end();
    void useCreditsStore.getState().refresh();
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      onSubmit();
    }
  };

  const submitLabel = hasVersion ? `Apply edit · ${CREDIT_COSTS.prompt_edit} credit` : `Generate scene · ${CREDIT_COSTS.scene_generation} credits`;
  const fade = { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: { duration: rm ? 0 : DUR.fast } };

  return (
    <div className="flex w-full max-w-full flex-col gap-2 px-3 py-3 sm:px-4" data-prompt-dock>
      <AnimatePresence initial={false}>
        {lowCredits && (
          <motion.p key="low" {...fade} role="status" className="text-xs text-fg-muted" data-testid="low-credits">
            <span className="text-accent">You have {balance} {balance === 1 ? "credit" : "credits"}.</span>{" "}
            The next {hasVersion ? "edit" : "scene"} costs {nextCost}.{" "}
            <Link href="/pricing" className="rounded-sm text-fg underline underline-offset-2 hover:text-accent focus-visible:focus-ring">
              Get credits
            </Link>
          </motion.p>
        )}
      </AnimatePresence>

      {!labouring && <PromptErrors onHint={fill} local={localError} onDismissLocal={() => setLocalError(null)} />}

      {/* Chips row, swapped for the planning steps while the director works. */}
      <div className="min-h-8">
        {planning ? (
          <LabourSequence
            steps={PLANNING_STEPS}
            workDone={planning.done}
            onDone={onDone}
            className="sm:flex-row sm:flex-wrap sm:gap-x-5 sm:gap-y-1"
          />
        ) : (
          <div className="-mx-3 overflow-x-auto px-3 sm:-mx-4 sm:px-4 [scrollbar-width:none]">
            <PresetChips onPick={(p) => fill(p.prompt)} disabled={locked} activeId={activePreset} />
          </div>
        )}
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <textarea
          ref={textareaRef}
          aria-label="Describe your render"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={locked}
          rows={2}
          placeholder={analysis ? `e.g. ${PRESETS[placeholderIdx].prompt}` : "Load a model, then describe the shot you want"}
          className={cx(
            "min-h-10 w-full flex-1 resize-none rounded-md border border-line bg-bg-0 px-3 py-2 text-sm text-fg outline-none transition-colors duration-fast ease-standard placeholder:text-fg-muted/70",
            "focus-visible:focus-ring focus:border-fg-muted/60 disabled:cursor-not-allowed disabled:opacity-60",
          )}
        />
        <div className="flex flex-wrap items-center justify-end gap-2">
          <OutputSettings disabled={locked} />
          {hasVersion && (
            <span title={trimmed ? undefined : "Type a new prompt first"} className="inline-flex">
              <Button
                variant="ghost"
                onClick={onStartOver}
                disabled={!canSubmit}
                aria-label={`Start over · ${CREDIT_COSTS.scene_generation} credits`}
              >
                Start over
              </Button>
            </span>
          )}
          <Button variant="primary" onClick={onSubmit} disabled={!canSubmit} loading={locked && planning !== null}>
            {submitLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
