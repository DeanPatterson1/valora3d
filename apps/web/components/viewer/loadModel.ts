import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { FBXLoader } from "three/addons/loaders/FBXLoader.js";
import { OBJLoader } from "three/addons/loaders/OBJLoader.js";
import { MAX_UPLOAD_BYTES } from "@/lib/pricing";
import { fail, ok, type Result } from "@/lib/services/result";
import type { Asset } from "@/lib/schema";

export type Format = Asset["format"];

export function validateFile(file: File): Result<Format> {
  const ext = file.name.split(".").pop()?.toLowerCase();
  if (ext !== "glb")
    return fail("unsupported_format", "Unsupported file type. Upload a single .glb file.");
  if (file.size > MAX_UPLOAD_BYTES)
    return fail("too_large", `File is over ${Math.round(MAX_UPLOAD_BYTES / 1024 / 1024)} MB.`);
  return ok(ext);
}

export type Loaded = { root: THREE.Object3D; notices: string[] };

export async function loadModel(source: Blob | string, format: Format): Promise<Result<Loaded>> {
  const url = typeof source === "string" ? source : URL.createObjectURL(source);
  const notices: string[] = [];
  try {
    if (format === "glb" || format === "gltf") {
      if (format === "gltf" && typeof source !== "string") {
        const text = await source.text();
        if (/"uri"\s*:\s*"(?!data:)/.test(text))
          return fail("external_files", "This .gltf references external files. Export as a single .glb instead.");
      }
      const gltf = await new GLTFLoader().loadAsync(url);
      (gltf.scene as unknown as { animations: unknown[] }).animations = gltf.animations;
      return ok({ root: gltf.scene, notices });
    }
    if (format === "fbx") return ok({ root: await new FBXLoader().loadAsync(url), notices });
    const obj = await new OBJLoader().loadAsync(url);
    obj.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) m.material = new THREE.MeshStandardMaterial({ color: 0x9a9a9a, roughness: 0.6 });
    });
    notices.push("OBJ loaded without materials; a neutral material was applied.");
    return ok({ root: obj, notices });
  } catch {
    return fail("parse_failed", "Couldn't read this model. Try re-exporting it as GLB.");
  } finally {
    if (typeof source !== "string") URL.revokeObjectURL(url);
  }
}

/**
 * Centre on origin, rest on ground (y = 0), scale by analysis factor later.
 * Works in the parent's space, so it is correct whether or not `root` already sits under
 * a scaled group.
 */
export function normalize(root: THREE.Object3D): void {
  root.parent?.updateWorldMatrix(true, false);
  root.updateWorldMatrix(false, true);
  const box = new THREE.Box3().setFromObject(root);
  if (root.parent) box.applyMatrix4(root.parent.matrixWorld.clone().invert());
  const c = box.getCenter(new THREE.Vector3());
  root.position.sub(c);
  root.position.y += c.y - box.min.y;
}
