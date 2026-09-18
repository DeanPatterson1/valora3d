"use client";

import Link from "next/link";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { cx } from "@/components/ui";
import { Scrubber } from "@/components/viewer/Scrubber";
import { DUR, EASE } from "@/lib/motion/tokens";
import { CREDIT_COSTS } from "@/lib/pricing";
import type { ScenePlan } from "@/lib/schema";
import type { ServiceError } from "@/lib/services";
import { useCreditsStore } from "@/lib/stores/credits";
import { useStudioStore } from "@/lib/stores/studio";
import { ComposerMenu } from "./ComposerMenu";
import { PLANNING_STEPS } from "./labour";
import { LabourSequence } from "./LabourSequence";
import { OutputSettings } from "./OutputSettings";
import { PRESETS, SUGGESTED_PRESETS } from "./presets";
import { PromptErrors } from "./PromptErrors";
import { runPlanning, useLabour, useLabourStore } from "./useLabour";
import { useStudioUi } from "./useStudioUi";
import { WarningBanner } from "./WarningBanner";

const PLACEHOLDER_MS = 6000;
const PLACEHOLDER_MAX = 56;

/** Placeholders stay on one line: cut at a word boundary with an ellipsis. */
function shorten(prompt: string): string {
  if (prompt.length <= PLACEHOLDER_MAX) return prompt;
  const cut = prompt.slice(0, PLACEHOLDER_MAX);
  return `${cut.slice(0, cut.lastIndexOf(" "))}…`;
}
const LINE_PX = 24;
const MAX_LINES = 6;

type Props = {
  /** Owned by the shell so the warning strip can refocus the input. */
  promptRef?: React.RefObject<HTMLTextAreaElement | null>;
  /** The plan the viewer shows (frozen during labour); drives the scrubber. */
  plan?: ScenePlan | null;
  previewSeconds?: number | null;
  onScrub?: (seconds: number | null) => void;
};

/**
 * The floating composer (spec 8, revised): `+` menu, an auto-growing textarea and a
 * round send button, in one pill. A second row with the output-settings chip and a
 * Controls chip appears only once a scene exists. Notices (warning, error, low credits)
 * are one slim strip above it, one at a time. While the director works, the planning
 * steps take the textarea's place; the viewer and history (frozen by `useLabour`)
 * reveal the new version when the steps finish.
 */
export function Composer({ promptRef, plan = null, previewSeconds = null, onScrub }: Props) {
  const rm = useReducedMotion() ?? false;
  const ownRef = useRef<HTMLTextAreaElement>(null);
  const textareaRef = promptRef ?? ownRef;

  const analysis = useStudioStore((s) => s.analysis);
  const asset = useStudioStore((s) => s.asset);
  const blobMissing = useStudioStore((s) => s.blobMissing);
  const versionCount = useStudioStore((s) => s.versions.length);
  const busy = useStudioStore((s) => s.busy);
  const storeError = useStudioStore((s) => s.error);
  const warning = useStudioStore((s) => s.pendingWarning);
  const submitPrompt = useStudioStore((s) => s.submitPrompt);
  const startOver = useStudioStore((s) => s.startOver);
  const balance = useCreditsStore((s) => s.balance);
  const creditsLoaded = useCreditsStore((s) => s.loaded);
  const { labouring, planning, frozenVersionCount, end } = useLabour();
  const openDrawer = useStudioUi((s) => s.openDrawer);
  const scrubberOpen = useStudioUi((s) => s.scrubberOpen);
  const setScrubberOpen = useStudioUi((s) => s.setScrubberOpen);

  const [text, setText] = useState("");
  const [localError, setLocalError] = useState<ServiceError | null>(null);

  const hasModel = asset !== null && !blobMissing;
  // The second row and suggestions follow the labour sequence, like the viewer.
  const hasVersion = (labouring ? frozenVersionCount : versionCount) > 0;
  const nextCost = versionCount > 0 ? CREDIT_COSTS.prompt_edit : CREDIT_COSTS.scene_generation;
  const trimmed = text.trim();
  const locked = labouring || busy !== null;
  const ready = hasModel && analysis !== null;
  const canSubmit = !locked && ready && trimmed.length > 0;
  const lowCredits = creditsLoaded && ready && balance < nextCost;
  const error = localError ?? storeError;

  // Example prompts rotate through the placeholder while the box is empty and a model is loaded.
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  useEffect(() => {
    if (text || !ready) return;
    const t = window.setInterval(() => setPlaceholderIdx((i) => (i + 1) % (PRESETS.length + 1)), PLACEHOLDER_MS);
    return () => window.clearInterval(t);
  }, [text, ready]);
  const placeholder = !hasModel
    ? "Load a model first"
    : placeholderIdx === 0
      ? "Describe the shot you want"
      : shorten(PRESETS[placeholderIdx - 1].prompt);

  // 1–6 lines, then the box scrolls. Empty stays one line whatever the placeholder.
  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${text ? Math.min(el.scrollHeight, LINE_PX * MAX_LINES) : LINE_PX}px`;
  }, [textareaRef, text, planning]);

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
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      onSubmit();
    }
  };

  const submitLabel = versionCount > 0 ? `Apply edit · ${CREDIT_COSTS.prompt_edit} credit` : `Generate scene · ${CREDIT_COSTS.scene_generation} credits`;
  const fade = { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: { duration: rm ? 0 : DUR.fast } };
  const rise = {
    initial: { opacity: 0, y: rm ? 0 : 6 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: rm ? 0 : 6, transition: { duration: rm ? 0 : DUR.fast } },
    transition: { duration: rm ? 0 : DUR.base, ease: EASE.standard },
  };

  const showSuggestions = ready && !hasVersion && !labouring && !warning;

  return (
    <div className="pointer-events-auto flex w-full max-w-[768px] flex-col items-center gap-3" data-composer>
      {/* Empty-state suggestions: three example prompts, gone once a scene exists. */}
      {showSuggestions && (
          <motion.ul key="suggestions" initial={rise.initial} animate={rise.animate} transition={rise.transition} aria-label="Example prompts" className="flex flex-wrap justify-center gap-2">
            {SUGGESTED_PRESETS.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  disabled={locked}
                  onClick={() => fill(p.prompt)}
                  className="h-9 cursor-pointer rounded-full border border-line bg-bg-0/70 px-3.5 text-sm text-fg-muted backdrop-blur-sm transition-colors duration-fast ease-standard hover:bg-bg-2 hover:text-fg focus-visible:focus-ring disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {p.label}
                </button>
              </li>
            ))}
          </motion.ul>
      )}

      {/* One notice at a time: warning, then error, then low credits. */}
      <div className="w-full empty:hidden">
        {warning ? (
          <WarningBanner promptRef={textareaRef} />
        ) : error && !labouring ? (
          <PromptErrors onHint={fill} local={localError} onDismissLocal={() => setLocalError(null)} />
        ) : (
          <AnimatePresence initial={false}>
            {lowCredits && (
              <motion.p key="low" {...fade} role="status" data-testid="low-credits" className="rounded-xl border border-line bg-bg-1/95 px-4 py-2 text-sm text-fg-muted backdrop-blur-sm">
                You have {balance} {balance === 1 ? "credit" : "credits"}; the next {versionCount > 0 ? "edit" : "scene"} costs {nextCost}.{" "}
                <Link href="/pricing" className="rounded-sm text-fg underline underline-offset-2 focus-visible:focus-ring">
                  Get credits
                </Link>
              </motion.p>
            )}
          </AnimatePresence>
        )}
      </div>

      {/* Camera-path scrubber, revealed by the "Preview path" chip. */}
      <AnimatePresence initial={false}>
        {scrubberOpen && plan && hasVersion && onScrub && (
          <motion.div key="scrubber" {...rise} className="w-full">
            <Scrubber plan={plan} seconds={previewSeconds} onChange={onScrub} disabled={labouring} className="rounded-xl border border-line bg-bg-1/95 backdrop-blur-sm" />
          </motion.div>
        )}
      </AnimatePresence>

      <div className={cx("relative flex w-full flex-col rounded-3xl bg-bg-2 px-2.5 py-2 shadow-raise", !hasModel && "opacity-70")}>
        <div className="flex items-end gap-2">
          <ComposerMenu
            disabled={locked}
            showPresets={hasVersion}
            onPreset={(p) => fill(p.prompt)}
            hasVersion={hasVersion}
            startOver={canSubmit ? onStartOver : null}
          />

          {planning ? (
            <div className="flex min-h-9 min-w-0 flex-1 items-center px-1 py-1.5">
              <LabourSequence steps={PLANNING_STEPS} workDone={planning.done} onDone={onDone} className="gap-1" />
            </div>
          ) : (
            <textarea
              ref={textareaRef}
              aria-label="Describe your render"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={onKeyDown}
              disabled={locked || !hasModel}
              rows={1}
              placeholder={placeholder}
              className="my-1.5 min-h-6 w-full min-w-0 flex-1 resize-none bg-transparent px-1 text-base leading-6 text-fg outline-none placeholder:text-fg-muted/80 disabled:cursor-not-allowed"
            />
          )}

          <button
            type="button"
            onClick={onSubmit}
            disabled={!canSubmit}
            aria-label={submitLabel}
            title={submitLabel}
            className="flex size-9 shrink-0 cursor-pointer items-center justify-center rounded-full bg-fg text-bg-0 transition-colors duration-fast ease-standard hover:bg-white focus-visible:focus-ring disabled:cursor-not-allowed disabled:bg-fg/30 disabled:text-bg-0/80"
          >
            <svg aria-hidden viewBox="0 0 20 20" className="size-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10 16V4m0 0-5 5m5-5 5 5" />
            </svg>
          </button>
        </div>

        {/* Second row: only once a scene exists. */}
        <AnimatePresence initial={false}>
          {hasVersion && (
            <motion.div
              key="row2"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: rm ? 0 : DUR.base, ease: EASE.standard }}
              className="overflow-hidden"
            >
              <div className="flex flex-wrap items-center gap-1 px-1 pt-1.5">
                <OutputSettings disabled={locked} />
                <ChipButton onClick={() => openDrawer("controls")} aria-label="Controls" aria-controls="scene-drawer">
                  <svg aria-hidden viewBox="0 0 16 16" className="size-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                    <path d="M2 5h7M12 5h2M2 11h3M8 11h6" />
                    <circle cx="10.5" cy="5" r="1.5" /><circle cx="6.5" cy="11" r="1.5" />
                  </svg>
                  Controls
                </ChipButton>
                <ChipButton
                  onClick={() => setScrubberOpen(!scrubberOpen)}
                  aria-pressed={scrubberOpen}
                  aria-label="Preview path"
                  selected={scrubberOpen}
                  disabled={!plan}
                >
                  <svg aria-hidden viewBox="0 0 16 16" className="size-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M6.5 4.5 11 8l-4.5 3.5v-7Z" />
                  </svg>
                  Preview path
                </ChipButton>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

type ChipButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & { selected?: boolean };

/** Small in-composer chip, the same idiom as the output-settings summary. */
export function ChipButton({ selected, className, children, ...rest }: ChipButtonProps) {
  return (
    <button
      type="button"
      className={cx(
        "inline-flex h-8 cursor-pointer select-none items-center gap-1.5 whitespace-nowrap rounded-full px-3 text-xs transition-colors duration-fast ease-standard focus-visible:focus-ring disabled:cursor-not-allowed disabled:opacity-40",
        selected ? "bg-bg-3 text-fg" : "text-fg-muted hover:bg-bg-3 hover:text-fg",
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}
