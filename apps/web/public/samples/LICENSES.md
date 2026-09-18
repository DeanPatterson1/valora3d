# Sample model licences

`tools/prepare_samples.mjs` reproduces both files from the originals.

## car.glb

- **Source:** BMW M4 G82 base model � authored in-house for ModVision by the owner
  (`ModVision/models/car-models/bmw-m4-g82/bmw-m4-g82-oem.glb`).
- **Licence:** All rights reserved. Bundled here as a sample for this app only; not for
  redistribution outside it.
- **Modifications:** trimmed for the web (alternate tyre set, LED colour variants, a stray
  brake-disc fragment set and an unused mesh removed); the four wheel groups renamed `Wheel_FL` /
  `Wheel_FR` / `Wheel_RL` / `Wheel_RR` (with `_rim`, `_badge`, `_tyre` meshes) so the analyser
  detects four wheels; body paint set to a blue metallic clearcoat (the export ships near-black);
  meshes welded, simplified and quantized; textures resized to 1024 px and re-encoded as WebP.
  Metres, Y-up, 4.84 m long.

## product.glb

- **Source:** Poly Haven, "Camera 01" (2k glTF download) — https://polyhaven.com/a/Camera_01
- **Author:** Rajil Jose Macatangay (published via Poly Haven)
- **Licence:** Creative Commons Zero (CC0 1.0) — https://polyhaven.com/license
- **Modifications:** the separate `.gltf` + `.bin` + nine 2k JPEG textures were repacked into a
  single binary GLB; nodes/meshes renamed `Camera_01` → `Camera`, `Camera_01_strap` → `Camera_Strap`.
  Geometry, materials and textures are otherwise unchanged. Real-world scale (≈ 21 × 8 × 26 cm).
