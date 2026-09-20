"use client";

import { create } from "zustand";
import type * as THREE from "three";
import { z } from "zod";
import {
  NO_EDITS,
  type MeshEdits,
  type Undoable,
  applyEdits,
  deleteNode,
  hasEdits,
  setNodeHidden,
  splitNode,
} from "@/components/viewer/meshEdits";
import { type OutlineNode, assignNodeIds, buildOutline, meshIdsUnder } from "@/components/viewer/meshTree";
import { applySelection, applySolidShading } from "@/components/viewer/solidShading";
import { KEYS, readJson, writeJson } from "@/lib/services/local/storage";

/** Steps kept for undo. Beyond this the oldest step's geometry is freed. */
const HISTORY_LIMIT = 50;

const MeshEditsSchema = z.object({
  split: z.array(z.string()),
  deleted: z.array(z.string()),
  hidden: z.array(z.string()),
});
const StoredEditsSchema = z.record(z.string(), MeshEditsSchema);

function readAll(): Record<string, MeshEdits> {
  if (typeof localStorage === "undefined") return {};
  return readJson(KEYS.edits, StoredEditsSchema, {}).value;
}

/** Edits for one project, or the empty set. */
export function readEdits(projectId: string): MeshEdits {
  return readAll()[projectId] ?? NO_EDITS;
}

function persist(projectId: string, edits: MeshEdits): void {
  const all = readAll();
  if (hasEdits(edits)) all[projectId] = edits;
  else delete all[projectId];
  writeJson(KEYS.edits, all);
}

type Step = { edits: MeshEdits; undo: Undoable[] };

type EditorState = {
  projectId: string | null;
  /** The live scene root. Mutated in place; not serialisable. */
  root: THREE.Object3D | null;
  edits: MeshEdits;
  selection: string[];
  outline: OutlineNode[];
  history: Step[];
  /** Bumped on every structural change, so the viewer re-measures bounds. */
  revision: number;
  /** One-line feedback for an action that could not do anything. */
  notice: string | null;

  attach: (projectId: string, root: THREE.Object3D) => void;
  detach: () => void;
  select: (id: string | null, additive?: boolean) => void;
  deleteSelected: () => void;
  splitSelected: () => void;
  toggleHidden: (id: string) => void;
  undo: () => void;
  resetEdits: () => void;
  clearNotice: () => void;
};

export const useEditorStore = create<EditorState>((set, get) => {
  /** Re-reads the tree and repaints selection after the graph changed. */
  const refresh = (root: THREE.Object3D, selection: string[]) => {
    applySelection(root, new Set(selection));
    return { outline: buildOutline(root), revision: get().revision + 1 };
  };

  /** Records one step, capping the history and freeing what falls off it. */
  const push = (step: Step, next: MeshEdits) => {
    const history = [...get().history, step];
    while (history.length > HISTORY_LIMIT) {
      const dropped = history.shift();
      dropped?.undo.forEach((u) => u.discard());
    }
    const projectId = get().projectId;
    if (projectId) persist(projectId, next);
    return { history, edits: next };
  };

  return {
    projectId: null,
    root: null,
    edits: NO_EDITS,
    selection: [],
    outline: [],
    history: [],
    revision: 0,
    notice: null,

    attach: (projectId, root) => {
      const edits = readEdits(projectId);
      assignNodeIds(root);
      applyEdits(root, edits);
      applySolidShading(root);
      applySelection(root, new Set());
      set({
        projectId,
        root,
        edits,
        selection: [],
        history: [],
        outline: buildOutline(root),
        revision: get().revision + 1,
        notice: null,
      });
    },

    detach: () => {
      get().history.forEach((step) => step.undo.forEach((u) => u.discard()));
      set({ projectId: null, root: null, edits: NO_EDITS, selection: [], outline: [], history: [], notice: null });
    },

    select: (id, additive = false) => {
      const { root, selection } = get();
      if (!root) return;
      if (id === null) {
        applySelection(root, new Set());
        set({ selection: [], notice: null });
        return;
      }
      const next = additive
        ? selection.includes(id)
          ? selection.filter((s) => s !== id)
          : [...selection, id]
        : [id];
      applySelection(root, new Set(next));
      set({ selection: next, notice: null });
    },

    deleteSelected: () => {
      const { root, selection, edits } = get();
      if (!root || selection.length === 0) return;
      const undo: Undoable[] = [];
      const removed: string[] = [];
      for (const id of selection) {
        const step = deleteNode(root, id);
        if (step) {
          undo.push(step);
          removed.push(id);
        }
      }
      if (removed.length === 0) return;
      const next = { ...edits, deleted: [...edits.deleted, ...removed] };
      set({
        ...push({ edits, undo }, next),
        selection: [],
        notice: null,
        ...refresh(root, []),
      });
    },

    splitSelected: () => {
      const { root, selection, edits } = get();
      if (!root || selection.length === 0) return;
      const undo: Undoable[] = [];
      const done: string[] = [];
      let parts = 0;
      for (const id of selection) {
        // A group selection splits every mesh beneath it, like Blender's P on a selection.
        for (const meshId of meshIdsUnder(root, id)) {
          const outcome = splitNode(root, meshId);
          if (outcome.ok) {
            undo.push(outcome.undo);
            done.push(meshId);
            parts += outcome.parts;
          }
        }
      }
      if (done.length === 0) {
        set({ notice: "Nothing to separate — that selection is already one connected piece." });
        return;
      }
      const next = { ...edits, split: [...edits.split, ...done] };
      set({
        ...push({ edits, undo }, next),
        selection: [],
        notice: `Separated into ${parts} parts.`,
        ...refresh(root, []),
      });
    },

    toggleHidden: (id) => {
      const { root, edits, selection } = get();
      if (!root) return;
      const hidden = edits.hidden.includes(id);
      if (!setNodeHidden(root, id, !hidden)) return;
      const next = {
        ...edits,
        hidden: hidden ? edits.hidden.filter((h) => h !== id) : [...edits.hidden, id],
      };
      const undo: Undoable[] = [{ revert: () => setNodeHidden(root, id, hidden), discard: () => {} }];
      set({ ...push({ edits, undo }, next), notice: null, ...refresh(root, selection) });
    },

    undo: () => {
      const { root, history } = get();
      if (!root || history.length === 0) return;
      const step = history[history.length - 1];
      // Reverse order: the last change made is the first undone.
      for (let i = step.undo.length - 1; i >= 0; i--) step.undo[i].revert();
      const projectId = get().projectId;
      if (projectId) persist(projectId, step.edits);
      set({
        history: history.slice(0, -1),
        edits: step.edits,
        selection: [],
        notice: null,
        ...refresh(root, []),
      });
    },

    resetEdits: () => {
      const { projectId } = get();
      if (projectId) persist(projectId, NO_EDITS);
      // The graph is rebuilt from a clean load; the viewer remounts on `revision`.
      set({ edits: NO_EDITS, selection: [], history: [], notice: null, revision: get().revision + 1 });
    },

    clearNotice: () => set({ notice: null }),
  };
});
