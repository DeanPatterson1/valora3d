import { describe, it, expect } from "vitest";
import * as THREE from "three";
import { computeSceneStats } from "./sceneStats";

describe("computeSceneStats", () => {
  it("counts triangles, meshes, materials and names; measures extents", () => {
    const root = new THREE.Group();
    const m1 = new THREE.Mesh(new THREE.BoxGeometry(2, 1, 4), new THREE.MeshStandardMaterial({ name: "Paint" }));
    m1.name = "Body";
    const m2 = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.5, 0.5), m1.material);
    m2.name = "Wheel_FL";
    m2.position.set(1, 0, 2);
    root.add(m1, m2);
    const s = computeSceneStats(root);
    expect(s.meshCount).toBe(2);
    expect(s.triangleCount).toBe(24);
    expect(s.materialCount).toBe(1);
    expect(s.objectNames).toEqual(["Body", "Wheel_FL"]);
    expect(s.materialNames).toEqual(["Paint"]);
    expect(s.extents[0]).toBeCloseTo(2.25);
    expect(s.hasSkeleton).toBe(false);
  });
  it("throws on empty or degenerate geometry", () => {
    expect(() => computeSceneStats(new THREE.Group())).toThrow(/no usable geometry/);
  });
});
