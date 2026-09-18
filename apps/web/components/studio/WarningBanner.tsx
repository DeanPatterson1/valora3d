"use client";

import { AnimatePresence, motion, useReducedMotion, type Variants } from "motion/react";
import { Button } from "@/components/ui";
import { DUR, EASE } from "@/lib/motion/tokens";
import { reduced } from "@/lib/motion/variants";
import { useStudioStore } from "@/lib/stores/studio";
import { runPlanning, useLabour } from "./useLabour";

/** Rises from the bottom edge of the viewer; the sibling of `panelSlide` for the y axis. */
const bannerSlide: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: DUR.base, ease: EASE.emphasized } },
  exit: { opacity: 0, y: 24, transition: { duration: DUR.fast, ease: EASE.standard } },
};

type Props = {
  /** The prompt textarea, refocused by "Rewrite prompt". */
  promptRef: React.RefObject<HTMLTextAreaElement | null>;
};

/**
 * Compatibility warning (spec 6.3): the director returned a valid static-subject plan
 * with a `capability_mismatch`. No version exists and nothing was charged until
 * "Use this scene"; that runs behind the planning sequence like any other append.
 */
export function WarningBanner({ promptRef }: Props) {
  const rm = useReducedMotion() ?? false;
  const warning = useStudioStore((s) => s.pendingWarning);
  const acceptPending = useStudioStore((s) => s.acceptPending);
  const dismissPending = useStudioStore((s) => s.dismissPending);
  const { labouring } = useLabour();

  const onAccept = () => {
    if (labouring) return;
    void runPlanning(acceptPending);
  };
  const onRewrite = () => {
    dismissPending();
    const el = promptRef.current;
    if (el) {
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
    }
  };

  return (
    <AnimatePresence>
      {warning && (
        <motion.div
          key="warning"
          role="status"
          aria-live="polite"
          data-testid="warning-banner"
          variants={rm ? reduced(bannerSlide) : bannerSlide}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="absolute inset-x-3 bottom-3 z-10 flex flex-col gap-3 rounded-lg border border-accent/40 bg-bg-1/95 p-3 shadow-raise backdrop-blur-sm sm:inset-x-auto sm:left-1/2 sm:w-[min(36rem,calc(100%-1.5rem))] sm:-translate-x-1/2 sm:flex-row sm:items-center"
        >
          <div className="flex min-w-0 flex-1 items-start gap-2.5">
            <svg aria-hidden viewBox="0 0 16 16" className="mt-0.5 size-4 shrink-0 text-accent" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M8 2.5 14 13H2L8 2.5Z" />
              <path d="M8 6.5v3M8 11.5v.01" />
            </svg>
            <p className="text-sm text-fg">{warning.message}</p>
          </div>
          <div className="flex shrink-0 gap-2">
            <Button size="sm" variant="ghost" onClick={onRewrite} disabled={labouring}>Rewrite prompt</Button>
            <Button size="sm" variant="primary" onClick={onAccept} disabled={labouring}>Use this scene</Button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
