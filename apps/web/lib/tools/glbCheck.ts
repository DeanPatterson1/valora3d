import { MAX_UPLOAD_BYTES } from "@/lib/pricing";
import { checkGlbHeader } from "@/lib/uploads/validate";
import { formatBytes } from "./formatBytes";

/**
 * The free .glb checker (/tools/glb-checker): everything here is pure and runs in the visitor's browser. It reads
 * the file's glTF JSON and image headers without three.js; the page then loads the model with the studio's own
 * loader (components/viewer/loadModel.ts) and analysis (components/viewer/sceneStats.ts + lib/scene/analyze.ts)
 * for triangles, size and units, and `glbVerdict` turns both into a list of checks with concrete fixes.
 */

/** Longest texture edge above which the checker suggests resizing. */
export const LARGE_TEXTURE_PX = 4096;
/** Triangle count above which the checker warns that previews may be slow. A guideline, not a hard limit. */
export const HEAVY_TRIANGLES = 3_000_000;

/** Compression extensions the studio's plain GLTFLoader cannot decode (it ships no Draco, Meshopt or KTX2 decoder). */
export const UNDECODABLE_EXTENSIONS: Record<string, string> = {
  KHR_draco_mesh_compression: "Draco mesh compression",
  EXT_meshopt_compression: "Meshopt compression",
  KHR_texture_basisu: "KTX2 / Basis Universal textures",
};

export type TextureInfo = {
  name: string;
  mimeType: string | null;
  /** True when the image bytes live inside the file (a buffer view or a data: URI). */
  embedded: boolean;
  bytes: number | null;
  width: number | null;
  height: number | null;
};

export type FileInspection = {
  kind: "glb" | "gltf";
  /** Why the file could not be read as glTF 2.0, or null. */
  error: string | null;
  textures: TextureInfo[];
  /** Buffers and images that point at files outside this one. */
  externalFiles: string[];
  extensionsUsed: string[];
  extensionsRequired: string[];
  meshCount: number;
  animationCount: number;
  generator: string | null;
};

type GltfJson = {
  asset?: { version?: string; generator?: string };
  buffers?: { uri?: string; byteLength?: number }[];
  bufferViews?: { buffer: number; byteOffset?: number; byteLength: number }[];
  images?: { name?: string; uri?: string; mimeType?: string; bufferView?: number }[];
  meshes?: unknown[];
  animations?: unknown[];
  extensionsUsed?: string[];
  extensionsRequired?: string[];
};

const EMPTY: Omit<FileInspection, "kind" | "error"> = {
  textures: [], externalFiles: [], extensionsUsed: [], extensionsRequired: [], meshCount: 0, animationCount: 0, generator: null,
};

const isData = (uri: string) => uri.startsWith("data:");

/** Width and height from a PNG, JPEG or WebP header, or null when the format is not recognized. */
export function imageSize(bytes: Uint8Array): { width: number; height: number } | null {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  // PNG: 8-byte signature, then the IHDR chunk with big-endian width and height.
  if (bytes.length >= 24 && bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47) {
    return { width: view.getUint32(16), height: view.getUint32(20) };
  }
  // JPEG: walk the segments to the first start-of-frame marker.
  if (bytes.length >= 4 && bytes[0] === 0xff && bytes[1] === 0xd8) {
    let i = 2;
    while (i + 9 < bytes.length) {
      if (bytes[i] !== 0xff) { i++; continue; }
      const marker = bytes[i + 1];
      if (marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc) {
        return { height: view.getUint16(i + 5), width: view.getUint16(i + 7) };
      }
      if (marker === 0xd8 || marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) { i += 2; continue; }
      i += 2 + view.getUint16(i + 2);
    }
    return null;
  }
  // WebP: RIFF....WEBP then a VP8, VP8L or VP8X chunk.
  if (bytes.length >= 30 && String.fromCharCode(...bytes.subarray(0, 4)) === "RIFF" && String.fromCharCode(...bytes.subarray(8, 12)) === "WEBP") {
    const chunk = String.fromCharCode(...bytes.subarray(12, 16));
    if (chunk === "VP8 ") return { width: view.getUint16(26, true) & 0x3fff, height: view.getUint16(28, true) & 0x3fff };
    if (chunk === "VP8L") {
      const b = view.getUint32(21, true);
      return { width: (b & 0x3fff) + 1, height: ((b >> 14) & 0x3fff) + 1 };
    }
    if (chunk === "VP8X") {
      const w = bytes[24] | (bytes[25] << 8) | (bytes[26] << 16);
      const h = bytes[27] | (bytes[28] << 8) | (bytes[29] << 16);
      return { width: w + 1, height: h + 1 };
    }
  }
  return null;
}

function dataUriBytes(uri: string): Uint8Array | null {
  const comma = uri.indexOf(",");
  if (comma < 0 || !uri.slice(0, comma).includes(";base64")) return null;
  try {
    const bin = atob(uri.slice(comma + 1));
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  } catch {
    return null;
  }
}

/** Reads the glTF JSON (and, for .glb, the binary chunk) that a file carries. */
export function inspectGltf(json: GltfJson, bin: Uint8Array | null, kind: "glb" | "gltf"): FileInspection {
  if (!json.asset?.version?.startsWith("2.")) return { ...EMPTY, kind, error: "This is not a glTF 2.0 file." };
  const externalFiles: string[] = [];
  json.buffers?.forEach((b, i) => {
    if (b.uri && !isData(b.uri)) externalFiles.push(b.uri);
    // A .glb's first buffer without a uri is the binary chunk.
    if (!b.uri && !(kind === "glb" && i === 0)) externalFiles.push(`buffer ${i}`);
  });
  const textures: TextureInfo[] = (json.images ?? []).map((img, i) => {
    const name = img.name || (img.uri && !isData(img.uri) ? img.uri : `Image ${i + 1}`);
    let bytes: Uint8Array | null = null;
    let embedded = false;
    if (img.uri) {
      if (isData(img.uri)) { embedded = true; bytes = dataUriBytes(img.uri); }
      else externalFiles.push(img.uri);
    } else if (img.bufferView !== undefined) {
      embedded = true;
      const bv = json.bufferViews?.[img.bufferView];
      if (bv && bv.buffer === 0 && bin) bytes = bin.subarray(bv.byteOffset ?? 0, (bv.byteOffset ?? 0) + bv.byteLength);
      else if (bv) return { name, mimeType: img.mimeType ?? null, embedded, bytes: bv.byteLength, width: null, height: null };
    }
    const size = bytes ? imageSize(bytes) : null;
    return { name, mimeType: img.mimeType ?? null, embedded, bytes: bytes?.length ?? null, width: size?.width ?? null, height: size?.height ?? null };
  });
  return {
    kind,
    error: null,
    textures,
    externalFiles,
    extensionsUsed: json.extensionsUsed ?? [],
    extensionsRequired: json.extensionsRequired ?? [],
    meshCount: json.meshes?.length ?? 0,
    animationCount: json.animations?.length ?? 0,
    generator: json.asset.generator ?? null,
  };
}

const JSON_CHUNK = 0x4e4f534a;
const BIN_CHUNK = 0x004e4942;

/** Parses a .glb's header and chunks. The header check is the one the upload pipeline uses. */
export function inspectGlb(buffer: ArrayBuffer): FileInspection {
  const bytes = new Uint8Array(buffer);
  const headerError = checkGlbHeader(bytes.subarray(0, 12), bytes.byteLength);
  if (headerError) return { ...EMPTY, kind: "glb", error: headerError };
  const view = new DataView(buffer);
  let json: GltfJson | null = null;
  let bin: Uint8Array | null = null;
  let offset = 12;
  while (offset + 8 <= bytes.byteLength) {
    const length = view.getUint32(offset, true);
    const type = view.getUint32(offset + 4, true);
    const start = offset + 8;
    if (start + length > bytes.byteLength) return { ...EMPTY, kind: "glb", error: "The file is cut short: a chunk runs past its end." };
    if (type === JSON_CHUNK && !json) {
      try {
        json = JSON.parse(new TextDecoder().decode(bytes.subarray(start, start + length))) as GltfJson;
      } catch {
        return { ...EMPTY, kind: "glb", error: "The file's glTF description is not valid JSON." };
      }
    } else if (type === BIN_CHUNK && !bin) {
      bin = bytes.subarray(start, start + length);
    }
    offset = start + length;
  }
  if (!json) return { ...EMPTY, kind: "glb", error: "The file has no glTF description." };
  return inspectGltf(json, bin, "glb");
}

/** Parses a .gltf (JSON) file. Its buffers and images usually live in separate files. */
export function inspectGltfText(text: string): FileInspection {
  try {
    return inspectGltf(JSON.parse(text) as GltfJson, null, "gltf");
  } catch {
    return { ...EMPTY, kind: "gltf", error: "The file is not valid glTF JSON." };
  }
}

export type SceneFacts = {
  triangleCount: number;
  meshCount: number;
  materialCount: number;
  /** Raw bounding-box size in file units, x / y / z. */
  extents: [number, number, number];
  unitGuess: "m" | "mm" | "cm" | "in" | "unknown";
  dimensionsMeters: [number, number, number];
  category: "car" | "product";
  rigged: boolean;
  animationClipCount: number;
};

export type CheckLevel = "error" | "warning" | "info" | "ok";
export type Check = { id: string; level: CheckLevel; title: string; detail: string; fix?: string };
export type Verdict = { status: "ready" | "fixes" | "blocked"; headline: string; checks: Check[] };

export type VerdictInput = {
  fileName: string;
  sizeBytes: number;
  inspection: FileInspection | null;
  /** From the three.js load; null when the load was skipped or failed. */
  scene: SceneFacts | null;
  /** Why the three.js load failed, when it was attempted. */
  loadError?: string | null;
};

const maxMB = Math.round(MAX_UPLOAD_BYTES / 1024 / 1024);
const UNIT_NAMES = { mm: "millimeters", cm: "centimeters", in: "inches", m: "meters" } as const;
const RESIZE_FIX = "Resize the textures to 2048 or 4096 pixels in your 3D app or image editor, or with glTF Transform: npx @gltf-transform/cli resize in.glb out.glb --width 2048 --height 2048";

/** The checks and the overall verdict. Pure: the page and the tests call it with the same facts. */
export function glbVerdict({ fileName, sizeBytes, inspection, scene, loadError }: VerdictInput): Verdict {
  const checks: Check[] = [];
  const ext = fileName.split(".").pop()?.toLowerCase() ?? "";

  if (ext !== "glb" && ext !== "gltf") {
    checks.push({ id: "format", level: "error", title: "Not a glTF file", detail: `A .${ext || "?"} file can't be checked or uploaded. Valora3D accepts a single .glb file.`, fix: "Export your model as glTF Binary (.glb) from your 3D app. See the export guides for step-by-step instructions." });
    return finish(checks);
  }
  if (sizeBytes === 0) {
    checks.push({ id: "size", level: "error", title: "The file is empty", detail: "It has no bytes to read.", fix: "Export the model again." });
    return finish(checks);
  }
  if (sizeBytes > MAX_UPLOAD_BYTES) {
    checks.push({ id: "size", level: "error", title: `Over the ${maxMB} MB upload limit`, detail: `This file is ${formatBytes(sizeBytes)}.`, fix: `Reduce it below ${maxMB} MB: resize large textures, remove hidden or unused objects, and simplify dense meshes (glTF Transform's resize and simplify commands can do this). Keep the original.` });
  } else {
    checks.push({ id: "size", level: "ok", title: "Within the upload limit", detail: `${formatBytes(sizeBytes)} of ${maxMB} MB.` });
  }

  if (ext === "gltf") {
    const external = inspection?.externalFiles.length ?? 0;
    checks.push({
      id: "format", level: "error", title: "A .gltf file, not a .glb",
      detail: external > 0 ? `It points at ${external} separate file${external === 1 ? "" : "s"} (such as ${inspection!.externalFiles[0]}), which would not travel with an upload.` : "Valora3D uploads accept the single-file binary form only.",
      fix: "Export again as glTF Binary (.glb), which packs the geometry and textures into one file. Or convert it with glTF Transform: npx @gltf-transform/cli copy model.gltf model.glb",
    });
  }

  if (!inspection) return finish(checks);
  if (inspection.error) {
    checks.push({ id: "parse", level: "error", title: "The file can't be read", detail: inspection.error, fix: "Export it again as glTF 2.0 Binary (.glb). Renaming another format to .glb does not convert it." });
    return finish(checks);
  }

  if (ext === "glb" && inspection.externalFiles.length > 0) {
    checks.push({ id: "external", level: "error", title: "It depends on separate files", detail: `This .glb points at ${inspection.externalFiles.join(", ")}, which would be missing after upload.`, fix: "Re-export with textures embedded (in most exporters, the glTF Binary format embeds them), then check the file again." });
  }

  const undecodable = inspection.extensionsRequired.filter((e) => e in UNDECODABLE_EXTENSIONS);
  if (undecodable.length > 0) {
    checks.push({ id: "compression", level: "error", title: "Uses compression the preview can't read", detail: `The file requires ${undecodable.map((e) => UNDECODABLE_EXTENSIONS[e]).join(" and ")}.`, fix: "Export again with mesh compression (Draco) and KTX2 textures turned off. To make the file smaller, resize textures instead." });
  }

  const tex = inspection.textures;
  if (tex.length === 0) {
    checks.push({ id: "textures", level: "info", title: "No image textures", detail: "The model uses plain material colors only. That's fine if it's meant to look that way; otherwise its textures were lost on export.", fix: "If the model should have textures, bake procedural or app-specific materials to images and export again." });
  } else {
    const large = tex.filter((t) => Math.max(t.width ?? 0, t.height ?? 0) > LARGE_TEXTURE_PX);
    const embedded = tex.filter((t) => t.embedded).length;
    if (large.length > 0) {
      const biggest = large.reduce((a, b) => (Math.max(b.width ?? 0, b.height ?? 0) > Math.max(a.width ?? 0, a.height ?? 0) ? b : a));
      checks.push({ id: "textures", level: "warning", title: `${large.length} very large texture${large.length === 1 ? "" : "s"}`, detail: `The largest is ${biggest.width} × ${biggest.height} pixels. Textures over ${LARGE_TEXTURE_PX} pixels rarely show more detail in a 1080p video but make the file heavier.`, fix: RESIZE_FIX });
    } else {
      checks.push({ id: "textures", level: "ok", title: `${tex.length} texture${tex.length === 1 ? "" : "s"}, ${embedded} embedded`, detail: `None is larger than ${LARGE_TEXTURE_PX} pixels on a side.` });
    }
  }

  if (loadError) {
    checks.push({ id: "load", level: "error", title: "The model didn't load", detail: loadError, fix: "Open the file in a fresh scene of your 3D app to confirm it imports, then export it again as .glb." });
    return finish(checks);
  }
  if (!scene) return finish(checks);

  if (scene.triangleCount > HEAVY_TRIANGLES) {
    checks.push({ id: "triangles", level: "warning", title: "A very dense model", detail: `${scene.triangleCount.toLocaleString("en-US")} triangles. The in-browser preview may be slow, and fine detail beyond what the camera sees adds file size without improving the video.`, fix: "Remove hidden parts and simplify dense meshes on a copy (for example Blender's Decimate modifier, or glTF Transform's simplify command), checking that the silhouette still looks right." });
  } else {
    checks.push({ id: "triangles", level: "ok", title: `${scene.triangleCount.toLocaleString("en-US")} triangles`, detail: `${scene.meshCount} mesh${scene.meshCount === 1 ? "" : "es"}, ${scene.materialCount} material${scene.materialCount === 1 ? "" : "s"}.` });
  }

  const dims = scene.dimensionsMeters.map((d) => (d >= 1 ? `${d.toFixed(2)} m` : `${Math.round(d * 100)} cm`)).join(" × ");
  if (scene.unitGuess === "unknown") {
    checks.push({ id: "scale", level: "warning", title: "Unusual size", detail: `Its bounding box is ${scene.extents.map((e) => +e.toPrecision(3)).join(" × ")} file units, which doesn't match a real-world object in meters, centimeters, millimeters or inches.`, fix: "Set your scene units to meters and model at real-world size, then export again. Remove stray objects far from the model, which stretch its bounds." });
  } else if (scene.unitGuess !== "m") {
    checks.push({ id: "scale", level: "info", title: `Probably exported in ${UNIT_NAMES[scene.unitGuess]}`, detail: `Read as ${UNIT_NAMES[scene.unitGuess]}, it measures ${dims}. Valora3D reads the size the same way and scales it to meters.`, fix: "To be sure, export in meters at real-world size." });
  } else {
    checks.push({ id: "scale", level: "ok", title: "Real-world size", detail: `It measures ${dims} (width × height × depth).` });
  }

  // glTF is Y-up. A car's height is its smallest dimension, so a car taller than it is long was exported on its side or nose.
  const [x, y, z] = scene.dimensionsMeters;
  if (scene.category === "car" && y > Math.min(x, z)) {
    checks.push({ id: "orientation", level: "warning", title: "It may be lying on its side", detail: "For a car, the vertical (Y) size should be the smallest, but here it isn't. glTF expects Y to point up.", fix: "Rotate the model upright, apply the rotation, and export with the exporter's +Y Up option turned on." });
  } else {
    checks.push({ id: "orientation", level: "info", title: scene.category === "car" ? "Looks like a car, standing upright" : "Read as a product", detail: scene.category === "car" ? "Car-shaped proportions and part names were found, so car shots such as walk-ins and wheel spins can be offered." : "glTF expects Y to point up. If the model looks tipped over in your 3D app's glTF preview, rotate it upright and apply the rotation before exporting." });
  }

  if (scene.rigged || scene.animationClipCount > 0) {
    checks.push({ id: "animation", level: "info", title: "Animation or rig found", detail: `${scene.animationClipCount} animation clip${scene.animationClipCount === 1 ? "" : "s"}${scene.rigged ? " and a skeleton" : ""}. The model is rendered as posed in the file; the camera moves around it.` });
  }

  return finish(checks);
}

function finish(checks: Check[]): Verdict {
  if (checks.some((c) => c.level === "error")) return { status: "blocked", headline: "Not ready yet: fix the items marked below, then check again.", checks };
  if (checks.some((c) => c.level === "warning")) return { status: "fixes", headline: "It will upload, but a few changes would help.", checks };
  return { status: "ready", headline: "Ready for Valora3D.", checks };
}
