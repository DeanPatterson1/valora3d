# Physics asset sources — licence-checked

Researched 2026-09-24. Marks: `[F]` licence read on the page itself, `[S]` licence from a search
snippet or a third-party article only (re-check the source page before shipping), `[P]` probed.
Rules carried over from `research/prior-art/PRIOR-ART.md`: prefer CC0; CC-BY is fine with a credit
file; anything non-commercial, "personal/showreel only" or unstated is **not shippable**.

**Shipping rule for the farm.** Every asset a block uses is downloaded once, hashed, and stored in
our own bucket (spec §4.7: same asset hashes on every worker). No block fetches from a third-party
site at render time. Poly Haven's API is fine for curation but not as a runtime dependency
(PRIOR-ART #1).

**Rights in outputs.** Assets below are rendered into customer videos; none is redistributed as a
file. CC0 needs nothing; CC-BY needs an attribution list we keep (a credits page or the job
metadata) — decide one place and use it for every CC-BY item.

---

## 1. Volumes (VDB): smoke, fire, dust, clouds, explosions

| Item | What | Size | Licence | Verdict |
|---|---|---|---|---|
| **JangaFX free VDB library** https://jangafx.com/software/embergen/download/free-vdb-animations | 15 animated sims: Aerial Explosion (120 f, 6.6 GB), Tornado Looping (200 f, 1.7 GB), Fire Plume (250 f, 5.5 GB), Cloud Pack (10 variations, 104 MB), Grenade Dust Impact (200 f), Dust Shockwave (155 f), Small Camp Fire (200 f, 59 MB), Industrial Chimney Smoke (250 f, 1.2 GB), Ground Explosion, Building Implosion, Gasoline Explosion, High-Res Smoke Plume (167 f, 2.8 GB), Simple Fire (101 f, 65 MB), Dust Devil (101 f), Mid-Air Explosion | 59 MB – 6.6 GB each | "licensed as CC0 (Public Domain) so you are free to use them however you want!" [F] | **USE** for GS-01, GS-06, GS-07, GS-10, VD-11 dust billows. Storage-heavy: keep 1–2 proxy-resolution copies (resample with 5.0 grid nodes) for preview, full for final |
| **Between Two Pines** loopable OpenVDB smoke (5 sims) via CG Channel https://www.cgchannel.com/2021/01/download-five-free-loopable-openvdb-smoke-animations/ ; store https://gumroad.com/betweentwopines | loopable smoke, ~2 GB each | ~10 GB | "can be used in commercial projects" per CG Channel [F on the article, S on the licence] | **USE after** reading the Gumroad licence text itself; loopable = ideal for ambient smoke |
| **OpenVDB sample models** https://www.openvdb.org/download/ | smoke.vdb (2 MB), smoke2.vdb (28 MB), fire.vdb (23 MB), bunny_cloud.vdb (74 MB) | small | **No licence statement on the download page** [F]. Disney's `wdas_cloud` is CC BY-SA 3.0 [S] | **SKIP** for shipping (unstated licence; bunny shape is a test object). Fine for internal testing only |
| **VFX Assets** free cloud VDBs via CG Channel https://www.cgchannel.com/2025/02/get-four-free-cloud-vdbs-from-vfx-assets/ | 4 clouds | – | free pack "licensed for use in personal projects and showreel work"; commercial pack CAD $25 [F] | **SKIP** free pack; optional **BUY** the commercial pack if JangaFX clouds are not enough |
| Burnout/tyre-smoke VDB packs (e.g. YouTube "Car Tires VFX Burnout Smoke VDB for Blender") https://www.youtube.com/watch?v=6HkOGqZQ96s | tyre smoke | – | not stated [S] | **SKIP** until a licence is found; build VD-10 from Mantaflow once and bake our own library |

**Own library (recommended).** For VD-10 tyre smoke, GS-02 steam, GS-05 dry ice and GS-09
coloured smoke there is no clean CC0 set. Bake 3–5 variants each with Mantaflow once (heavy but
one-off), save as VDB, and they become our own assets forever.

## 2. Models & textures for particles, debris and set dressing

| Item | Use | Licence | Verdict |
|---|---|---|---|
| **Poly Haven** models, textures, HDRIs https://polyhaven.com/license | rocks (https://polyhaven.com/models/rocks), Dry Branches Medium 01 (17k tris) https://polyhaven.com/a/dry_branches_medium_01 , Namaqualand scans (10 rocks, 5 branches/ground debris), leaf-litter ground textures (Forest Floor, Dry Decay Leaves, Leaves Forest Ground, Forest Leaves 02–04) | CC0: "Anyone can then use the work in any way and for any purpose, including commercial purposes"; no attribution required [F] | **USE**: ground debris, rocks for rigid scatter, leaf-litter floors for autumn worlds, wet/puddle ground textures |
| **ambientCG Leaf Sets** e.g. https://ambientcg.com/view?id=LeafSet020 (LeafSet001–020) | photogrammetry leaf atlases (1K–8K PBR, ~30 × 15 cm set) → cut into leaf cards for PT-02 | "All assets are released under the Creative Commons CC0 license … even in commercial circumstances" [F] | **USE** for photoreal falling leaves (cards with alpha, two-sided) |
| **ambientCG** materials/decals https://ambientcg.com (licence https://docs.ambientcg.com/license/) | wet asphalt, mud, snow, sand, ice surfaces; decals | CC0 (PRIOR-ART #2) [F] | **USE** |
| **Quaternius Stylized Nature MegaKit** https://quaternius.com/packs/stylizednaturemegakit.html | 116 nature models (trees, plants, flowers, rocks, grass), glTF | CC0 "free to use in personal, educational and commercial projects" [F]; only 60–70% free, rest paid tiers | **USE for stylised looks only** (low-poly style, not photoreal). Also on Poly Pizza https://poly.pizza/bundle/Ultimate-Stylized-Nature-Pack-zyIyYd9yGr [S] |
| **Tumbleweed** (Sketchfab, biggreenorange) https://sketchfab.com/3d-models/tumbleweed-e9fa341c64fe4626b5d5b0052b0c0b64 | tumbleweed mesh, 2.7k tris | **CC Attribution** (CC-BY) [F] | **USE with credit**, or build our own procedural tumbleweed (GN: random curves on a sphere shell, CC0 by construction) — recommended, since density/porosity must vary per seed anyway |
| Other tumbleweeds (Meshy AI "CC0" generated models) https://www.meshy.ai/tags/tumbleweed | – | CC0 claimed on an AI-generation site [S] | **SKIP** (provenance of AI-generated assets is unclear) |
| **Blender Studio character library** https://studio.blender.org/characters/ | rigged characters (Rain, Spring…) for testing SC-04/HF-04 (garments, hair) | CC-BY ("use as you wish, just give a fair credit") [S] | **USE for eval/test** subjects (spec §9 wants a character in the test set) |
| BlenderKit https://www.blenderkit.com/docs/licenses/licensing-faq/ | props (confetti, debris, bottles) | CC0 + Royalty-Free; renders may be sold (PRIOR-ART #19) | **USE with care** (CC0 only by default) |

## 3. Simulation presets, node groups and demo files

| Item | What it gives | Licence | Verdict |
|---|---|---|---|
| **Blender demo files** https://www.blender.org/download/demo-files/ | Physics demos with per-file licences: "Space Fabric Cloth Tear" (Cartesian Caramel) **CC-BY**; "2D Puff Simulation" (Simon Thommes, Blender Studio) **CC-BY**; "Jiggly Pudding" (Mingwei Lim) **CC0**; "Mesh Fracturing" (Simon Thommes) **CC0**; "Particle Simulation" (Simon Thommes) **CC0**. No licence shown for: "APIC vs FLIP solver", "Lava animation", "Internal Air Pressure", "Inner Springs", "Hair Comb", "Chains Compound Collision" [F] | per file | **USE** the CC0 ones as starting node trees (GN particles, fracture, jiggle); CC-BY ones with credit; **study only** the unlicensed ones |
| **Robin Hohni particle node groups** https://blenderartists.org/t/particle-node-groups-cc0-for-simulation-nodes/1496381 → https://robinhohni.gumroad.com/l/BlenderParticleNodeGroups | Simulate Particles, Spawn By Rate, Air Resistance/Drag, bounce/slide collision, gravity/velocity; snow example; Blender 4.0+ | CC0 [F] | **USE** as the seed of M-GNS (PT-*, FL-02/04, VD-11/12). Re-verify on 5.0.1 |
| **Cell Fracture** extension https://extensions.blender.org/add-ons/cell-fracture/ | pre-fracture for DS-* | GPL (Blender add-on); v0.2.1 for 4.2+, "offered as it is, with limited support", not bundled [S] | **USE optional**; prefer the CC0 GN "Mesh Fracturing" demo approach to avoid an extension dependency on farm images |
| **Rigacar** https://github.com/digicreatures/rigacar | car rig with wheel automation and suspension | **GPL-3.0** [F]; history of breaking on new Blender versions [S] | **MINE** (ideas for wheel/suspension controls); write our own M-KIN car rig in `build.py` |
| **FLIP Fluids add-on** https://github.com/rlguy/Blender-FLIP-Fluids , https://flipfluids.com/faq/ | production liquid sims with whitewater, viscosity | addon GPL, engine MIT, some content Standard Royalty Free; paid licence for the full feature set [S] | **BUY later** if Mantaflow liquids fail the owner's grade (PHASING phase 7); Mantaflow first |
| Procedural rain GN tutorial + presets https://www.blendernation.com/2022/06/09/procedural-rain-effect-with-geometry-nodes-in-blender/ | rain, drops, splashes, ripples | not stated [S] | **MINE** (technique); render-studio's own rain code is the base (spec §4.3) |
| Droplet generators (Gumroad: "Water Droplets", "Droplet Generator", "Quick Water Drops") e.g. https://malinmp4.gumroad.com/l/pjprnk | droplets + running drops | not stated / paid [S] | **MINE** only; our FL-03/FL-04 is a small GN build |
| Squish-and-bulge GN group https://higgsas.gumroad.com/l/wrusot | contact deformer idea (CD-02/03) | not stated [S] | **MINE** only; CD-02 is ~20 nodes, build our own |
| Camera Shakify https://github.com/EatTheFuture/camera_shakify | real shake data for VD-06 camera coupling | code GPL-3, shake data CC0 (CATALOG-GAPS rank 9) [F via craft] | **USE** the data |

## 4. Reference footage for calibration (study, never ship)

| Item | Use | Licence | Verdict |
|---|---|---|---|
| ActionVFX vehicle dust trails https://www.actionvfx.com/collections/vehicle-dust-trails-stock-footage | reference for VD-11 look (speed, density, 6 angles) | commercial stock (paid) [S] | **MINE** as visual reference if bought for the §9a paid-stock month |
| Pexels / Mixkit / Pixabay rain, smoke, leaves clips | calibrate FL-01 streaks, PT-02 flutter, GS-01 motion | per spec §9a sourcing rules (hand-picked; Pexels forbids ML scraping) | **MINE** per §9a |
| Owner refs ref01, ref02, ref06, ref12 | fluid/rigid/rain calibration targets | owner-supplied social downloads, internal eval only (`assets-in/refs/MANIFEST.md`) | internal only |

## 5. Gaps

- **No clean CC0 photoreal tumbleweed, confetti, glitter or tyre-smoke asset** was found: build
  procedurally (tumbleweed, confetti, glitter) or bake our own library once (tyre smoke, steam,
  dry ice).
- **No licensed library of liquid sim caches** (pours, splashes) exists; FL-08..FL-14 must be
  simulated per job or from our own baked library of generic splashes that the product is
  composited into (a later phase decision, PHASING §5).
- OpenVDB's own sample files have no stated licence; don't ship them.
