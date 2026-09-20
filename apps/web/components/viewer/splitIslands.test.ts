import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { splitGeometryIslands } from "./splitIslands";

/** Two disjoint boxes in one geometry: the canonical "loose parts" case. */
function twoBoxes(): THREE.BufferGeometry {
  const a = new THREE.BoxGeometry(1, 1, 1).translate(-5, 0, 0);
  const b = new THREE.BoxGeometry(1, 1, 1).translate(5, 0, 0);
  return mergeGeometries([a, b]);
}

function mergeGeometries(parts: THREE.BufferGeometry[]): THREE.BufferGeometry {
  const positions: number[] = [];
  const normals: number[] = [];
  for (const part of parts) {
    const nonIndexed = part.index ? part.toNonIndexed() : part;
    const position = nonIndexed.getAttribute("position");
    const normal = nonIndexed.getAttribute("normal");
    for (let i = 0; i < position.count; i++) {
      positions.push(position.getX(i), position.getY(i), position.getZ(i));
      normals.push(normal.getX(i), normal.getY(i), normal.getZ(i));
    }
  }
  const merged = new THREE.BufferGeometry();
  merged.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  merged.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  return merged;
}

describe("splitGeometryIslands", () => {
  it("separates two disjoint boxes", () => {
    const islands = splitGeometryIslands(twoBoxes());
    expect(islands).not.toBeNull();
    expect(islands).toHaveLength(2);
  });

  it("keeps every triangle", () => {
    const source = twoBoxes();
    const islands = splitGeometryIslands(source)!;
    const total = islands.reduce((sum, g) => sum + g.getIndex()!.count / 3, 0);
    expect(total).toBe(source.getAttribute("position").count / 3);
  });

  it("carries every attribute onto each island", () => {
    const islands = splitGeometryIslands(twoBoxes())!;
    for (const island of islands) {
      expect(island.getAttribute("position")).toBeDefined();
      expect(island.getAttribute("normal")).toBeDefined();
    }
  });

  it("welds duplicated vertices so one box stays one island", () => {
    // A box exported non-indexed has every corner duplicated per face; without
    // welding this would report twelve islands instead of one.
    const box = new THREE.BoxGeometry(1, 1, 1).toNonIndexed();
    expect(splitGeometryIslands(box)).toBeNull();
  });

  it("returns null when there is nothing to separate", () => {
    expect(splitGeometryIslands(new THREE.BoxGeometry(1, 1, 1))).toBeNull();
  });

  it("returns null for a geometry with no triangles", () => {
    const empty = new THREE.BufferGeometry();
    empty.setAttribute("position", new THREE.Float32BufferAttribute([], 3));
    expect(splitGeometryIslands(empty)).toBeNull();
  });

  it("orders islands largest first", () => {
    const small = new THREE.TetrahedronGeometry(0.4).translate(-8, 0, 0);
    const large = new THREE.BoxGeometry(1, 1, 1).translate(8, 0, 0);
    const islands = splitGeometryIslands(mergeGeometries([small, large]))!;
    const counts = islands.map((g) => g.getIndex()!.count);
    expect(counts[0]).toBeGreaterThanOrEqual(counts[1]);
  });
});
