import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import * as THREE from "three";
import { loadModel, normalize, validateFile } from "./loadModel";
import { MAX_UPLOAD_BYTES } from "@/lib/pricing";

const f = (name: string, size = 10) => new File([new Uint8Array(size)], name);

describe("validateFile", () => {
  it("accepts supported formats", () => {
    expect(validateFile(f("a.glb"))).toEqual({ ok: true, value: "glb" });
    expect(validateFile(f("a.GLB"))).toEqual({ ok: true, value: "glb" });
    for (const ext of ["fbx", "obj", "gltf"]) expect(validateFile(f(`a.${ext}`)).ok).toBe(false);
  });
  it("rejects unsupported", () => {
    expect(validateFile(f("a.stl")).ok).toBe(false);
  });
  it("rejects oversize", () => {
    const big = { name: "a.glb", size: MAX_UPLOAD_BYTES + 1 } as File;
    const r = validateFile(big);
    expect(!r.ok && r.error.code).toBe("too_large");
  });
});

describe("loadModel", () => {
  const original = { create: URL.createObjectURL, revoke: URL.revokeObjectURL };
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => "blob:test");
    URL.revokeObjectURL = vi.fn();
  });
  afterEach(() => {
    URL.createObjectURL = original.create;
    URL.revokeObjectURL = original.revoke;
  });

  it("rejects a .gltf that references external files", async () => {
    const gltf = JSON.stringify({ asset: { version: "2.0" }, buffers: [{ uri: "scene.bin", byteLength: 8 }] });
    const r = await loadModel(new Blob([gltf], { type: "model/gltf+json" }), "gltf");
    expect(!r.ok && r.error.code).toBe("external_files");
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:test");
  });
  it("lets an embedded data: uri through the external-file check", async () => {
    const gltf = JSON.stringify({ asset: { version: "2.0" }, buffers: [{ uri: "data:application/octet-stream;base64,AAAA", byteLength: 3 }] });
    const r = await loadModel(new Blob([gltf]), "gltf");
    // The loader itself fails in jsdom (no fetch of blob:), but not with the external-files code.
    expect(r.ok || r.error.code !== "external_files").toBe(true);
  });
});

describe("normalize", () => {
  const worldBox = (o: THREE.Object3D) => {
    o.updateWorldMatrix(true, true);
    return new THREE.Box3().setFromObject(o);
  };

  it("centres the model on the origin and rests it on the ground", () => {
    const root = new THREE.Group();
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(2, 1, 4));
    mesh.position.set(3, 5, -2);
    root.add(mesh);
    normalize(root);
    const box = worldBox(root);
    expect(box.min.y).toBeCloseTo(0);
    expect(box.max.y).toBeCloseTo(1);
    expect((box.min.x + box.max.x) / 2).toBeCloseTo(0);
    expect((box.min.z + box.max.z) / 2).toBeCloseTo(0);
  });
  it("is correct when the root already sits under a scaled group", () => {
    const scaled = new THREE.Group();
    scaled.scale.setScalar(0.5);
    const root = new THREE.Group();
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(2, 1, 4));
    mesh.position.set(3, 5, -2);
    root.add(mesh);
    scaled.add(root);
    normalize(root);
    const box = worldBox(scaled);
    expect(box.min.y).toBeCloseTo(0);
    expect(box.max.y).toBeCloseTo(0.5);
    expect((box.min.x + box.max.x) / 2).toBeCloseTo(0);
    expect((box.min.z + box.max.z) / 2).toBeCloseTo(0);
  });
});
