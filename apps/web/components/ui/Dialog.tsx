"use client";

import { useEffect, useId, useRef } from "react";
import { cx } from "./cx";

export type DialogProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children?: React.ReactNode;
  /** Action row, usually Buttons. */
  footer?: React.ReactNode;
  className?: string;
};

/** Native <dialog> wrapper. `showModal()` gives focus trapping and Escape for free. */
export function Dialog({ open, onClose, title, description, children, footer, className }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  const titleId = `${id}-title`;
  const descId = `${id}-desc`;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    else if (!open && el.open) el.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => {
        // Only the backdrop is the dialog element itself; clicks inside land on children.
        if (e.target === e.currentTarget) onClose();
      }}
      aria-labelledby={titleId}
      aria-describedby={description ? descId : undefined}
      className={cx(
        "m-auto w-[min(92vw,28rem)] rounded-lg bg-bg-2 p-0 text-fg shadow-raise backdrop:bg-black/60 open:animate-fade-in motion-reduce:animate-none",
        className,
      )}
    >
      <div className="flex flex-col gap-4 p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h2 id={titleId} className="text-xl font-semibold tracking-tight text-fg">
              {title}
            </h2>
            {description && (
              <p id={descId} className="text-sm text-fg-muted">
                {description}
              </p>
            )}
          </div>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="-mr-2 -mt-2 flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-full text-fg-muted transition-colors hover:bg-bg-3 hover:text-fg focus-visible:focus-ring"
          >
            <svg aria-hidden viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round">
              <path d="M4 4l8 8M12 4l-8 8" />
            </svg>
          </button>
        </div>
        {children}
        {footer && <div className="flex justify-end gap-2 pt-2">{footer}</div>}
      </div>
    </dialog>
  );
}
