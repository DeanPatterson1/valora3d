import * as THREE from "three";

/**
 * Stable identity for the nodes of a loaded model.
 *
 * `Object3D.uuid` is regenerated on every load, so edits keyed by uuid would not
 * survive a reload. Ids are instead the node's child-index path from the root
 * ("0/2/5"), which a given file always reproduces. Islands split out of a mesh
 * extend their parent's id with `#n`, so an edit made after a split replays in
 * order against the same node.
 */

export const SPLIT_SEPARATOR = "#";

export type NodeKind = "group" | "mesh";

export type OutlineNode = {
  id: string;
  name: string;
  kind: NodeKind;
  /** Triangles in this node alone; groups report the sum of their descendants. */
  triangles: number;
  children: OutlineNode[];
};

type Tagged = THREE.Object3D & { userData: { rsId?: string } };

/** Writes a stable id onto every node below (and including) `root`. Idempotent. */
export function assignNodeIds(root: THREE.Object3D, prefix = ""): void {
  (root as Tagged).userData.rsId = prefix === "" ? "root" : prefix;
  root.children.forEach((child, i) => {
    assignNodeIds(child, prefix === "" ? String(i) : `${prefix}/${i}`);
  });
}

export function nodeId(object: THREE.Object3D): string | null {
  return (object as Tagged).userData.rsId ?? null;
}

export function findNode(root: THREE.Object3D, id: string): THREE.Object3D | null {
  if (nodeId(root) === id) return root;
  let found: THREE.Object3D | null = null;
  root.traverse((o) => {
    if (found) return;
    if (nodeId(o) === id) found = o;
  });
  return found;
}

export function triangleCount(mesh: THREE.Mesh): number {
  const geometry = mesh.geometry;
  const index = geometry.getIndex();
  const count = index ? index.count : (geometry.getAttribute("position")?.count ?? 0);
  return Math.floor(count / 3);
}

/** A readable label for a node the file left unnamed. */
export function displayName(object: THREE.Object3D, id: string): string {
  if (object.name) return object.name;
  const tail = id.split("/").pop() ?? id;
  return (object as THREE.Mesh).isMesh ? `Mesh ${tail}` : `Group ${tail}`;
}

/**
 * Builds the outliner tree. Nodes carrying no mesh anywhere below them are
 * dropped: a GLB's empty transform nodes are noise in a parts list.
 */
export function buildOutline(root: THREE.Object3D): OutlineNode[] {
  const node = outlineOf(root);
  // The root itself is a wrapper; surface its children as the top level.
  return node ? node.children : [];
}

function outlineOf(object: THREE.Object3D): OutlineNode | null {
  const id = nodeId(object);
  if (id === null) return null;
  const children = object.children.map(outlineOf).filter((c): c is OutlineNode => c !== null);
  const mesh = object as THREE.Mesh;
  const own = mesh.isMesh ? triangleCount(mesh) : 0;
  if (!mesh.isMesh && children.length === 0) return null;
  return {
    id,
    name: displayName(object, id),
    kind: mesh.isMesh ? "mesh" : "group",
    triangles: own + children.reduce((sum, c) => sum + c.triangles, 0),
    children,
  };
}

/** Every mesh id at or below `id`, so selecting a group acts on its whole subtree. */
export function meshIdsUnder(root: THREE.Object3D, id: string): string[] {
  const node = findNode(root, id);
  if (!node) return [];
  const ids: string[] = [];
  node.traverse((o) => {
    if ((o as THREE.Mesh).isMesh) {
      const childId = nodeId(o);
      if (childId) ids.push(childId);
    }
  });
  return ids;
}
