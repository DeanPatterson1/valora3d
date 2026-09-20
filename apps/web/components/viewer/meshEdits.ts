import * as THREE from "three";
import { SPLIT_SEPARATOR, assignNodeIds, findNode, nodeId } from "./meshTree";
import { splitGeometryIslands } from "./splitIslands";

/**
 * The user's geometry edits, stored as normalised sets rather than a log so that
 * undoing is a removal and replaying is order-independent within each phase.
 * Splits run first (a parent must exist before its islands can be addressed),
 * then deletes, then visibility.
 */
export type MeshEdits = {
  /** Mesh ids that were separated into their loose parts. */
  split: string[];
  /** Node ids removed from the scene. Gone from the render too. */
  deleted: string[];
  /** Node ids hidden in the viewport only, exactly like Blender's eye toggle. */
  hidden: string[];
};

export const NO_EDITS: MeshEdits = { split: [], deleted: [], hidden: [] };

export function hasEdits(edits: MeshEdits): boolean {
  return edits.split.length > 0 || edits.deleted.length > 0 || edits.hidden.length > 0;
}

/**
 * Puts the scene back the way it was before one operation.
 * A detached node keeps its geometry alive so undo can re-attach it; `discard`
 * frees that geometry once the step falls out of the undo history.
 */
export type Undoable = { revert: () => void; discard: () => void };

/** Depth of a node id, so parents are always processed before their islands. */
function depth(id: string): number {
  return id.split("/").length + id.split(SPLIT_SEPARATOR).length;
}

function disposeTree(object: THREE.Object3D): void {
  object.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (mesh.isMesh) mesh.geometry.dispose();
  });
}

/** Detaches a child while remembering where it sat, so it can go back in place. */
function detach(node: THREE.Object3D): () => void {
  const parent = node.parent;
  if (!parent) return () => {};
  const index = parent.children.indexOf(node);
  parent.remove(node);
  return () => {
    node.parent = parent;
    parent.children.splice(Math.min(index, parent.children.length), 0, node);
  };
}

export type SplitOutcome =
  | { ok: true; parts: number; undo: Undoable }
  | { ok: false; reason: "not_a_mesh" | "single_island" };

/**
 * Replaces the mesh at `id` with a group of one mesh per connected component.
 * The group inherits the mesh's id so later edits keep resolving; islands become
 * `${id}#0`, `${id}#1`, … in descending size order.
 */
export function splitNode(root: THREE.Object3D, id: string): SplitOutcome {
  const target = findNode(root, id);
  const mesh = target as THREE.Mesh | null;
  if (!mesh || !mesh.isMesh) return { ok: false, reason: "not_a_mesh" };

  const islands = splitGeometryIslands(mesh.geometry);
  if (!islands) return { ok: false, reason: "single_island" };

  const group = new THREE.Group();
  group.name = mesh.name || `Part ${id}`;
  group.position.copy(mesh.position);
  group.rotation.copy(mesh.rotation);
  group.scale.copy(mesh.scale);
  group.userData.rsId = id;

  islands.forEach((geometry, i) => {
    const part = new THREE.Mesh(geometry, mesh.material);
    part.name = `${group.name}.${String(i + 1).padStart(3, "0")}`;
    part.castShadow = mesh.castShadow;
    part.receiveShadow = mesh.receiveShadow;
    part.userData.rsId = `${id}${SPLIT_SEPARATOR}${i}`;
    group.add(part);
  });

  const parent = mesh.parent;
  const index = parent ? parent.children.indexOf(mesh) : -1;
  if (parent) {
    parent.remove(mesh);
    parent.children.splice(index, 0, group);
    group.parent = parent;
  }

  return {
    ok: true,
    parts: islands.length,
    undo: {
      // The source mesh is held (not disposed) until the step leaves the history.
      revert: () => {
        if (!parent) return;
        parent.remove(group);
        mesh.parent = parent;
        parent.children.splice(Math.min(index, parent.children.length), 0, mesh);
      },
      discard: () => mesh.geometry.dispose(),
    },
  };
}

/** Removes a node from its parent. Geometry survives until the undo step is discarded. */
export function deleteNode(root: THREE.Object3D, id: string): Undoable | null {
  const target = findNode(root, id);
  if (!target || target === root || !target.parent) return null;
  const reattach = detach(target);
  return { revert: reattach, discard: () => disposeTree(target) };
}

/** Hides or shows a node in the viewport. Never affects what the renderer receives. */
export function setNodeHidden(root: THREE.Object3D, id: string, hidden: boolean): boolean {
  const target = findNode(root, id);
  if (!target) return false;
  target.visible = !hidden;
  return true;
}

/**
 * Applies the whole edit set to a freshly loaded root, in place.
 * Ids that no longer resolve are skipped: deleting a parent legitimately removes
 * its islands, and the edit set keeps the stale entries harmlessly. Replay has no
 * history behind it, so removed geometry is freed immediately.
 */
export function applyEdits(root: THREE.Object3D, edits: MeshEdits): void {
  assignNodeIds(root);
  for (const id of [...edits.split].sort((a, b) => depth(a) - depth(b))) {
    const outcome = splitNode(root, id);
    if (outcome.ok) outcome.undo.discard();
  }
  for (const id of edits.deleted) deleteNode(root, id)?.discard();

  const hidden = new Set(edits.hidden);
  root.traverse((o) => {
    const id = nodeId(o);
    if (id !== null) o.visible = !hidden.has(id);
  });
}

/** True once every mesh has been removed — the viewer then has nothing to show. */
export function isEmpty(root: THREE.Object3D): boolean {
  let found = false;
  root.traverse((o) => {
    if ((o as THREE.Mesh).isMesh) found = true;
  });
  return !found;
}
