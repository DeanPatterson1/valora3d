"use client";

import { useId } from "react";
import { cx } from "@/components/ui";

/** One-question multiple choice: native radios (keyboard and screen readers for free), each a full-width row. */
export function ChoiceList<T extends string>({
  legend,
  options,
  value,
  onChange,
  columns = 1,
}: {
  legend: string;
  options: readonly { id: T; label: string; hint?: string }[];
  value: T | null;
  onChange: (value: T) => void;
  columns?: 1 | 3;
}) {
  const name = useId();
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2 text-sm text-fg">{legend}</legend>
      <div className={cx("grid gap-1.5", columns === 3 && "grid-cols-3")}>
        {options.map((o) => {
          const checked = value === o.id;
          return (
            <label
              key={o.id}
              className={cx(
                "flex min-h-11 cursor-pointer items-center gap-3 rounded-md border px-3 py-2 text-sm transition-colors duration-fast ease-standard has-[:focus-visible]:focus-ring",
                checked ? "border-fg/60 bg-bg-3 text-fg" : "border-line text-fg hover:bg-bg-3",
                columns === 3 && "justify-center text-center",
              )}
            >
              <input
                type="radio"
                name={name}
                value={o.id}
                checked={checked}
                onChange={() => onChange(o.id)}
                className={cx("size-4 shrink-0 accent-[var(--color-fg)]", columns === 3 && "sr-only")}
              />
              <span className="flex min-w-0 flex-col">
                <span>{o.label}</span>
                {o.hint && columns === 1 && <span className="text-xs text-fg-muted">{o.hint}</span>}
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

/** A plain multi-line text box in the kit's style (the kit's Field is single-line). */
export function TextArea({
  label,
  value,
  onChange,
  maxLength,
  rows = 3,
  placeholder,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  maxLength: number;
  rows?: number;
  placeholder?: string;
  hint?: string;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm text-fg">
        {label}
      </label>
      <textarea
        id={id}
        rows={rows}
        maxLength={maxLength}
        value={value}
        placeholder={placeholder}
        aria-describedby={hint ? `${id}-hint` : undefined}
        onChange={(e) => onChange(e.target.value)}
        className="w-full resize-y rounded-sm border border-line bg-bg-2 px-3 py-2 text-sm text-fg outline-none transition-colors duration-fast ease-standard placeholder:text-fg-muted/70 hover:border-fg-muted/40 focus-visible:focus-ring"
      />
      {hint && (
        <p id={`${id}-hint`} className="text-xs text-fg-muted">
          {hint}
        </p>
      )}
    </div>
  );
}
