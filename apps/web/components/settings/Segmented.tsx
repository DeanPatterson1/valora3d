"use client";

import { useRef } from "react";
import { cx } from "@/components/ui";

export type SegmentedOption<T extends string | number> = { value: T; label: string; disabled?: boolean };

export type SegmentedProps<T extends string | number> = {
  label: string;
  options: readonly SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  disabled?: boolean;
};

/** A radio group drawn as one pill; arrow keys move the selection. */
export function Segmented<T extends string | number>({ label, options, value, onChange, disabled }: SegmentedProps<T>) {
  const ref = useRef<HTMLDivElement>(null);

  const move = (from: number, delta: number) => {
    // Arrow keys skip options that cannot be chosen.
    let i = from;
    for (let step = 0; step < options.length; step++) {
      i = (i + delta + options.length) % options.length;
      if (!options[i]?.disabled) break;
    }
    const next = options[i];
    if (!next || next.disabled) return;
    onChange(next.value);
    ref.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[i]?.focus();
  };

  return (
    <div ref={ref} role="radiogroup" aria-label={label} className="inline-flex w-fit max-w-full flex-wrap items-center gap-0.5 rounded-full border border-line bg-bg-0 p-1">
      {options.map((o, i) => {
        const checked = o.value === value;
        return (
          <button
            key={String(o.value)}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={checked ? 0 : -1}
            disabled={disabled || o.disabled}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); move(i, 1); }
              if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); move(i, -1); }
            }}
            className={cx(
              "h-10 cursor-pointer rounded-full px-3 text-xs tabular transition-colors duration-fast ease-standard focus-visible:focus-ring disabled:cursor-not-allowed disabled:opacity-50 sm:h-8",
              checked ? "bg-bg-3 text-fg" : "text-fg-muted hover:text-fg",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
