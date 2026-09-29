import { MAX_UPLOAD_BYTES } from "@/lib/pricing";
import { glbVerdict, inspectGlb, inspectGltfText, UNDECODABLE_EXTENSIONS, type FileInspection, type SceneFacts, type Verdict } from "./glbCheck";

/**
 * Browser-only runner for the .glb checker. The page imports this module lazily when a file is chosen, and it in
 * turn imports three.js (via the studio's loader) lazily, so neither ships in the page's initial JavaScript.
 * Nothing here makes a network request: the file is read from memory and loaded through a blob: URL.
 */
export type GlbCheckResult = { fileName: string; sizeBytes: number; inspection: FileInspection | null; scene: SceneFacts | null; verdict: Verdict };

async function sceneFacts(file: Blob): Promise<{ scene: SceneFacts | null; loadError: string | null }> {
  const [{ loadModel }, { computeSceneStats }, { analyzeStats }] = await Promise.all([
    import("@/components/viewer/loadModel"),
    import("@/components/viewer/sceneStats"),
    import("@/lib/scene/analyze"),
  ]);
  const loaded = await loadModel(file, "glb");
  if (!loaded.ok) return { scene: null, loadError: loaded.error.message };
  const root = loaded.value.root;
  try {
    const stats = computeSceneStats(root);
    const analysis = analyzeStats(stats);
    return {
      scene: {
        triangleCount: stats.triangleCount, meshCount: stats.meshCount, materialCount: stats.materialCount, extents: stats.extents,
        unitGuess: analysis.unitGuess, dimensionsMeters: analysis.dimensionsMeters, category: analysis.category,
        rigged: analysis.rigged, animationClipCount: stats.animationClipCount,
      },
      loadError: null,
    };
  } catch {
    return { scene: null, loadError: "The file has no usable geometry: no meshes with a real size." };
  } finally {
    // The checker keeps only the numbers; release the parsed geometry and materials.
    root.traverse((o) => {
      const mesh = o as unknown as { geometry?: { dispose(): void }; material?: { dispose(): void } | { dispose(): void }[] };
      mesh.geometry?.dispose();
      for (const m of Array.isArray(mesh.material) ? mesh.material : mesh.material ? [mesh.material] : []) m.dispose();
    });
  }
}

export async function runGlbCheck(file: File): Promise<GlbCheckResult> {
  const fileName = file.name;
  const ext = fileName.split(".").pop()?.toLowerCase();
  let inspection: FileInspection | null = null;
  let scene: SceneFacts | null = null;
  let loadError: string | null = null;
  // An empty, oversized or non-glTF file is judged on its name and size alone, without reading it into memory.
  if (file.size > 0 && file.size <= MAX_UPLOAD_BYTES) {
    if (ext === "glb") inspection = inspectGlb(await file.arrayBuffer());
    else if (ext === "gltf") inspection = inspectGltfText(await file.text());
  }
  // Load only a self-contained .glb the studio's loader can decode: an external reference would make the loader
  // request that file, and a compressed one would only fail.
  const loadable = ext === "glb" && inspection !== null && !inspection.error && inspection.externalFiles.length === 0
    && !inspection.extensionsRequired.some((e) => e in UNDECODABLE_EXTENSIONS);
  if (loadable) ({ scene, loadError } = await sceneFacts(file));
  return { fileName, sizeBytes: file.size, inspection, scene, verdict: glbVerdict({ fileName, sizeBytes: file.size, inspection, scene, loadError }) };
}
