import * as THREE from "three";
import { nodeId } from "./meshTree";

/**
 * Solid shading for the editing viewport.
 *
 * The viewport is a workspace, not the product: it shows untextured clay so
 * geometry reads clearly while parts are picked apart. The file's own materials
 * are kept on `userData.rsMaterial` because the renderer still needs them.
 */

const CLAY = "#8d9096";
const SELECTED = "#ff8a3d";

/** One shared instance each; per-mesh materials would leak on every selection change. */
export const solidMaterial = new THREE.MeshStandardMaterial({
  color: CLAY,
  roughness: 0.68,
  metalness: 0,
  name: "rs.solid",
});

export const selectedMaterial = new THREE.MeshStandardMaterial({
  color: CLAY,
  roughness: 0.68,
  metalness: 0,
  emissive: new THREE.Color(SELECTED),
  emissiveIntensity: 0.55,
  name: "rs.solid.selected",
});

/**
 * The file's own materials, by mesh.
 *
 * Deliberately not `userData`: `Object3D.clone()` round-trips userData through
 * `JSON.stringify`, which would mangle a Material. The snapshot export clones the
 * scene, so the stash has to live outside it.
 */
const originalMaterials = new WeakMap<THREE.Mesh, THREE.Material | THREE.Material[]>();

/**
 * Swaps every mesh to clay, remembering the original once. Safe to call repeatedly:
 * the stash is only written the first time a mesh is seen.
 */
export function applySolidShading(root: THREE.Object3D): void {
  root.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    if (!originalMaterials.has(mesh)) originalMaterials.set(mesh, mesh.material);
    mesh.material = solidMaterial;
  });
}

/** Puts the file's own materials back, for the render path or a textured preview. */
export function restoreMaterials(root: THREE.Object3D): void {
  root.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    const original = originalMaterials.get(mesh);
    if (original) mesh.material = original;
  });
}

/** True when the node, or any ancestor of it, is selected. Selecting a group tints its subtree. */
function inSelection(object: THREE.Object3D, selected: ReadonlySet<string>): boolean {
  for (let node: THREE.Object3D | null = object; node; node = node.parent) {
    const id = nodeId(node);
    if (id !== null && selected.has(id)) return true;
  }
  return false;
}

/** Tints the selected meshes. Everything else returns to plain clay. */
export function applySelection(root: THREE.Object3D, selected: ReadonlySet<string>): void {
  root.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.material = inSelection(mesh, selected) ? selectedMaterial : solidMaterial;
  });
}
