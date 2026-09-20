import * as THREE from "three";

/**
 * Splits a geometry into its connected components ("loose parts" in Blender).
 *
 * GLB exporters duplicate vertices wherever normals or UVs break, so raw index
 * adjacency reports far more islands than the surface actually has. Vertices are
 * therefore welded by quantised position first; the split itself runs on that
 * welded topology while the emitted geometries keep every original attribute.
 */

/** Positions are snapped to this many units before welding. 0.1 mm at metre scale. */
const WELD_EPSILON = 1e-4;
/** Refuse to split past this many parts; beyond it the outliner stops being useful. */
export const MAX_ISLANDS = 512;

class UnionFind {
  private readonly parent: Int32Array;
  constructor(size: number) {
    this.parent = new Int32Array(size);
    for (let i = 0; i < size; i++) this.parent[i] = i;
  }
  find(a: number): number {
    let root = a;
    while (this.parent[root] !== root) root = this.parent[root];
    // Path compression, iterative so deep chains cannot blow the stack.
    let node = a;
    while (this.parent[node] !== root) {
      const next = this.parent[node];
      this.parent[node] = root;
      node = next;
    }
    return root;
  }
  union(a: number, b: number): void {
    const ra = this.find(a);
    const rb = this.find(b);
    if (ra !== rb) this.parent[rb] = ra;
  }
}

/** Maps every vertex to a representative index shared by all vertices at the same position. */
function weldByPosition(position: THREE.BufferAttribute | THREE.InterleavedBufferAttribute): Int32Array {
  const count = position.count;
  const representative = new Int32Array(count);
  const seen = new Map<string, number>();
  const inverseEpsilon = 1 / WELD_EPSILON;
  for (let i = 0; i < count; i++) {
    const x = Math.round(position.getX(i) * inverseEpsilon);
    const y = Math.round(position.getY(i) * inverseEpsilon);
    const z = Math.round(position.getZ(i) * inverseEpsilon);
    const key = `${x},${y},${z}`;
    const existing = seen.get(key);
    if (existing === undefined) {
      seen.set(key, i);
      representative[i] = i;
    } else {
      representative[i] = existing;
    }
  }
  return representative;
}

/** Triangle indices of the geometry, synthesised when it is non-indexed. */
function triangleIndices(geometry: THREE.BufferGeometry): ArrayLike<number> {
  const index = geometry.getIndex();
  if (index) return index.array;
  const count = geometry.getAttribute("position").count;
  const synthetic = new Uint32Array(count);
  for (let i = 0; i < count; i++) synthetic[i] = i;
  return synthetic;
}

/**
 * Returns one geometry per connected component, or `null` when the geometry is a
 * single island (nothing to split) or has no triangles to walk.
 */
export function splitGeometryIslands(geometry: THREE.BufferGeometry): THREE.BufferGeometry[] | null {
  const position = geometry.getAttribute("position");
  if (!position) return null;
  const indices = triangleIndices(geometry);
  const triangleCount = Math.floor(indices.length / 3);
  if (triangleCount === 0) return null;

  const welded = weldByPosition(position);
  const sets = new UnionFind(position.count);
  for (let t = 0; t < triangleCount; t++) {
    const a = welded[indices[t * 3]];
    const b = welded[indices[t * 3 + 1]];
    const c = welded[indices[t * 3 + 2]];
    sets.union(a, b);
    sets.union(a, c);
  }

  // Bucket triangles by the component their first corner lands in.
  const buckets = new Map<number, number[]>();
  for (let t = 0; t < triangleCount; t++) {
    const root = sets.find(welded[indices[t * 3]]);
    const bucket = buckets.get(root);
    if (bucket) bucket.push(t);
    else buckets.set(root, [t]);
  }
  if (buckets.size <= 1 || buckets.size > MAX_ISLANDS) return null;

  // Largest island first, so the outliner leads with the meaningful parts.
  const groups = [...buckets.values()].sort((a, b) => b.length - a.length);
  return groups.map((triangles) => extractTriangles(geometry, indices, triangles));
}

/** Builds a standalone geometry from a subset of the source triangles. */
function extractTriangles(source: THREE.BufferGeometry, indices: ArrayLike<number>, triangles: number[]): THREE.BufferGeometry {
  const out = new THREE.BufferGeometry();
  // Original vertex index -> index in the new attribute arrays.
  const remap = new Map<number, number>();
  const order: number[] = [];
  const newIndex = new Uint32Array(triangles.length * 3);
  let cursor = 0;
  for (let i = 0; i < triangles.length; i++) {
    const t = triangles[i];
    for (let corner = 0; corner < 3; corner++) {
      const vertex = indices[t * 3 + corner];
      let mapped = remap.get(vertex);
      if (mapped === undefined) {
        mapped = cursor++;
        remap.set(vertex, mapped);
        order.push(vertex);
      }
      newIndex[i * 3 + corner] = mapped;
    }
  }

  for (const name of Object.keys(source.attributes)) {
    out.setAttribute(name, sliceAttribute(source.attributes[name], order));
  }
  out.setIndex(new THREE.BufferAttribute(newIndex, 1));
  out.computeBoundingBox();
  out.computeBoundingSphere();
  return out;
}

function sliceAttribute(
  attribute: THREE.BufferAttribute | THREE.InterleavedBufferAttribute,
  order: number[],
): THREE.BufferAttribute {
  const itemSize = attribute.itemSize;
  const values = new Float32Array(order.length * itemSize);
  for (let i = 0; i < order.length; i++) {
    const from = order[i];
    for (let c = 0; c < itemSize; c++) {
      values[i * itemSize + c] = attribute.getComponent(from, c);
    }
  }
  return new THREE.BufferAttribute(values, itemSize, attribute.normalized);
}
