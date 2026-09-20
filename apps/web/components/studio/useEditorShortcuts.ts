"use client";

import { useEffect } from "react";
import { useEditorStore } from "@/lib/stores/editor";

/** Typing in the composer must never delete geometry. */
function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
}

/**
 * Blender's muscle memory for the studio: P separates, H hides, Delete removes,
 * Ctrl/Cmd+Z undoes. Escape is left alone — the drawer owns it.
 */
export function useEditorShortcuts(): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTyping(e.target)) return;
      const store = useEditorStore.getState();
      if (!store.root) return;

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey) {
        if (store.history.length === 0) return;
        e.preventDefault();
        store.undo();
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;

      if (e.key === "Delete" || e.key === "Backspace") {
        if (store.selection.length === 0) return;
        e.preventDefault();
        store.deleteSelected();
        return;
      }
      if (e.key.toLowerCase() === "p") {
        if (store.selection.length === 0) return;
        e.preventDefault();
        store.splitSelected();
        return;
      }
      if (e.key.toLowerCase() === "h") {
        const [first] = store.selection;
        if (!first) return;
        e.preventDefault();
        store.toggleHidden(first);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
