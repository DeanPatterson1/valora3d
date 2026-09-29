import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { MAX_UPLOAD_BYTES } from "@/lib/pricing";
import { glbVerdict, HEAVY_TRIANGLES, imageSize, inspectGlb, inspectGltfText, type SceneFacts } from "./glbCheck";

function pad4(bytes: Uint8Array, fill: number): Uint8Array {
  const out = new Uint8Array(Math.ceil(bytes.length / 4) * 4).fill(fill);
  out.set(bytes);
  return out;
}

/** A minimal .glb: one JSON chunk and one BIN chunk. */
function makeGlb(json: object, bin: Uint8Array = new Uint8Array(0)): ArrayBuffer {
  const j = pad4(new TextEncoder().encode(JSON.stringify(json)), 0x20);
  const b = pad4(bin, 0);
  const total = 12 + 8 + j.length + (b.length ? 8 + b.length : 0);
  const out = new Uint8Array(total);
  const v = new DataView(out.buffer);
  out.set([0x67, 0x6c, 0x54, 0x46]); // "glTF"
  v.setUint32(4, 2, true);
  v.setUint32(8, total, true);
  v.setUint32(12, j.length, true);
  v.setUint32(16, 0x4e4f534a, true);
  out.set(j, 20);
  if (b.length) {
    v.setUint32(20 + j.length, b.length, true);
    v.setUint32(24 + j.length, 0x004e4942, true);
    out.set(b, 28 + j.length);
  }
  return out.buffer;
}

function pngHeader(width: number, height: number): Uint8Array {
  const out = new Uint8Array(24);
  out.set([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 13, 0x49, 0x48, 0x44, 0x52]);
  const v = new DataView(out.buffer);
  v.setUint32(16, width);
  v.setUint32(20, height);
  return out;
}

const withImage = (width: number, height: number, extra: object = {}) => {
  const png = pngHeader(width, height);
  return makeGlb({
    asset: { version: "2.0" },
    buffers: [{ byteLength: png.length }],
    bufferViews: [{ buffer: 0, byteLength: png.length }],
    images: [{ name: "Albedo", mimeType: "image/png", bufferView: 0 }],
    meshes: [{}],
    ...extra,
  }, png);
};

const scene = (over: Partial<SceneFacts> = {}): SceneFacts => ({
  triangleCount: 120_000, meshCount: 4, materialCount: 2, extents: [0.3, 0.2, 0.25], unitGuess: "m",
  dimensionsMeters: [0.3, 0.2, 0.25], category: "product", rigged: false, animationClipCount: 0, ...over,
});

const levels = (v: ReturnType<typeof glbVerdict>) => Object.fromEntries(v.checks.map((c) => [c.id, c.level]));

describe("reading a file", () => {
  it("reads embedded textures and their size from a .glb", () => {
    const r = inspectGlb(withImage(8192, 4096));
    expect(r.error).toBeNull();
    expect(r.textures).toEqual([{ name: "Albedo", mimeType: "image/png", embedded: true, bytes: 24, width: 8192, height: 4096 }]);
    expect(r.externalFiles).toEqual([]);
  });

  it("reads the shipped sample car (WebP textures) without errors", () => {
    const file = readFileSync(path.join(process.cwd(), "public/samples/toycar.glb"));
    const r = inspectGlb(file.buffer.slice(file.byteOffset, file.byteOffset + file.byteLength));
    expect(r.error).toBeNull();
    expect(r.textures.length).toBeGreaterThan(0);
    for (const t of r.textures) {
      expect(t.embedded).toBe(true);
      expect(t.width).toBeGreaterThan(0);
    }
  });

  it("rejects files that are not glTF 2.0 binaries", () => {
    expect(inspectGlb(new TextEncoder().encode("PK\u0003\u0004 not a model at all").buffer).error).toMatch(/not a binary glTF/);
    expect(inspectGlb(makeGlb({ asset: { version: "1.0" } })).error).toMatch(/glTF 2\.0/);
  });

  it("lists external files a .gltf or .glb points at", () => {
    const gltf = inspectGltfText(JSON.stringify({ asset: { version: "2.0" }, buffers: [{ uri: "scene.bin", byteLength: 10 }], images: [{ uri: "wood.jpg" }] }));
    expect(gltf.externalFiles).toEqual(["scene.bin", "wood.jpg"]);
    expect(inspectGltfText("{nope").error).toMatch(/not valid/);
  });

  it("reads JPEG and WebP sizes too", () => {
    const jpeg = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0, 4, 0, 0, 0xff, 0xc0, 0, 17, 8, 0x04, 0x00, 0x08, 0x00, 3]);
    expect(imageSize(jpeg)).toEqual({ width: 2048, height: 1024 });
    const webp = new Uint8Array(30);
    webp.set(new TextEncoder().encode("RIFF"), 0);
    webp.set(new TextEncoder().encode("WEBPVP8X"), 8);
    webp.set([0xff, 0x07, 0, 0xff, 0x03, 0], 24);
    expect(imageSize(webp)).toEqual({ width: 2048, height: 1024 });
  });
});

describe("the verdict", () => {
  it("is ready for a clean, real-size .glb", () => {
    const v = glbVerdict({ fileName: "watch.glb", sizeBytes: 5_000_000, inspection: inspectGlb(withImage(2048, 2048)), scene: scene() });
    expect(v.status).toBe("ready");
    expect(v.checks.every((c) => c.level === "ok" || c.level === "info")).toBe(true);
  });

  it("blocks a file over the upload limit, and says the limit", () => {
    const v = glbVerdict({ fileName: "big.glb", sizeBytes: MAX_UPLOAD_BYTES + 1, inspection: inspectGlb(withImage(1024, 1024)), scene: scene() });
    expect(v.status).toBe("blocked");
    expect(v.checks.find((c) => c.id === "size")!.title).toContain(`${Math.round(MAX_UPLOAD_BYTES / 1024 / 1024)} MB`);
    expect(glbVerdict({ fileName: "ok.glb", sizeBytes: MAX_UPLOAD_BYTES, inspection: null, scene: null }).status).not.toBe("blocked");
  });

  it("blocks other formats and a .gltf, and tells how to get a .glb", () => {
    expect(glbVerdict({ fileName: "car.fbx", sizeBytes: 10, inspection: null, scene: null }).status).toBe("blocked");
    const gltf = inspectGltfText(JSON.stringify({ asset: { version: "2.0" }, buffers: [{ uri: "scene.bin", byteLength: 10 }] }));
    const v = glbVerdict({ fileName: "car.gltf", sizeBytes: 100, inspection: gltf, scene: null });
    expect(v.status).toBe("blocked");
    expect(v.checks.find((c) => c.id === "format")!.fix).toMatch(/\.glb/);
  });

  it("blocks compression the preview can't decode", () => {
    const glb = withImage(1024, 1024, { extensionsUsed: ["KHR_draco_mesh_compression"], extensionsRequired: ["KHR_draco_mesh_compression"] });
    const v = glbVerdict({ fileName: "a.glb", sizeBytes: 1000, inspection: inspectGlb(glb), scene: null });
    expect(levels(v).compression).toBe("error");
  });

  it("suggests resizing huge textures with glTF Transform", () => {
    const v = glbVerdict({ fileName: "a.glb", sizeBytes: 1000, inspection: inspectGlb(withImage(8192, 8192)), scene: scene() });
    expect(v.status).toBe("fixes");
    expect(v.checks.find((c) => c.id === "textures")!.fix).toMatch(/gltf-transform/);
  });

  it("warns about dense meshes, odd sizes and a car on its side", () => {
    const heavy = glbVerdict({ fileName: "a.glb", sizeBytes: 1000, inspection: inspectGlb(withImage(512, 512)), scene: scene({ triangleCount: HEAVY_TRIANGLES + 1 }) });
    expect(levels(heavy).triangles).toBe("warning");
    const odd = glbVerdict({ fileName: "a.glb", sizeBytes: 1000, inspection: inspectGlb(withImage(512, 512)), scene: scene({ unitGuess: "unknown", extents: [900, 800, 700] }) });
    expect(levels(odd).scale).toBe("warning");
    const cm = glbVerdict({ fileName: "a.glb", sizeBytes: 1000, inspection: inspectGlb(withImage(512, 512)), scene: scene({ unitGuess: "cm" }) });
    expect(levels(cm).scale).toBe("info");
    const sideways = glbVerdict({ fileName: "a.glb", sizeBytes: 1000, inspection: inspectGlb(withImage(512, 512)), scene: scene({ category: "car", dimensionsMeters: [1.9, 4.5, 1.3] }) });
    expect(levels(sideways).orientation).toBe("warning");
    const upright = glbVerdict({ fileName: "a.glb", sizeBytes: 1000, inspection: inspectGlb(withImage(512, 512)), scene: scene({ category: "car", dimensionsMeters: [1.9, 1.3, 4.5] }) });
    expect(levels(upright).orientation).toBe("info");
  });

  it("blocks when the model fails to load", () => {
    const v = glbVerdict({ fileName: "a.glb", sizeBytes: 1000, inspection: inspectGlb(withImage(512, 512)), scene: null, loadError: "No usable geometry." });
    expect(v.status).toBe("blocked");
  });
});
