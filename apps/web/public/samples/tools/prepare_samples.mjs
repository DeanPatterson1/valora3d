// Rebuilds the studio's sample models from their CC0 sources (see ../LICENSES.md).
//
// Usage (from a scratch dir with the deps installed):
//   npm i @gltf-transform/core @gltf-transform/extensions @gltf-transform/functions sharp
//   node prepare_samples.mjs <ToyCar.glb> <Camera_01_2k.gltf | -> <pocket_watch.glb> <out dir>
//
// The studio loads samples with a plain GLTFLoader (no Draco / Meshopt / KTX2 decoders), so the
// output only uses what three.js reads natively: KHR_mesh_quantization and EXT_texture_webp.
//
// toycar.glb:  Khronos glTF-Sample-Assets "ToyCar" (CC0). The display cloth ("Fabric") under the
//              car is dropped; the body and glass sit under one `ToyCar` root scaled so the car is
//              4.3 m long (the source is a 3.8 cm toy), which lets the scene analyser read it as a
//              car and drive the car shots; the body node is named `Car_Body` and the glass
//              `Windshield`. Materials (clearcoat, sheen, transmission) are unchanged; textures
//              re-encoded as WebP.
// product.glb: Poly Haven "Camera 01" (2k), repacked from .gltf + .bin + jpg textures into a
//              single GLB; geometry untouched, nodes renamed to Camera / Camera_Strap.
// watch.glb:   Poly Haven "Pocket Watch" (CC0), 4k JPEG textures resized to 2048 and re-encoded as
//              WebP; geometry and node names untouched. Real scale (≈ 5.8 × 6.9 cm).
import { NodeIO, getBounds } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { dedup, prune, quantize, textureCompress } from "@gltf-transform/functions";
import sharp from "sharp";
import path from "node:path";

const [toyCarIn, cameraIn, watchIn, outDir] = process.argv.slice(2);
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const CAR_LENGTH_M = 4.3;

// --- car -------------------------------------------------------------------
{
  const doc = await io.read(toyCarIn);
  const root = doc.getRoot();
  const scene = root.getDefaultScene() ?? root.listScenes()[0];
  for (const node of root.listNodes()) if (node.getName() === "Fabric") node.dispose();

  // Length of the car (its long axis) in world space before rescaling.
  const b = getBounds(scene);
  const length = Math.max(...b.max.map((v, i) => v - b.min[i]));
  const body = root.listNodes().find((n) => n.getName() === "ToyCar");

  const wrapper = doc.createNode("ToyCar").setScale(Array(3).fill(CAR_LENGTH_M / length));
  for (const child of scene.listChildren()) {
    scene.removeChild(child);
    wrapper.addChild(child);
  }
  scene.addChild(wrapper);
  body.setName("Car_Body");
  body.getMesh().setName("Car_Body");
  const glass = root.listNodes().find((n) => n.getName() === "Glass");
  glass.setName("Windshield");
  glass.getMesh().setName("Windshield");

  await doc.transform(
    dedup(),
    prune(),
    quantize(),
    textureCompress({ encoder: sharp, targetFormat: "webp", quality: 88 }),
  );
  root.getAsset().extras = { source: "Khronos glTF-Sample-Assets ToyCar (CC0)", modified: "cloth removed, scaled to 4.3 m, body and glass renamed, webp textures" };
  await io.write(path.join(outDir, "toycar.glb"), doc);
}

// --- product (camera) ------------------------------------------------------
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

// --- watch -----------------------------------------------------------------
{
  const doc = await io.read(watchIn);
  await doc.transform(
    dedup(),
    prune(),
    textureCompress({ encoder: sharp, targetFormat: "webp", resize: [2048, 2048], quality: 88 }),
  );
  doc.getRoot().getAsset().extras = { source: "Poly Haven Pocket Watch (CC0)", modified: "textures resized to 2048 and re-encoded as webp" };
  await io.write(path.join(outDir, "watch.glb"), doc);
}
