"use client";

import { useEffect, useId, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { cx } from "@/components/ui";
import { DUR, EASE } from "@/lib/motion/tokens";
import { PRESETS, type Preset } from "./presets";
import { ACCEPT, SAMPLES, useModelIngest } from "./useModelIngest";

type Props = {
  disabled?: boolean;
  /** Without a model the menu is one item, "Add a model", which opens the file picker. */
  hasModel: boolean;
  /** Shown once a scene exists: presets move here from the empty-state suggestions. */
  showPresets: boolean;
  onPreset: (preset: Preset) => void;
};

function UploadIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 11V3m0 0L5 6m3-3 3 3" />
      <path d="M3 10.5V12a1.5 1.5 0 0 0 1.5 1.5h7A1.5 1.5 0 0 0 13 12v-1.5" />
    </svg>
  );
}
function CubeIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round">
      <path d="M8 2 13.5 5v6L8 14l-5.5-3V5L8 2Z" />
      <path d="M8 8l5.5-3M8 8 2.5 5M8 8v6" />
    </svg>
  );
}
function SparkIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round">
      <path d="M8 2.5c.4 2.9 2.1 4.6 5 5-2.9.4-4.6 2.1-5 5-.4-2.9-2.1-4.6-5-5 2.9-.4 4.6-2.1 5-5Z" />
    </svg>
  );
}
/**
 * The composer's `+` menu: load a model, pick a sample, choose a preset. "Start over"
 * is an inline button in the composer's second row, not a menu item.
 * Items are plain buttons (not menuitems) so they read as actions anywhere.
 */
export function ComposerMenu({ disabled, hasModel, showPresets, onPreset }: Props) {
  const rm = useReducedMotion() ?? false;
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelId = useId();
  const { onFile, onSample } = useModelIngest();

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setOpen(false); buttonRef.current?.focus(); }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        const items = Array.from(rootRef.current?.querySelectorAll<HTMLButtonElement>("[data-menu-item]:not(:disabled)") ?? []);
        if (items.length === 0) return;
        e.preventDefault();
        const i = items.indexOf(document.activeElement as HTMLButtonElement);
        const next = e.key === "ArrowDown" ? (i + 1) % items.length : (i - 1 + items.length) % items.length;
        items[next].focus();
      }
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const pick = (fn: () => void) => () => { setOpen(false); fn(); };
  const onUpload = () => { setOpen(false); inputRef.current?.click(); };

  return (
    <div ref={rootRef} className="contents">
      <button
        ref={buttonRef}
        type="button"
        aria-label="Model options"
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={panelId}
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className={cx(
          "flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-full text-fg transition-colors duration-fast ease-standard hover:bg-bg-3 focus-visible:focus-ring disabled:cursor-not-allowed disabled:opacity-40 sm:size-9",
          open && "bg-bg-3",
        )}
      >
        <svg aria-hidden viewBox="0 0 20 20" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round">
          <path d="M10 4v12M4 10h12" />
        </svg>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="sr-only"
        aria-label="Choose a model file"
        tabIndex={-1}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) onFile(file);
        }}
      />

      <AnimatePresence>
        {open && (
          <motion.div
            key="menu"
            id={panelId}
            role="group"
            aria-label="Model options"
            initial={{ opacity: 0, y: rm ? 0 : 6, scale: rm ? 1 : 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: rm ? 0 : 6, scale: rm ? 1 : 0.98, transition: { duration: rm ? 0 : DUR.fast } }}
            transition={{ duration: rm ? 0 : DUR.base, ease: EASE.emphasized }}
            className="absolute bottom-full left-0 z-30 mb-2 flex w-64 flex-col rounded-2xl bg-bg-2 p-1.5 shadow-raise"
          >
            {!hasModel ? (
              // Straight to the file picker; the upload card on the viewer keeps the samples.
              <Item icon={<UploadIcon />} onClick={onUpload}>Add a model</Item>
            ) : (
              <>
                <Item icon={<UploadIcon />} onClick={onUpload}>Upload model…</Item>
                {SAMPLES.map((s) => (
                  <Item key={s.id} icon={<CubeIcon />} ariaLabel={s.name} onClick={pick(() => void onSample(s))}>{s.name}</Item>
                ))}
              </>
            )}
            {showPresets && (
              <>
                <Divider />
                {PRESETS.map((p) => (
                  <Item key={p.id} icon={<SparkIcon />} onClick={pick(() => onPreset(p))}>{p.label}</Item>
                ))}
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Divider() {
  return <div role="separator" className="my-1 h-px bg-line" />;
}

type ItemProps = {
  icon: React.ReactNode;
  onClick: () => void;
  ariaLabel?: string;
  children: React.ReactNode;
};

function Item({ icon, onClick, ariaLabel, children }: ItemProps) {
  return (
    <button
      type="button"
      data-menu-item
      onClick={onClick}
      aria-label={ariaLabel}
      className="flex h-9 w-full cursor-pointer items-center gap-2.5 rounded-lg px-2.5 text-left text-sm text-fg transition-colors duration-fast ease-standard hover:bg-bg-3 focus-visible:focus-ring"
    >
      <span className="text-fg-muted">{icon}</span>
      {children}
    </button>
  );
}
