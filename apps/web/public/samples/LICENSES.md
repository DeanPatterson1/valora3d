# Sample model licences

Both files are derived from CC0 1.0 (public domain) sources. Attribution is not required by
the licence but is given here anyway. `tools/prepare_samples.mjs` reproduces both files from
the originals.

## car.glb

- **Source:** Kenney, "Car Kit" (v3.1), `Models/GLB format/sedan.glb` — https://kenney.nl/assets/car-kit
- **Author:** Kenney (www.kenney.nl)
- **Licence:** Creative Commons Zero (CC0 1.0) — http://creativecommons.org/publicdomain/zero/1.0/
- **Modifications:** uniformly scaled by 4.5 / 2.55 ≈ 1.765 (baked into vertex positions and node
  translations) so the car is 4.5 m long; nodes and meshes renamed `body` → `Body`,
  `wheel-front-left` → `Wheel_FL`, `wheel-front-right` → `Wheel_FR`, `wheel-back-left` → `Wheel_RL`,
  `wheel-back-right` → `Wheel_RR`. Geometry, material and the embedded colour-palette texture are
  otherwise unchanged.

## product.glb

- **Source:** Poly Haven, "Camera 01" (2k glTF download) — https://polyhaven.com/a/Camera_01
- **Author:** Rajil Jose Macatangay (published via Poly Haven)
- **Licence:** Creative Commons Zero (CC0 1.0) — https://polyhaven.com/license
- **Modifications:** the separate `.gltf` + `.bin` + nine 2k JPEG textures were repacked into a
  single binary GLB; nodes/meshes renamed `Camera_01` → `Camera`, `Camera_01_strap` → `Camera_Strap`.
  Geometry, materials and textures are otherwise unchanged. Real-world scale (≈ 21 × 8 × 26 cm).
