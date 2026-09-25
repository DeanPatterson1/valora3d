# World assets: what was downloaded, and what to get next

Art pass 2026-09-25. The owner approved free Poly Haven CC0 downloads (no paid assets, no other site).
Every file below came from `api.polyhaven.com` through `tools/assets/fetch_polyhaven.py`, which checks the
API's md5 for each file, pins it by sha256 in `engine/assets/manifest.json`, and records `licenceProof`
(https://polyhaven.com/license: every Poly Haven asset is CC0) and the retrieval date. The files live in
`assets-in/library/polyhaven/` (gitignored); every world still builds its procedural fallback when they are
missing.

Re-fetch on a new machine:

```
py tools/assets/fetch_polyhaven.py hdri magalies_field_sunset
py tools/assets/fetch_polyhaven.py hdri plains_sunset
py tools/assets/fetch_polyhaven.py hdri kloppenheim_01
py tools/assets/fetch_polyhaven.py hdri cobblestone_street_night
py tools/assets/fetch_polyhaven.py model grass_medium_02 --extra dry_diff
py tools/assets/fetch_polyhaven.py model modular_urban_apartments_facade
py tools/assets/fetch_polyhaven.py model street_lamp_01
py tools/assets/fetch_polyhaven.py texture withered_grass
py tools/assets/fetch_polyhaven.py texture leafy_grass
py tools/assets/fetch_polyhaven.py texture dry_ground_01
py tools/assets/fetch_polyhaven.py texture concrete_pavement
```

## Downloaded (41 manifest entries, 167 MB)

| Poly Haven slug | Kind, size | Used by | Why |
|---|---|---|---|
| `magalies_field_sunset` | HDRI 4k | golden_field `golden` | Dry grass field at a 4 deg sun with a treeline: the sky, the key's colour and the skyline past the set |
| `plains_sunset` | HDRI 4k | golden_field `dawn`, `dusk` | Same low sun over open plains, tinted per time of day |
| `kloppenheim_01` | HDRI 4k | golden_field `overcast` | Misty overcast field at dawn: soft sky for the overcast field |
| `cobblestone_street_night` | HDRI 4k | night_street `night` | Lamp-lit European street at night: a night fill and a real skyline past the blocks |
| `grass_medium_02` (+ `dry_diff`) | glTF 1k | golden_field | Photoscanned tufts with a dry, golden colour variant: the near field and the far grass |
| `modular_urban_apartments_facade` | glTF 1k | night_street | Brick facade kit with real window / door frames, glass, cornices, crowns: replaces the grey boxes |
| `street_lamp_01` | glTF 1k | night_street | A real lantern post for every street lamp (and the far ones) |
| `withered_grass` | texture 2k | golden_field ground | Matted, sun-dried grass: the floor between the tufts |
| `leafy_grass` | texture 2k | golden_field ground | Green patches through the dry floor (more of it when overcast) |
| `dry_ground_01` | texture 2k | golden_field `track` | Dirt for the drive track |
| `concrete_pavement` | texture 2k | night_street | Pavement slabs and kerbs |

Already pinned before the pass and reused: `grass_medium_01` (tufts, ground cover), `tree_small_02` (the
field's treelines), `asphalt_02` (roads), `cloudy_vondelpark` (the courtyard).

## Next, if the owner approves more (CC0, Poly Haven only)

Ranked by how much each would lift the look.

1. `island_tree_01`, `island_tree_02` (glTF 1k, ~66 MB each). Larger, fuller trees: the field's treelines are
   all one small tree today, so a stand repeats its silhouette.
2. `fir_tree_01` / `pine_tree_01` are too heavy (~1 GB glTF); instead `fir_sapling_medium` and
   `pine_sapling_medium` (glTF) for a conifer edge in the overcast field.
3. `shanghai_bund` or `neuer_zollhof` (HDRI 4k). A second night HDRI with modern buildings and neon, so
   night_street is not always the same old-town skyline.
4. `modular_factory_facade` (glTF 1k). A second facade kit (industrial brick, roller doors) to mix with the
   apartments so a street is not one building style.
5. `rollershutter_door`, `rollershutter_window_01` (glTF). Closed shopfronts for the ground floor at night.
6. `metal_trash_can`, `fire_hydrant`, `utility_box_01`, `modular_street_seating` (glTF). Street furniture for
   the pavements (placed through the layout's camera-clearance rules like lamps).
7. `dandelion_01`, `celandine_01`, `flower_empodium` (glTF). Real wildflowers for the `wildflowers` crop
   (today the flowers are coloured triangles).
8. `wheat` is not on Poly Haven; the `wheat` crop keeps tinted grass tufts.
9. A dusk city HDRI (e.g. `rooftop_night`, tagged sunrise-sunset + night) so `dusk` on the street has a photo
   sky instead of the physical sky.

## Round 2 (2026-09-25, same approval and pinning)

| Poly Haven slug | Used by | Why |
|---|---|---|
| `metal_trash_can`, `fire_hydrant`, `utility_box_01`, `trashbag`, `standing_chalkboard_01`, `planter_box_02` | night_street furniture | Breaks up the empty pavements (placed by the layout under the lamps' camera rules) |
| `covered_car` | night_street | A parked car under a cover now and then at the kerb |
| `water_manhole_cover` | night_street | Covers set in the road |
| `neuer_zollhof` | night_street `dusk` | A blue-hour city sky and skyline instead of the physical sky |
| `island_tree_01`, `island_tree_02` | golden_field treelines | Three tree models, so a treeline no longer repeats one silhouette |
| `weed_plant_02`, `celandine_01` | golden_field ground cover | Low weeds that stay in a trampled lane (flattened under the sight line) |
| `flower_empodium`, `dandelion_01` | golden_field flowers | Real flowers (dense for `wildflowers`, sparse otherwise) |
| `flower_gazania`, `shrub_03`, `modular_street_seating` | not used yet | Downloaded and pinned; gazania's stems sit below its origin and the seating is a modular kit that needs assembly |

Still wanted: bollards and bicycles (none on Poly Haven), an uncovered parked car (none CC0 there), a second
facade kit (`modular_factory_facade`).

## Round 5 (2026-09-25, same approval and pinning)

| Poly Haven slug | Used by | Why |
|---|---|---|
| `overcast_soil` (8k, 4k) | not used (evaluated) | Critique mat-v2 #2 proposed it as the courtyard's neutral lighting baseline. Upper-hemisphere irradiance is within 10% of `cloudy_vondelpark` (4.66 vs 4.26 on the 4k files), but its open, bright horizon flattened the hood into one grey reflection and lifted the wet asphalt (look-check `real_r5_ab_soil` vs `real_r5_ab_park`, final, same key). The courtyard keeps the park panorama; soil stays pinned for a field or studio baseline. |
