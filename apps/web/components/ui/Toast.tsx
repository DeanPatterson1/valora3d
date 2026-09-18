"use client";

import { create } from "zustand";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { fadeRise, reduced } from "@/lib/motion/variants";
import { cx } from "./cx";

export type ToastKind = "info" | "success" | "danger";
export type Toast = { id: number; kind: ToastKind; message: string };

type ToastState = {
  toasts: Toast[];
  push: (t: { kind: ToastKind; message: string }) => number;
  dismiss: (id: number) => void;
};

const AUTO_DISMISS_MS = 4000;
let nextId = 1;

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  push: ({ kind, message }) => {
    const id = nextId++;
    set({ toasts: [...get().toasts, { id, kind, message }] });
    setTimeout(() => get().dismiss(id), AUTO_DISMISS_MS);
    return id;
  },
  dismiss: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
}));

const KIND: Record<ToastKind, string> = {
  info: "",
  success: "",
  danger: "",
};

const DOT: Record<ToastKind, string> = {
  info: "bg-fg-muted",
  success: "bg-success",
  danger: "bg-danger",
};

/** Mount once in the root layout. */
export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);
  const rm = useReducedMotion();
  const variants = rm ? reduced(fadeRise) : fadeRise;

  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-center gap-2 sm:bottom-6"
    >
      <AnimatePresence initial={false}>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            layout={!rm}
            variants={variants}
            initial="hidden"
            animate="visible"
            exit="exit"
            className={cx(
              "pointer-events-auto flex w-fit max-w-sm items-center gap-3 rounded-full bg-bg-2 py-2 pl-4 pr-2 text-sm text-fg shadow-raise",
              KIND[t.kind],
            )}
          >
            <span aria-hidden className={cx("size-1.5 shrink-0 rounded-full", DOT[t.kind])} />
            <span className="flex-1">{t.message}</span>
            <button
              type="button"
              aria-label="Dismiss"
              onClick={() => dismiss(t.id)}
              className="flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-full text-fg-muted transition-colors hover:bg-bg-3 hover:text-fg focus-visible:focus-ring"
            >
              <svg aria-hidden viewBox="0 0 16 16" className="size-3.5" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round">
                <path d="M4 4l8 8M12 4l-8 8" />
              </svg>
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
