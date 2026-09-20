import * as THREE from "three";
import { GLTFExporter } from "three/addons/exporters/GLTFExporter.js";
import { applySelection, applySolidShading, restoreMaterials } from "@/components/viewer/solidShading";

/**
 * The input contract for the render pipeline: the edited scene as a self-contained GLB.
 *
 * What the renderer receives is what the viewer shows, with two deliberate differences.
 * The clay of the editing viewport is dropped for the file's own materials — clay is a
 * working view, not the product. Hidden parts are still exported: hiding is the
 * viewport's eye toggle, and only Delete takes geometry out of the video.
 */

/** Refuse anything the local server will reject anyway (`jobs.validate_snapshot`). */
export const MAX_SNAPSHOT_BYTES = 90 * 1024 * 1024;

export type Snapshot = {
  /** Base64 GLB, no data-URI prefix. */
  data: string;
  bytes: number;
};

export class SnapshotError extends Error {
  constructor(
    message: string,
    readonly code: "empty" | "too_large" | "export_failed",
  ) {
    super(message);
    this.name = "SnapshotError";
  }
}

function meshCount(root: THREE.Object3D): number {
  let count = 0;
  root.traverse((o) => {
    if ((o as THREE.Mesh).isMesh) count++;
  });
  return count;
}

/**
 * Builds the GLB.
 *
 * `scaleFactor` is the analysis unit conversion the viewer applies on a wrapper group,
 * so the model itself is never rescaled. The export bakes it in, which is what makes
 * the Blender side able to measure the subject in metres and frame it like the viewer.
 */
export async function exportSnapshot(
  root: THREE.Object3D,
  scaleFactor: number,
  selection: readonly string[] = [],
): Promise<Snapshot> {
  if (meshCount(root) === 0) {
    throw new SnapshotError("There is no geometry left to render.", "empty");
  }

  // Clone with the file's own materials on, then put the viewport back to clay. Both
  // swaps are synchronous, so no frame is ever drawn in between.
  restoreMaterials(root);
  let copy: THREE.Object3D;
  try {
    copy = root.clone(true);
  } finally {
    applySolidShading(root);
    applySelection(root, new Set(selection));
  }

  const wrapper = new THREE.Group();
  wrapper.name = "RenderStudioSnapshot";
  wrapper.scale.setScalar(scaleFactor);
  wrapper.add(copy);
  wrapper.updateMatrixWorld(true);

  let binary: ArrayBuffer;
  try {
    const result = await new GLTFExporter().parseAsync(wrapper, {
      binary: true,
      // Hidden parts still render: the eye toggle is a viewport control.
      onlyVisible: false,
      maxTextureSize: 2048,
    });
    binary = result as ArrayBuffer;
  } catch {
    throw new SnapshotError("The model could not be exported for rendering.", "export_failed");
  }

  if (binary.byteLength > MAX_SNAPSHOT_BYTES) {
    const mb = Math.round(binary.byteLength / (1024 * 1024));
    throw new SnapshotError(`This model is ${mb} MB once prepared, over the 90 MB render limit.`, "too_large");
  }
  return { data: toBase64(binary), bytes: binary.byteLength };
}

/** Chunked so a large GLB cannot blow the argument limit of `String.fromCharCode`. */
function toBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  const CHUNK = 0x8000;
  let binary = "";
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary);
}
