# Sample model licences

All three samples are CC0 1.0 (public domain dedication): free for commercial use, no attribution
required (credited here as a courtesy). `tools/prepare_samples.mjs` reproduces every file from the
originals. Licences checked 2026-09-28 against the source's own licence page / `metadata.json`.

## toycar.glb

- **Source:** Khronos glTF-Sample-Assets, "ToyCar" (`glTF-Binary/ToyCar.glb`) —
  https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/ToyCar
- **Author:** Guido Odendahl (model), Eric Chadwick (extensions / scene)
- **Licence:** Creative Commons Zero (CC0 1.0) — `"license": "CC0-1.0"` for both entries in the
  model's `metadata.json`; https://creativecommons.org/publicdomain/zero/1.0/
- **Modifications:** the display cloth (`Fabric`) removed; the car wrapped in a `ToyCar` root scaled
  so it is 4.3 m long (the original is a 3.8 cm toy) so the studio reads it as a car; body node
  renamed `Car_Body`, glass node `Windshield`; accessors quantized; textures re-encoded as WebP.
  Materials (clearcoat, sheen, transmission) unchanged. ≈ 4.30 × 2.10 × 1.30 m.

## product.glb

- **Source:** Poly Haven, "Camera 01" (2k glTF download) — https://polyhaven.com/a/Camera_01
- **Author:** Rajil Jose Macatangay (published via Poly Haven)
- **Licence:** Creative Commons Zero (CC0 1.0) — https://polyhaven.com/license
- **Modifications:** the separate `.gltf` + `.bin` + nine 2k JPEG textures were repacked into a
  single binary GLB; nodes/meshes renamed `Camera_01` → `Camera`, `Camera_01_strap` → `Camera_Strap`.
  Geometry, materials and textures are otherwise unchanged. Real-world scale (≈ 21 × 8 × 26 cm).

## watch.glb

- **Source:** Poly Haven, "Pocket Watch" (4k glTF download, packed to GLB) —
  https://polyhaven.com/a/pocket_watch
- **Author:** PierreB3D (published via Poly Haven)
- **Licence:** Creative Commons Zero (CC0 1.0) — https://polyhaven.com/license
- **Modifications:** the four 4k JPEG textures resized to 2048 px and re-encoded as WebP. Geometry,
  node names and materials unchanged. Real-world scale (≈ 5.8 × 6.9 cm).
