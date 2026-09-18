"use client";

import { useId } from "react";
import { cx } from "./cx";

export type FieldProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, "id"> & {
  label: string;
  error?: string;
  hint?: string;
  className?: string;
  /** Extra classes on the <input> itself (e.g. a taller control on auth pages). */
  inputClassName?: string;
  /** Slot rendered inside the control's right edge, e.g. a show/hide toggle. */
  trailing?: React.ReactNode;
  ref?: React.Ref<HTMLInputElement>;
};

export function Field({ label, error, hint, className, inputClassName, trailing, ...input }: FieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(" ") || undefined;

  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-sm text-fg">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cx(
            "h-9 w-full rounded-sm border bg-bg-2 px-3 text-sm text-fg placeholder:text-fg-muted/70 transition-colors duration-fast ease-standard outline-none focus-visible:focus-ring disabled:cursor-not-allowed disabled:opacity-50",
            error ? "border-danger" : "border-line hover:border-fg-muted/40",
            trailing ? "pr-16" : undefined,
            inputClassName,
          )}
          {...input}
        />
        {trailing && <div className="absolute inset-y-0 right-1.5 flex items-center">{trailing}</div>}
      </div>
      {error ? (
        <p id={errorId} className="text-sm text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-sm text-fg-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
