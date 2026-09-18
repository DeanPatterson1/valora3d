"use client";

import { useRef } from "react";
import { cx } from "@/components/ui";

export type SegmentedOption<T extends string | number> = { value: T; label: string };

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
    const i = (from + delta + options.length) % options.length;
    const next = options[i];
    if (!next) return;
    onChange(next.value);
    ref.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[i]?.focus();
  };

  return (
    <div ref={ref} role="radiogroup" aria-label={label} className="inline-flex w-fit items-center gap-0.5 rounded-full bg-bg-1 p-1">
      {options.map((o, i) => {
        const checked = o.value === value;
        return (
          <button
            key={String(o.value)}
            type="button"
            role="radio"
            aria-checked={checked}
            tabIndex={checked ? 0 : -1}
            disabled={disabled}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); move(i, 1); }
              if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); move(i, -1); }
            }}
            className={cx(
              "h-7 cursor-pointer rounded-full px-3 text-xs tabular transition-colors duration-fast ease-standard focus-visible:focus-ring disabled:cursor-not-allowed disabled:opacity-50",
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
