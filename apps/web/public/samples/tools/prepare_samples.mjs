// Rebuilds car.glb and product.glb from their sources (see ../LICENSES.md).
//
// Usage (from a scratch dir with the deps installed):
//   npm i @gltf-transform/core @gltf-transform/extensions @gltf-transform/functions meshoptimizer sharp
//   node prepare_samples.mjs <bmw-m4-g82-oem.glb> <Camera_01_2k.gltf> <out dir>
//
// car.glb:     ModVision's in-house BMW M4 G82 (`models/car-models/bmw-m4-g82/bmw-m4-g82-oem.glb`,
//              Blender export, metres, Y-up, 4.84 m long, nose towards +Z). Trimmed for the web:
//              the alternate tyre set, the LED colour variants, a stray brake-disc fragment set
//              and an "unused" mesh are dropped; the four wheel groups are renamed Wheel_FL /
//              Wheel_FR / Wheel_RL / Wheel_RR (rim, badge and tyre meshes under each) so the
//              scene analyser detects four wheels; the body paint gets a blue metallic clearcoat;
//              meshes are welded, simplified (meshoptimizer) and quantized; textures are resized
//              to 1024 and re-encoded as WebP. Other materials are unchanged.
// product.glb: Poly Haven "Camera 01" (2k), repacked from .gltf + .bin + jpg textures into a
//              single GLB; geometry untouched, nodes renamed to Camera / Camera_Strap.
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS, KHRMaterialsClearcoat } from "@gltf-transform/extensions";
import { dedup, prune, quantize, simplify, textureCompress, weld } from "@gltf-transform/functions";
import { MeshoptSimplifier } from "meshoptimizer";
import sharp from "sharp";
import path from "node:path";

const [m4In, cameraIn, outDir] = process.argv.slice(2);
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);

// --- car -------------------------------------------------------------------
{
  const doc = await io.read(m4In);
  const root = doc.getRoot();

  // Drop what the web sample does not need. Left = +X in this model (door_FL, mirror_L sit at +X).
  const DROP = [
    /^M4_2024_tire_michelin/, // second tyre set on the same hubs as the P Zeros
    /^M4_2024_LED_[LR]_(red|yellow)/, // DRL colour variants stacked on the white ones
    /^b:polySurface\d+_b:_TNRRims/, // fragments of another rim's brake disc on one wheel only
    /^M4_2024_unused$/,
  ];
  for (const node of root.listNodes()) if (DROP.some((re) => re.test(node.getName()))) node.dispose();

  // wheels_m_black[.00N] and tire_pzero[.00N] share hub translations; map them by corner.
  const CORNER = { "": "FL", ".001": "RL", ".002": "RR", ".003": "FR" };
  for (const node of root.listNodes()) {
    const m = /^M4_2024_(wheels_m_black|tire_pzero)(\.\d{3})?$/.exec(node.getName());
    if (!m) continue;
    const corner = CORNER[m[2] ?? ""];
    const group = `Wheel_${corner}`;
    node.setName(m[1] === "tire_pzero" ? `${group}_tyre_group` : group);
    for (const child of node.listChildren()) {
      const part = m[1] === "tire_pzero" ? "tyre" : /badge/.test(child.getName()) ? "badge" : "rim";
      child.setName(`${group}_${part}`);
      child.getMesh()?.setName(`${group}_${part}`);
    }
  }

  // The export leaves the body in near-black gloss (ModVision recolours it at runtime); give the
  // sample a real paint so it reads against both studios: Portimao-blue metallic under clearcoat.
  // (`M4_2024_paint` covers the shell, doors and trunk; `.001` the hood, fenders and bumpers.)
  const clearcoat = doc.createExtension(KHRMaterialsClearcoat);
  const paint = clearcoat.createClearcoat().setClearcoatFactor(1).setClearcoatRoughnessFactor(0.05);
  for (const mat of root.listMaterials()) {
    if (!/^M4_2024_paint(\.\d{3})?$/.test(mat.getName())) continue;
    mat.setBaseColorFactor([0.02, 0.09, 0.32, 1]).setMetallicFactor(0.4).setRoughnessFactor(0.3);
    mat.setExtension("KHR_materials_clearcoat", paint);
  }

  await doc.transform(
    dedup(),
    prune({ keepLeaves: false }),
    weld(),
    simplify({ simplifier: MeshoptSimplifier, ratio: 0.4, error: 0.001 }),
    quantize(),
    textureCompress({ encoder: sharp, targetFormat: "webp", resize: [1024, 1024], quality: 85 }),
  );
  root.getAsset().extras = { source: "ModVision BMW M4 G82 (in-house)", modified: "variants trimmed, wheels renamed, paint set, welded, simplified, quantized, webp textures" };
  await io.write(path.join(outDir, "car.glb"), doc);
}

// --- product ---------------------------------------------------------------
if (cameraIn && cameraIn !== "-") {
  const doc = await io.read(cameraIn);
  const rename = { Camera_01: "Camera", Camera_01_strap: "Camera_Strap" };
  for (const node of doc.getRoot().listNodes()) {
    const name = rename[node.getName()] ?? node.getName();
    node.setName(name);
    node.getMesh()?.setName(name);
  }
  doc.getRoot().getAsset().extras = { source: "Poly Haven Camera 01 (CC0)", modified: "repacked as GLB, nodes renamed" };
  await io.write(path.join(outDir, "product.glb"), doc);
}
