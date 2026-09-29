"use client";

import { cx } from "@/components/ui";

/** An on/off switch (role="switch"): white track when on, like the one primary colour. */
export function Switch({ label, checked, onChange, disabled }: { label: string; checked: boolean; onChange: (next: boolean) => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cx(
        "relative inline-flex h-7 w-12 shrink-0 cursor-pointer items-center rounded-full border transition-colors duration-fast ease-standard focus-visible:focus-ring disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "border-primary bg-primary" : "border-line bg-bg-3",
      )}
    >
      <span
        aria-hidden
        className={cx(
          "inline-block size-5 rounded-full transition-transform duration-fast ease-standard",
          checked ? "translate-x-6 bg-primary-fg" : "translate-x-1 bg-fg-muted",
        )}
      />
    </button>
  );
}
