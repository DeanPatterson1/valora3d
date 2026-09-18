"use client";

import { useId, useRef } from "react";
import { motion, useReducedMotion } from "motion/react";
import { SPRING } from "@/lib/motion/tokens";
import { cx } from "./cx";

export type TabItem = { id: string; label: string };

export type TabsProps = {
  items: TabItem[];
  value: string;
  onChange: (id: string) => void;
  /** Accessible name for the tab list. */
  label?: string;
  /** Shared prefix for tab/panel ids. Pass the same value to `TabPanel`. Defaults to a generated id. */
  id?: string;
  className?: string;
};

export function Tabs({ items, value, onChange, label, id: idProp, className }: TabsProps) {
  const autoId = useId();
  const baseId = idProp ?? autoId;
  const rm = useReducedMotion();
  const listRef = useRef<HTMLDivElement>(null);

  const focusAndSelect = (index: number) => {
    const i = (index + items.length) % items.length;
    const next = items[i];
    if (!next) return;
    onChange(next.id);
    listRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[i]?.focus();
  };

  const onKeyDown = (e: React.KeyboardEvent, index: number) => {
    switch (e.key) {
      case "ArrowRight":
      case "ArrowDown":
        e.preventDefault();
        focusAndSelect(index + 1);
        break;
      case "ArrowLeft":
      case "ArrowUp":
        e.preventDefault();
        focusAndSelect(index - 1);
        break;
      case "Home":
        e.preventDefault();
        focusAndSelect(0);
        break;
      case "End":
        e.preventDefault();
        focusAndSelect(items.length - 1);
        break;
    }
  };

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label={label}
      className={cx("flex items-end gap-1 border-b border-line", className)}
    >
      {items.map((item, i) => {
        const selected = item.id === value;
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`${baseId}-tab-${item.id}`}
            aria-selected={selected}
            aria-controls={`${baseId}-panel-${item.id}`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.id)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={cx(
              "relative -mb-px cursor-pointer rounded-t-sm px-3 pb-2.5 pt-2 text-sm transition-colors duration-fast ease-standard focus-visible:focus-ring",
              selected ? "text-fg" : "text-fg-muted hover:text-fg",
            )}
          >
            {item.label}
            {selected && (
              <motion.span
                aria-hidden
                layoutId={rm ? undefined : `${baseId}-underline`}
                transition={SPRING.snappy}
                className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-accent"
              />
            )}
          </button>
        );
      })}
    </div>
  );
}

export type TabPanelProps = {
  /** The `id` given to the matching `Tabs`. */
  tabsId: string;
  id: string;
  active: boolean;
  children: React.ReactNode;
  className?: string;
};

/** Panel wired to its tab for assistive tech. Renders nothing when inactive. */
export function TabPanel({ tabsId, id, active, children, className }: TabPanelProps) {
  if (!active) return null;
  return (
    <div
      role="tabpanel"
      id={`${tabsId}-panel-${id}`}
      aria-labelledby={`${tabsId}-tab-${id}`}
      tabIndex={0}
      className={className}
    >
      {children}
    </div>
  );
}
