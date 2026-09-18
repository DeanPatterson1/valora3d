// Rebuilds car.glb and product.glb from their CC0 sources (see ../LICENSES.md).
//
// Usage (from a scratch dir with the deps installed):
//   npm i @gltf-transform/core @gltf-transform/extensions @gltf-transform/functions
//   node prepare_samples.mjs <kenney_car-kit/Models/GLB format/sedan.glb> <Camera_01_2k.gltf> <out dir>
//
// car.glb:     Kenney "Car Kit" sedan, scaled x1.765 (2.55 m -> 4.5 m long) with the scale
//              baked into the vertex data, nodes renamed to Body / Wheel_FL / Wheel_FR /
//              Wheel_RL / Wheel_RR so the scene analyser detects four wheels.
// product.glb: Poly Haven "Camera 01" (2k), repacked from .gltf + .bin + jpg textures into a
//              single GLB; geometry untouched, nodes renamed to Camera / Camera_Strap.
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { transformMesh } from "@gltf-transform/functions";
import { fromScaling } from "gl-matrix/esm/mat4.js";
import path from "node:path";

const [sedanIn, cameraIn, outDir] = process.argv.slice(2);
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);

// --- car -------------------------------------------------------------------
{
  const doc = await io.read(sedanIn);
  const S = 4.5 / 2.55;
  const m = fromScaling(new Float32Array(16), [S, S, S]);
  const rename = {
    body: "Body",
    "wheel-front-left": "Wheel_FL",
    "wheel-front-right": "Wheel_FR",
    "wheel-back-left": "Wheel_RL",
    "wheel-back-right": "Wheel_RR",
  };
  for (const node of doc.getRoot().listNodes()) {
    node.setTranslation(node.getTranslation().map((v) => v * S));
    const mesh = node.getMesh();
    if (mesh) transformMesh(mesh, m);
    const name = rename[node.getName()] ?? node.getName();
    node.setName(name);
    if (mesh) mesh.setName(name);
  }
  doc.getRoot().getAsset().extras = { source: "Kenney Car Kit (CC0)", modified: "scaled x1.765, nodes renamed" };
  await io.write(path.join(outDir, "car.glb"), doc);
}

// --- product ---------------------------------------------------------------
{
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
