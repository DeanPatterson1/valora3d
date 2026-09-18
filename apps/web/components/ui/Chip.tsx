"use client";

import { motion } from "motion/react";
import { scalePress } from "@/lib/motion/variants";
import { cx } from "./cx";

export type ChipProps = {
  selected?: boolean;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
  children: React.ReactNode;
};

/** A selectable pill. Used for presets and example prompts. 36px tall on touch widths, 32px from `sm` up. */
export function Chip({ selected = false, onClick, disabled, className, children }: ChipProps) {
  return (
    <motion.button
      type="button"
      aria-pressed={selected}
      disabled={disabled}
      onClick={onClick}
      whileTap={disabled ? undefined : scalePress.whileTap}
      transition={scalePress.transition}
      className={cx(
        "inline-flex min-h-9 cursor-pointer select-none items-center rounded-full border px-3 text-sm transition-colors duration-fast ease-standard focus-visible:focus-ring disabled:cursor-not-allowed disabled:opacity-50 sm:h-8 sm:min-h-0",
        selected
          ? "border-primary bg-bg-3 text-fg"
          : "border-line bg-transparent text-fg-muted hover:bg-bg-3 hover:text-fg",
        className,
      )}
    >
      {children}
    </motion.button>
  );
}
