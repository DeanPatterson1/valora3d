import type * as THREE from "three";

/**
 * How the render service reaches the live, edited scene.
 *
 * The `RenderService` seam is given only a project and a version id, but the geometry
 * to render lives in memory in the viewer — already normalised, already edited. Rather
 * than widen the interface or let a service import a store (the stores import
 * services, so that would be a cycle), the editor registers a reader here.
 */

export type Scene = {
  root: THREE.Object3D;
  /** Analysis unit conversion; the export bakes it in so the GLB is in metres. */
  scaleFactor: number;
  /** Repainted after the export swaps materials, so the highlight survives. */
  selection: readonly string[];
};

export type SceneSource = () => Scene | null;

let source: SceneSource | null = null;

export function setSceneSource(next: SceneSource | null): void {
  source = next;
}

export function currentScene(): Scene | null {
  return source?.() ?? null;
}
