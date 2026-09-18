"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Button } from "@/components/ui";
import { DUR, EASE } from "@/lib/motion/tokens";
import { useStudioStore } from "@/lib/stores/studio";
import { runPlanning, useLabour } from "./useLabour";

type Props = {
  /** The prompt textarea, refocused by "Rewrite prompt". */
  promptRef: React.RefObject<HTMLTextAreaElement | null>;
};

/**
 * Compatibility warning (spec 6.3), one slim strip above the composer: the director
 * returned a valid static-subject plan with a `capability_mismatch`. No version exists
 * and nothing was charged until "Use this scene"; that runs behind the planning
 * sequence like any other append.
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
          initial={{ opacity: 0, y: rm ? 0 : 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: rm ? 0 : 6, transition: { duration: rm ? 0 : DUR.fast } }}
          transition={{ duration: rm ? 0 : DUR.base, ease: EASE.emphasized }}
          className="flex w-full flex-col gap-2 rounded-xl border border-line bg-bg-1/95 px-4 py-2.5 backdrop-blur-sm sm:flex-row sm:items-center sm:gap-3"
        >
          <p className="min-w-0 flex-1 text-sm text-fg">{warning.message}</p>
          <div className="flex shrink-0 gap-1">
            <Button size="sm" variant="ghost" onClick={onRewrite} disabled={labouring}>Rewrite prompt</Button>
            <Button size="sm" variant="primary" onClick={onAccept} disabled={labouring}>Use this scene</Button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
