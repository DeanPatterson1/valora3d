import * as THREE from "three";
import type { SceneStats } from "@/lib/schema";

export function computeSceneStats(root: THREE.Object3D): SceneStats {
  let triangleCount = 0;
  let meshCount = 0;
  let hasSkeleton = false;
  const materials = new Set<THREE.Material>();
  const objectNames: string[] = [];
  root.updateMatrixWorld(true);
  root.traverse((o) => {
    if ((o as THREE.SkinnedMesh).isSkinnedMesh) hasSkeleton = true;
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    meshCount++;
    if (mesh.name) objectNames.push(mesh.name);
    const g = mesh.geometry;
    const count = g.index ? g.index.count : (g.attributes.position?.count ?? 0);
    triangleCount += Math.floor(count / 3);
    for (const m of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) materials.add(m);
  });
  if (meshCount === 0) throw new Error("no usable geometry");
  const box = new THREE.Box3().setFromObject(root);
  const size = box.getSize(new THREE.Vector3());
  const extents: [number, number, number] = [size.x, size.y, size.z];
  if (extents.some((e) => !Number.isFinite(e) || e <= 0)) throw new Error("no usable geometry");
  return {
    triangleCount,
    meshCount,
    materialCount: materials.size,
    objectNames,
    materialNames: [...materials].map((m) => m.name).filter(Boolean),
    extents,
    hasSkeleton,
    animationClipCount: (root as unknown as { animations?: unknown[] }).animations?.length ?? 0,
  };
}
