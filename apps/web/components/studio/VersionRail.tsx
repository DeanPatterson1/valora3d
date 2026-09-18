"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { motion, useReducedMotion } from "motion/react";
import { cx } from "@/components/ui";
import { fadeRise, reduced } from "@/lib/motion/variants";
import type { SceneVersion } from "@/lib/schema";
import { useStudioStore } from "@/lib/stores/studio";

const MANUAL_PREFIX = "manual: ";

const CONTROL_COPY: Record<string, string> = {
  handheld: "Handheld adjusted",
  depthOfField: "Depth of field adjusted",
  motionBlur: "Motion blur adjusted",
  fog: "Fog adjusted",
  light: "Light adjusted",
  output: "Output changed",
};

/** Rail label for a version: the user's own prompt text, or a human phrase for a slider/output change. */
export function versionLabel(prompt: string): { text: string; manual: boolean } {
  if (!prompt.startsWith(MANUAL_PREFIX)) return { text: prompt, manual: false };
  const control = prompt.slice(MANUAL_PREFIX.length).trim();
  return { text: CONTROL_COPY[control] ?? `${control} adjusted`, manual: true };
}

/** "just now", "3 min ago", "2 h ago", "4 d ago". */
export function relativeTime(createdAt: number, now: number): string {
  const s = Math.max(0, Math.round((now - createdAt) / 1000));
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} h ago`;
  return `${Math.floor(h / 24)} d ago`;
}

function useNow(intervalMs: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(t);
  }, [intervalMs]);
  return now;
}

/**
 * Scene history (spec 6.3, 10), listed under the open project in the sidebar. Versions are
 * append-only and in creation order, labelled with the user's own prompt text so a version
 * is recognised, not recalled. `versions` comes from the caller so the list can be frozen
 * during the labour sequence.
 */
export function VersionRail({ versions }: { versions: SceneVersion[] }) {
  const selectedVersionId = useStudioStore((s) => s.selectedVersionId);
  const selectVersion = useStudioStore((s) => s.selectVersion);
  const busy = useStudioStore((s) => s.busy);
  const rm = useReducedMotion() ?? false;
  const now = useNow(30_000);

  // Items present at mount render settled; only versions appended afterwards rise in.
  // `initial` is read once when an <li> mounts, so the set never needs updating.
  const [mounted] = useState(() => new Set(versions.map((v) => v.id)));

  const listRef = useRef<HTMLUListElement>(null);
  useEffect(() => {
    if (!selectedVersionId) return;
    const el = listRef.current?.querySelector<HTMLElement>('[aria-current="true"]');
    el?.scrollIntoView?.({ block: "nearest" });
  }, [selectedVersionId, versions.length]);

  const disabled = busy !== null;
  const item = rm ? reduced(fadeRise) : fadeRise;

  const focusItem = (index: number) => {
    const items = listRef.current?.querySelectorAll<HTMLElement>("[data-version-item]");
    items?.[index]?.focus();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLLIElement>, index: number, id: string) => {
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        focusItem(Math.min(versions.length - 1, index + 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        focusItem(Math.max(0, index - 1));
        break;
      case "Home":
        e.preventDefault();
        focusItem(0);
        break;
      case "End":
        e.preventDefault();
        focusItem(versions.length - 1);
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        if (!disabled) void selectVersion(id);
        break;
    }
  };

  if (versions.length === 0) {
    return (
      <p className="px-2.5 py-1.5 text-xs text-fg-muted">Your scene history appears here.</p>
    );
  }

  // Roving tabindex: the selected item (or the first) is the single tab stop.
  const tabStop = versions.some((v) => v.id === selectedVersionId) ? selectedVersionId : versions[0].id;

  return (
    <ul ref={listRef} role="list" aria-label="Scene versions" aria-busy={disabled || undefined} className="flex flex-col gap-px py-0.5">
      {versions.map((v, index) => {
        const selected = v.id === selectedVersionId;
        const { text, manual } = versionLabel(v.prompt);
        return (
          <motion.li
            key={v.id}
            data-version-item
            role="listitem"
            aria-label={`Version ${index + 1}: ${text}${manual ? " (manual)" : ""}`}
            aria-current={selected ? "true" : undefined}
            data-disabled={disabled || undefined}
            tabIndex={v.id === tabStop ? 0 : -1}
            variants={item}
            initial={mounted.has(v.id) ? false : "hidden"}
            animate="visible"
            onClick={() => { if (!disabled) void selectVersion(v.id); }}
            onKeyDown={(e) => onKeyDown(e, index, v.id)}
            className={cx(
              "flex cursor-pointer select-none items-baseline gap-2 rounded-sm py-1.5 pl-2.5 pr-2 transition-colors duration-fast ease-standard focus-visible:focus-ring",
              selected ? "bg-bg-2 text-fg" : "text-fg-muted hover:bg-bg-2 hover:text-fg",
              disabled && "cursor-default opacity-60",
            )}
          >
            <span className={cx("w-4 shrink-0 tabular text-xs", selected ? "text-fg" : "text-fg-muted")}>{index + 1}</span>
            <span className="min-w-0 flex-1 truncate text-sm" title={v.prompt}>{text}</span>
            {manual && <span className="shrink-0 rounded-sm border border-line px-1 text-[10px] text-fg-muted">manual</span>}
            <span className="shrink-0 text-[11px] text-fg-muted">{relativeTime(v.createdAt, now)}</span>
          </motion.li>
        );
      })}
    </ul>
  );
}
