"use client";

import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Chip } from "@/components/ui";
import { DUR } from "@/lib/motion/tokens";
import type { ServiceError } from "@/lib/services";
import { useStudioStore } from "@/lib/stores/studio";

type Props = {
  /** Chip text goes into the textarea without submitting. */
  onHint: (text: string) => void;
  /** An error the dock holds itself (e.g. a `busy` refusal, which the store does not keep). */
  local?: ServiceError | null;
  onDismissLocal?: () => void;
  className?: string;
};

/** The wording for each director/store error code; anything unknown falls back to the service message. */
function copy(error: ServiceError): { message: string; pricing?: boolean } {
  switch (error.code) {
    case "edit_not_understood":
      return { message: error.message || "I didn't catch that. Try one of these:" };
    case "at_limit":
      return { message: error.message || "That's already as far as it goes." };
    case "insufficient_credits":
      return { message: error.message || "Not enough credits for that.", pricing: true };
    case "busy":
      return { message: "Still working on the last change." };
    case "no_model":
      return { message: "Load a model first." };
    default:
      return { message: error.message || "Something went wrong. Try again." };
  }
}

/**
 * Inline, recoverable prompt errors (spec 11). Reads and clears the studio store's
 * error; `edit_not_understood` turns its hints into chips that refill the textarea.
 */
export function PromptErrors({ onHint, local = null, onDismissLocal, className }: Props) {
  const rm = useReducedMotion() ?? false;
  const storeError = useStudioStore((s) => s.error);
  const clearError = useStudioStore((s) => s.clearError);
  const error = local ?? storeError;

  const dismiss = () => {
    if (local) onDismissLocal?.();
    else clearError();
  };

  return (
    <AnimatePresence initial={false}>
      {error && (
        <motion.div
          key={`${error.code}:${error.message}`}
          role="alert"
          data-testid="prompt-error"
          className={className ? `flex flex-col gap-2 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-fg ${className}` : "flex flex-col gap-2 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-fg"}
          initial={{ opacity: 0, y: rm ? 0 : 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, transition: { duration: rm ? 0 : DUR.fast } }}
          transition={{ duration: rm ? 0 : DUR.fast }}
        >
          <div className="flex items-start gap-3">
            <span className="flex-1">
              <ErrorBody error={error} />
            </span>
            <button
              type="button"
              onClick={dismiss}
              aria-label="Dismiss"
              className="rounded-sm px-1 text-fg-muted hover:text-fg focus-visible:focus-ring"
            >
              ×
            </button>
          </div>
          {error.code === "edit_not_understood" && error.hints && error.hints.length > 0 && (
            <ul aria-label="Suggested phrasings" className="flex flex-wrap gap-2">
              {error.hints.map((h) => {
                const text = stripTry(h);
                return (
                  <li key={h}>
                    <Chip onClick={() => { onHint(text); dismiss(); }}>{text}</Chip>
                  </li>
                );
              })}
            </ul>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function ErrorBody({ error }: { error: ServiceError }) {
  const c = copy(error);
  return (
    <>
      {c.message}
      {c.pricing && (
        <>
          {" "}
          <Link href="/pricing" className="rounded-sm underline underline-offset-2 hover:text-accent focus-visible:focus-ring">
            Get credits
          </Link>
        </>
      )}
    </>
  );
}

/** `Try: "make it darker"` → `make it darker`, so the chip fills the box with something submittable. */
export function stripTry(hint: string): string {
  const m = hint.match(/^\s*try:?\s*["“]?(.*?)["”]?\s*$/i);
  return m ? m[1] : hint;
}
