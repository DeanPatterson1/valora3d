# Physics methods in Blender 5.0 — cheapest convincing build per phenomenon

Researched 2026-09-24. IDs refer to `TAXONOMY.md`. Target build: **Blender 5.0.1** (the engine's
`engine/blender_cli.py` default path is `Blender 5.0`; probed version string `5.0.1`).

Marks: `[F]` fetched, `[S]` search snippet only, `[P]` probed in Blender 5.0.1 headless
(`--background --factory-startup --disable-autoexec`) on 2026-09-24, `[R]` in-repo, `(eng)`
engineering estimate. Manual links point at `docs.blender.org/manual/en/latest/` (currently the
5.2 LTS manual); the 5.0 behaviour was probed where it matters.

---

## 0. Cross-cutting rules (apply to every physics block)

**R1. Prefer stateless over stateful.** A *stateless* method computes frame N from time and seed
alone (keyframes, drivers, procedural shaders, Geometry Nodes driven by scene time, Ocean modifier,
analytic paths). A *stateful* method needs frame N-1 (simulation zones, Bullet, cloth, Mantaflow,
dynamic paint, legacy particles). Stateless methods can be split across GPUs by frame range with no
bake, scrub correctly, and cannot diverge between workers. **Use a stateful method only when a
stateless fake would be visibly wrong.** Most "always-on" defaults in this file are stateless.

**R2. Bake once, then split.** Spec §4.7 splits final renders by frame range across rented GPUs
(D7). Every stateful effect is baked **once, on one machine, before the split**, and the cache is
shipped to workers as a hashed job asset, like textures. Workers never re-simulate. Rigid bodies can
be baked straight to keyframes (`bpy.ops.rigidbody.bake_to_keyframes` [P]), which removes the cache
entirely. Simulation-zone and Mantaflow caches go to disk (`cache_type` REPLAY / MODULAR / ALL,
data format OPENVDB default [P]). The Blender manual says the same for simulation nodes: once baked
to disk "it can be rendered in a non-sequential order" [S]
(https://docs.blender.org/manual/en/latest/physics/simulation_nodes.html).

**R3. Seeds.** Every random choice is derived from the script `seed` (spec §4.2) as
`hash(seed, blockId, instanceIndex, purpose)`. Legacy particle system seed accepts
0–2 147 483 647 [P]; **force-field `seed` only accepts 1–128** [P], so map with `1 + h % 128`.
Same Blender build + same seed + same inputs ⇒ same bake is the working assumption for Bullet, cloth
and Mantaflow; do not rely on it across builds or GPU/CPU mixes (spec §4.7 already pins one build
and GPU model per job). Because of R2, bit-exact determinism across machines is not required;
determinism *on the bake machine* is, so a rerun of "more like this" layer-1 reroll is reproducible.

**R4. True scale in, deliberate time scale out.** Ingest keeps true metres (spec §4.1); gravity
is −9.81 m/s² by default [P]. Real physics at real scale makes small objects look fast and toy-like
(a 10 cm drop takes 0.14 s: t = √(2h/g)). Every sim block therefore carries an explicit
`timeScale` (Mantaflow `time_scale` 0.0001–10 [P], cloth `time_scale` [P], rigid world `time_scale`
0–100 [P]; kinematic blocks scale their clocks). Taste defaults (eng): hero liquid 0.1–0.2 (≈ 300 fps
into 30 fps, products.md P-M02 [R]); product drops and scatters 0.3–0.5; vehicle-scale events 0.8–1.0;
ambient weather 1.0 always (slowed rain reads wrong).

**R5. Thresholds scale with the subject.** Blender defaults assume ~1 m objects: cloth collision
`distance_min` 0.015 m [P], rigid `collision_margin` 0.04 m [P], Mantaflow `resolution_max` 32 [P].
For a 5 cm lipstick, 0.04 m margin is most of the object. Every size-bearing parameter is set as a
fraction of SubjectProfile `longest` (guides per method below).

**R6. Colliders are proxies, never the raw upload.** Uploads are untrusted and often non-manifold,
self-intersecting or 1M+ polys. Build a collision proxy at compile time: decimate to ≤ 20k tris for
Bullet `MESH` (passive only) or convex decomposition for active pieces; for Mantaflow/cloth a
voxel-remeshed closed shell (Geometry Nodes `Mesh to SDF Grid` → `Grid to Mesh` [P], or the Remesh
modifier). The render mesh is untouched (spec §4.5 "materials are left alone").

**R7. Every moving particle/volume carries velocity for motion blur.** Cycles uses a point-cloud
attribute named `velocity` for deformation blur of GN points
(https://blenderartists.org/t/velocity-attribute-on-geometry-nodes-particles/1487905 [S]); volume
motion blur needs a velocity grid, with `velocity_grid`, `velocity_scale`, `velocity_unit` on the
Volume data [P] (https://developer.blender.org/docs/release_notes/3.2/cycles/ [S]). TIERS T2-05
requires shutter 0.5 ± 0.25 [R]; without velocity, sparks and rain strobe.

**R8. Every sim treats the subject as a collider and is checked against it** (TAXONOMY RB-12).
Nothing passes through the subject; nothing spawns inside its bounds.

**R9. The preview tier uses the same bake.** Mantaflow resolution changes the look and apparent
speed of smoke: "most artists test at low-res till happy, then bake at higher res, then get
frustrated that the smoke appears to move slower" (https://docs.blender.org/manual/en/2.80/physics/smoke/types/domain.html [S]).
So a heavy sim is baked at final resolution before the preview render, or the preview shows a
placeholder labelled as such. Never approve a preview on a low-res sim and ship a different high-res
sim.

**R10. Blender 5.0 vs 5.2.** Geometry-nodes hair and cloth dynamics (a declarative XPBD framework
with colliders, custom forces and effector tags) first shipped in **Blender 5.2 LTS, still marked
experimental**; rigid bodies (Jolt being evaluated) and a fluid solver are on the roadmap
(https://code.blender.org/2026/07/geometry-nodes-physics/ [F]). Blender **5.0** has instead the new
**volume grid nodes**: advection, curl, divergence, gradient, Laplacian, SDF boolean/offset/fillet,
Field-to-Grid, Sample Grid, Mesh to SDF/Density Grid, Points to SDF Grid, Grid to Mesh, etc. (30
`GeometryNode*Grid*` types present [P]; https://code.blender.org/2025/10/volume-grids-in-geometry-nodes/ [F]).
This file uses only 5.0 features; the 5.2 upgrade is a decision in PHASING.md §5.

### 0.1 Cost classes

| Class | Meaning (per 10 s, 30 fps clip at final tier, RTX-5080 class GPU; eng) |
|---|---|
| **cheap** | no bake; adds < 15% render time |
| **medium** | bake ≤ 10 min on one machine, or adds 15–60% render time |
| **heavy** | bake 10 min – several hours, or volumes/refraction that multiply render time ×1.5 or more |

Baseline: final render is ~35 s/frame for the film-grade rain scene and 2–4 s/frame for
product-render (spec §4.7). Measure every physics block's GPU-seconds and bake-seconds per spec
§4.7's cost logging; the classes above are starting labels only.

### 0.2 Blender 5.0.1 facts probed for this file [P]

| Area | Default / range (5.0.1) |
|---|---|
| Fluid domain | types GAS, LIQUID; `resolution_max` 32 (6–10000); `time_scale` 1.0; `cfl_condition` 2.0; `timesteps` 1–4, adaptive on; liquid method FLIP (APIC available); `flip_ratio` 0.97; mesh upres `mesh_scale` 2; spray/foam/bubble particles available; **viscosity** (`use_viscosity`, `viscosity_value/base/exponent`) and `surface_tension` present; gravity (0, 0, −9.81); cache REPLAY/MODULAR/ALL, data OPENVDB |
| Cloth | `quality` 5; mass 0.3 kg; air damping 1; tension/compression 15, shear 5, bending 0.5 (ANGULAR); pressure (`use_pressure`, `uniform_pressure_force`); internal springs; pin stiffness 1; collision `distance_min` 0.015 m, self-collision off |
| Rigid body world | substeps 10/frame, solver iterations 10, time scale 1.0; shapes BOX, SPHERE, CAPSULE, CYLINDER, CONE, CONVEX_HULL (default), MESH, COMPOUND; friction 0.5, restitution 0, margin 0.04 m, linear/angular damping 0.04/0.1 |
| Force fields | WIND, TURBULENCE, VORTEX, FORCE, DRAG, HARMONIC, TEXTURE, GUIDE, FLUID_FLOW, …; wind `noise` 0–10, `flow` 1.0, `seed` **1–128** |
| Legacy particles | EMITTER/HAIR; physics NEWTON/KEYED/BOIDS/FLUID; drag, brownian, damping; hair dynamics available; system seed 0–2 147 483 647 |
| Soft body | goal default 0.7, goal spring 0.5, pull/push 0.5, damping 0.5, steps 10–300 |
| Dynamic paint | canvas + brush (displace, wetmap surfaces) |
| Geometry nodes | Simulation zone, Bake node, Repeat zone, For-each element zone, Raycast, Sample Nearest Surface, Proximity, Index of Nearest, Points to Volume, Volume to Mesh, 30 grid nodes incl. Grid Advect / Curl / Mesh to SDF Grid / Sample Grid |
| Cycles | shadow caustics object flags `is_caustics_caster`, `is_caustics_receiver`; Volume `velocity_grid/scale/unit` |
| Compositor | `CompositorNodeDisplace`, `MapUV`, `Glare` present |

---

## 1. The method toolbox

Each phenomenon row in §2 names one of these as its cheapest convincing method.

| Key | Method | State | Reference |
|---|---|---|---|
| **M-KIN** | Keyframes / drivers / analytic motion (spring-damper curves, ω = v/r, parabolic hops, F-curve noise) written by `build.py` | stateless | Rigacar (GPL-3, reference only: wheel automation and suspension controls) https://github.com/digicreatures/rigacar [F] |
| **M-GND** | Geometry Nodes deformer (contact flatten + bulge, squash, sag) evaluated per frame, no sim | stateless | squish-and-bulge node-group idea (contact squish-in, border bulge-out) https://higgsas.gumroad.com/l/wrusot [S]; tyre deformation GN demo https://www.youtube.com/watch?v=U1AvAR-93uQ [S] |
| **M-GNT** | Geometry Nodes time-driven procedural motion (noise advected along wind: grass, trees, flags, fog) | stateless | windy grass with GN, no simulation https://www.blendernation.com/2024/11/19/how-to-make-windy-grass-using-blender-geometry-nodes/ [S] |
| **M-GNS** | Geometry Nodes **simulation zone** particles (spawn, forces, drag, collide via Raycast/SDF, die) with `velocity` attribute | stateful → bake | manual https://docs.blender.org/manual/en/latest/physics/simulation_nodes.html [S]; CC0 particle node groups (simulate, spawn by rate, drag, bounce/slide collision, snow example) https://blenderartists.org/t/particle-node-groups-cc0-for-simulation-nodes/1496381 [F] |
| **M-PS** | Legacy particle system + force fields (emitter, hair dynamics, boids) | stateful → bake | force fields: wind = constant force along local Z, noise adds gustiness https://docs.blender.org/manual/en/latest/physics/forces/force_fields/types/turbulence.html [S] |
| **M-RB** | Bullet rigid body world → **bake to keyframes** | stateful → keyframes | collisions/shapes/margin https://docs.blender.org/manual/en/latest/physics/rigid_body/properties/collisions.html [S]; substeps/iterations advice (10 → ~30 for stability) https://artisticrender.com/blender-rigid-body-simulation-guide/ [S] |
| **M-CL** | Cloth modifier (pins, pressure, internal springs, self-collision) | stateful → bake | https://docs.blender.org/manual/en/latest/physics/cloth/settings/index.html [S]; cushion via cloth pressure https://www.youtube.com/watch?v=4h097E4pRCw [S] |
| **M-SB** | Soft body (goal-weighted jiggle) | stateful → bake | Blender demo "Jiggly Pudding" (GN sim, CC0) https://www.blender.org/download/demo-files/ [F] |
| **M-MFG** | Mantaflow gas (smoke, fire) with collider proxy | stateful → bake (heavy) | domain voxels / resolution-vs-speed caveat https://docs.blender.org/manual/en/2.80/physics/smoke/types/domain.html [S] |
| **M-MFL** | Mantaflow liquid (FLIP/APIC, mesh upres, viscosity, spray/foam/bubbles) | stateful → bake (heavy) | https://docs.blender.org/manual/en/latest/physics/fluid/index.html [S]; demo "APIC vs FLIP solver" https://www.blender.org/download/demo-files/ [F] |
| **M-FLIP** | FLIP Fluids add-on (better whitewater, viscosity, meshing) | stateful → bake (heavy) | addon code GPL, engine MIT, some content royalty-free; paid https://github.com/rlguy/Blender-FLIP-Fluids [S], FAQ https://flipfluids.com/faq/ [S] |
| **M-VDB** | Imported OpenVDB sequence (smoke/fire/dust) placed, scaled, retimed | stateless at render (pre-made cache) | JangaFX CC0 VDB library https://jangafx.com/software/embergen/download/free-vdb-animations [F] |
| **M-VOL** | Procedural volume shader (noise advected by time, height/shape falloff) | stateless | fog/haze already in render-studio `rain_atmosphere.py` (spec §4.3) [R] |
| **M-SPR** | Image-sequence cards / sprites (background rain sheets, distant smoke, splash flipbooks) | stateless | (eng) |
| **M-SHD** | Shader-only (wetness, ripples, glitter, droplet normals, caustic gobos) | stateless | procedural rain incl. drops, splashes, ripples with GN + shaders https://www.blendernation.com/2022/06/09/procedural-rain-effect-with-geometry-nodes-in-blender/ [S] |
| **M-MNEE** | Cycles shadow caustics (manifold next-event estimation) | stateless | caustics only in shadows of refractive objects, ≤ 4 refractive bounces, smooth normals needed, enable on light + caster + receiver https://developer.blender.org/docs/release_notes/3.2/cycles/ [S], https://www.blendernation.com/2022/04/11/fast-shadow-caustics-coming-to-blender-3-2/ [S] |
| **M-COMP** | Compositor tricks (Displace for heat haze, lens drops, glare) | stateless | displace by noise pass, stronger with Z depth https://www.moddb.com/groups/blender-artist/tutorials/how-to-create-heat-distortion [S]; https://www.blenderguru.com/tutorials/how-to-create-heat-distortion [S] |
| **M-DP** | Dynamic Paint (displace canvas, wetmap) | stateful → bake | displace = intersection depth, cumulative; wetmap as render mask https://docs.blender.org/manual/en/latest/physics/dynamic_paint/canvas.html [S] |
| **M-OCN** | Ocean modifier (time-driven spectrum, foam) | stateless | https://docs.blender.org/manual/en/latest/modeling/modifiers/physics/ocean.html [S] |
| **M-FRAC** | Pre-fracture at compile (GN or Cell Fracture extension) + M-RB | stateful → keyframes | Cell Fracture now an extension (v0.2.1, Blender 4.2+, "limited support", not bundled) https://extensions.blender.org/add-ons/cell-fracture/ [S]; Blender Studio "Mesh Fracturing" GN demo (CC0) https://www.blender.org/download/demo-files/ [F] |
| **M-GRID** | 5.0 volume grid nodes in a simulation zone (advect density by a velocity grid; custom lightweight gas) | stateful → bake | https://code.blender.org/2025/10/volume-grids-in-geometry-nodes/ [F] — **experimental for us**: the post does not show a full gas solver |

---

## 2. Per-phenomenon methods

Columns: **Method** (cheapest convincing; heavier upgrade after "↑") · **Cost** · **Seed/determinism** ·
**Scale** (how it scales with true subject size) · **Failure modes** · **Ingest must know**.
References: the toolbox row's URL applies unless another is given.

### 2.1 Contact & deformation

| ID | Method | Cost | Seed / determinism | Scale | Failure modes | Ingest must know |
|---|---|---|---|---|---|---|
| CD-01 | Cycles shadows from a ground plane or shadow catcher, plus ray-traced AO in the ground shader; **no fake decal** unless the world has no floor. ↑ contact darkening decal only for stylised floating shots | cheap | none | shadow softness follows light size; fine | floor below z=0 by a unit error leaves a gap; very soft key → no seam | lowest point (already z=0, spec §4.6), true scale |
| CD-02 | **M-GND on each tyre, world space**: lower the vehicle by deflection *d*; for tyre vertices below the ground plane clamp z to 0 (flat patch); push sidewall vertices outward along the axle by `k·(d − h)` with smooth falloff over 0–0.3 r above ground; slight radial compression of tread. *d* from patch length *L*: `d = L² / (8r)`; car L 0.12–0.18 m ⇒ d ≈ 2–3.5% of r (r = 0.33 m ⇒ d 5–12 mm), bulge 20–40% of d (eng from TR). Evaluated after wheel rotation so the patch stays at the bottom while the wheel spins. Locally subdivide the contact band if the tyre is coarse | cheap | none (analytic) | *d* ∝ r; scale-free | faceted patch on low-poly tyres; flattening the rim too (select only tyre ring r∈[0.62r, 1.0r]); patch at the wrong side if the axle axis is wrong; motorbike lean needs the patch to follow the lean | `wheels[]` centre/radius/axis (exists), **tyre vs rim split** (radius band + material class rubber = rough non-metal), whether wheels are separate meshes |
| CD-03 | Rest sink: M-GND radial falloff dent (depth 5–15% of cushion thickness, eng) under each resting contact + wrinkle normal map. ↑ M-CL with pressure (pillow) or internal springs, one-off settle bake | cheap / ↑ medium | none / bake | depth ∝ cushion thickness | dent on a hard part misclassified as soft; dent without matching object sink | **soft-part map**: fabric-like material class (exists) + part boxes; which faces are seat tops (normal up) |
| CD-04 | M-KIN squash-and-stretch on landing: scale along contact normal 0.85–0.95 for 2–4 frames, volume-preserving, damped recovery (P-M01's 2 f landing shake) [R] | cheap | none | squash % independent of size | squashing rigid products (a watch) | material class fabric-like / rubber share > 50% |
| CD-05 | **Analytic trails**: sample contact points along the known (keyframed) path → curve → displaced + darkened groove on the ground (GN), grown up to the current frame: stateless because the path is known. ↑ M-DP displace canvas for characters with unknown foot plants | cheap / ↑ medium | none | groove width = tyre width / foot size | trail appears ahead of the wheel (time offset bug); tread pattern missing | wheel width (from wheel box), path from the motion block |
| CD-06 | M-KIN: dent depth decays exp(−t/τ), τ 1–4 s (eng) | cheap | none | – | – | soft-part map |
| CD-07 | GN on the scatter system: delete/flatten blades within the contact footprint (Proximity to the subject's lower hull), bend blades near it away; lower the subject 5–20 mm into ground cover (eng) | cheap | seed of the scatter | footprint from bounds | subject hovering on blade tips; blades through tyres | lower-hull samples (surface samples with low z exist), wheel boxes |
| CD-08 | Needs a hand/character asset and keyed contact; M-GND local dent on product | medium | none | – | intersection | part boxes; not before a character path exists |
| CD-09 | M-GND procedural crumple (noise displacement ramped by time) ↑ M-CL with high stiffness / plasticity-like shrink | medium | seed | – | paper-like crumple on metal | material class |
| CD-10 | Same as CD-07 for rug/carpet pile; sink 5–10 mm (eng) | cheap | none | – | – | leg contact points (lowest samples clusters) |

### 2.2 Vehicle dynamics

| ID | Method | Cost | Seed | Scale | Failure modes | Ingest must know |
|---|---|---|---|---|---|---|
| VD-01 | M-KIN damped spring on the **body** (not wheels): `z(t) = A·e^(−ζωt)·cos(ω_d t)`, f 1.2–1.6 Hz passenger, 1.8–2.0 Hz sporty, < 0.8 Hz luxury; rear 10–20% higher (RF [S]); ζ 0.3–0.5 (vehicles.md V-M03 [R]); A from drop height or decel (pitch ≈ 0.5–1.5°/g, eng). Static sag: body −1–2% of wheel radius below "as modelled" (eng) | cheap | none | frequency is per vehicle class, not per size; clamp for toy-scale models (a 30 cm toy car gets no bounce) | body moves but wheels are welded to it (single mesh) → wheels leave the ground; jelly bounce if ζ < 0.2 | **body vs wheels separable**; vehicle class hint (sport/luxury/offroad) from proportions (ground clearance / length, eng) |
| VD-02 | M-KIN: wheel rotation = path length / r; spoke-strobe guard per vehicles.md V-M01 (`frac(n·ω/2π / fps)` outside [0,0.1]∪[0.9,1.1] unless shutter ≥ 0.5) [R] | cheap | none | r from ingest | wheel spins about the wrong axis (axis from ingest); hub caps with baked text rotate (fine) | wheel centre/axis/radius (exists), spoke count (CATALOG-GAPS asks for it) |
| VD-03 | M-KIN: steer angle from path curvature, `δ = atan(wheelbase · κ)`; Ackermann inner/outer split | cheap | none | wheelbase from wheel centres | steering the rear axle; steering a single-mesh car (not possible) | front/rear axle identification (direction of travel = facing) |
| VD-04/05 | M-KIN: roll = gradient × lateral g (1–3 °/g sport, 4–7 comfort, < 2 race) [SS]; pitch same order on accel/brake; body lag 0.1–0.2 s (eng) | cheap | none | – | roll into the turn (sign error); roll on a parked car | vehicle class |
| VD-06 | M-KIN: band-limited noise on body (0.5–2 mm, 8–15 Hz) + camera micro-shake coupling when camera is car-mounted (eng) | cheap | seed | amplitude fixed in mm, not % | visible vibration at low speed | – |
| VD-07 | M-KIN: 10–30 Hz body noise 0.2–0.5 mm; exhaust tip jitter (eng) | cheap | seed | – | reads as camera shake if too big | exhaust tip location (detail point, small dark cylinder at rear, eng) |
| VD-08 | M-COMP displace with animated noise masked by a render-layer volume/cone behind each exhaust; strength falls with distance 0.3–1.5 m (eng) | cheap | seed | cone ∝ tip diameter | whole frame wobbles; haze through the car body (mask must be occluded by the car: use a holdout-aware mask pass) | exhaust tip points and direction |
| VD-09 | Cheap: M-VOL cone with advected noise, white, low density, wind-bent. ↑ M-MFG short plume | cheap / ↑ heavy | seed | plume length 0.5–3 m | steam looks like smoke (too grey/opaque) | exhaust tips |
| VD-10 | **M-VDB** (burnout smoke VDB) parented to each rear tyre contact point, retimed, wind-offset. ↑ M-MFG emitting from the tyre contact with the car as collider and wind | medium / ↑ heavy | clip choice + offset from seed | smoke volume scaled to wheel radius, not the car | same VDB twice in one shot (repeat is obvious); smoke not following the car; volume render cost | wheel contact points, driving path |
| VD-11 | M-GNS particles emitted at tyre contact, velocity = tyre tangential + upward cone, gravity, drag 0.5–2 /s, lit by the scene; big billow = M-VDB dust clips | medium | seed | particle size 1–5 mm grains + 5–20 cm billow puffs | dust in front of the car; dust on asphalt | contact points, ground material (dirt vs asphalt from world block) |
| VD-12 | M-GNS: spray sheet from each tyre (rooster tail droplets 1–3 mm, streaked by motion blur) + M-VOL mist trail behind the car | medium | seed | – | spray when the world is dry | contact points, wet flag from world |
| VD-13 | M-SHD: emission on brake-disc ring driven by a temperature attribute (blackbody 900–1100 K, eng) | cheap | none | – | glowing carbon-ceramic hub caps (wrong mesh) | brake disc detection (metal ring inside the wheel, behind spokes) — best-effort |
| VD-14 | M-GND: lateral shear of the contact band by slip angle (eng) | cheap | none | – | – | as CD-02 |
| VD-15 | M-KIN with ease-out + 1 overshoot (5–10% of travel, 0.15–0.3 s) about a hinge axis | cheap | none | – | hinge axis wrong ⇒ door flies off | **articulated parts + hinge axes**: best-effort (door seams are not in GLBs); usually unsupported |
| VD-16 | M-GNS streamlines: points advected by a potential-flow approximation around the SDF of the body (5.0 Mesh to SDF Grid + Grid Gradient [P]) rendered as thin glowing curves | medium | seed | – | lines through the body | collision proxy SDF |

### 2.3 Rigid bodies & destruction

| ID | Method | Cost | Seed | Scale | Failure modes | Ingest must know |
|---|---|---|---|---|---|---|
| RB-01 | M-KIN drop with analytic bounce: height sequence h·eⁿ (restitution e 0.2–0.5 products, eng), 1–3 bounces, rotation settle to the rest pose; pairs with SF-05. ↑ M-RB when the object must tumble into a non-rest pose | cheap / ↑ medium | seed for tilt | apply R4 time scale; real drop of 0.2 m takes 0.2 s | lands in an unstable pose (must end in ingest's rest orientation) | rest orientation (placed pose), mass-share guess (from volume, eng) |
| RB-02 | M-KIN: rotation = distance / r about the axis ⟂ to motion and up; for non-round objects (can on its side) roll about the long axis; slight speed decay (rolling resistance) | cheap | none | r from bounds | rolling a non-rollable shape; slipping (rotation ≠ distance/r) | roll axis + radius: fit a cylinder/sphere to the hull (eng; roundness test on surface samples) |
| RB-03 | M-RB with the subject convex hull; or M-KIN pivot about the support edge with rock-and-settle | cheap / medium | seed | – | pivoting about the centre | support polygon of the base (lowest samples) |
| RB-04 | M-KIN ballistic arc + spin about the principal axis of max/min inertia (stable axes); Dzhanibekov flip only for flat thin objects (eng) | cheap | seed | arc time from R4 | spinning about an arbitrary axis at constant rate reads fake | principal axes (PCA of surface samples) |
| RB-05 | M-RB scatter: 50–500 instanced pieces (convex hulls) dropped from a seeded emitter onto the ground + passive subject proxy; substeps 30–60, iterations 20–30 for small pieces (artisticrender advice 10 → ~30 [S]); **bake to keyframes** | medium (bake 1–10 min) | seed for spawn positions/orientation | margin = 2–5% of piece size (R5); piece size 1–5% of subject (eng) | jitter/explosion from interpenetrating spawns; pieces tunnelling through thin subject parts; pile never sleeps | collision proxy of subject; clear drop zone above/around (bounds) |
| RB-06 | M-RB with constraints | medium | seed | – | order errors | – |
| RB-07 | M-KIN drift: each piece has slow linear drift 1–5% of subject size per second and 5–20 °/s spin, avoids subject bounds (eng) | cheap | seed | ∝ subject | collisions through the subject | bounds + margin |
| RB-08 | M-KIN: hover bob amplitude 1–3% of height at 0.2–0.5 Hz + slow yaw drift (spec §4.3 `hover_bob`) | cheap | seed | ∝ height | constant-speed spin > 45 °/s (P-C11 cap) [R] | – |
| RB-09 | M-KIN exploded burst with ease-out-back, hold, reassemble (products.md P-M01 timings) [R]; pieces are separable parts or supplied ingredient assets | cheap | seed | travel 0.3–1.5 S (P-M01) | parts that are not separable at ingest | **separable parts** (CATALOG-GAPS rank 19) |
| RB-10 | M-KIN: spin-down with precession growth (eng) | cheap | – | – | – | round base detection |
| RB-11 | M-KIN pendulum: period 2π√(L/g), damped; ↑ M-RB chain constraints (demo "Chains Compound Collision") | cheap | – | L from the hanging part | period wrong for its size (miniature feel) | pivot point of the hanging part |
| RB-12 | Rule, not method: add the subject collision proxy (R6) as passive collider / effector to every sim | – | – | – | – | proxy |
| DS-01 | M-FRAC with radial points dense at impact + tiny shard particles (M-GNS) + glints | heavy (bake + many objects) | seed | shard size falls with distance from impact | Voronoi-looking chunks; floating fragments | closed, manifold mesh required — uploads rarely are ⇒ fracture only the proxy or **supplied props**, never the customer's hero product by default |
| DS-02 | M-FRAC + dust (M-GNS/M-VDB) | heavy | seed | – | – | as DS-01 |
| DS-03 | M-FRAC on a **prop** wall/paper/ice block that the subject breaks through; subject motion keyframed | heavy | seed | wall ∝ subject | – | subject bounds and motion path |
| DS-04 | M-CL with tearing (5.0 legacy cloth has no tearing; GN "Space Fabric Cloth Tear" demo, CC-BY, shows a GN approach) | medium | seed | – | – | prop only |

### 2.4 Soft body & cloth

| ID | Method | Cost | Seed | Scale | Failure modes | Ingest must know |
|---|---|---|---|---|---|---|
| SC-01 | **M-GNT travelling wave**: displacement along normal `A(x)·sin(kx − ωt + φ(noise))`, amplitude rising from the pole, ω from wind speed (flutter frequency grows with speed, eng); wind direction from WD-01. ↑ M-CL with pinned pole edge + wind field (bake) for hero flags | cheap / ↑ medium | seed | wave length ∝ flag length | sine-perfect regular waves; flag flapping in calm | – (prop asset) |
| SC-02 | M-CL drape: sheet (≈ 1.5× subject footprint + height) pinned at pull points animated by hooks; subject **proxy** as collider (R6); `quality` 8–15, collision `distance_min` ≈ 0.3–0.5% of subject size (R5), self-collision on; bake 100–300 frames | heavy-ish (bake 5–30 min, eng) | seed for pull direction jitter | cloth vertex spacing ≈ 1% of subject length; mass/stiffness preset "silk" vs "canvas" | sheet snags on antennas/mirrors; passes through thin parts (proxy too thin); explodes on intersections at frame 0 (start the sheet above the proxy + small offset) | proxy; top-down height map to pre-shape the sheet; thin protrusions list |
| SC-03 | Pre-baked at compile: M-CL settle for N frames then freeze (static); ↑ animated settle | medium (one bake, static afterwards) | seed | – | fabric floats above surface (distance_min too big, R5) | furniture top surfaces |
| SC-04 | Needs rigged character with separate garment meshes: M-CL with pin group = skin-bound areas, or bone-jiggle (M-KIN spring on garment bones). 5.2 XPBD cloth is the future path (R10) | heavy | – | – | garment clipping through body | rig present (ingest has it), garment separation (material/mesh split), skin weights |
| SC-05 | M-GNT: ribbon = curve following a seeded spline around the subject with travelling twist and width modulation (stateless "fake silk"); ↑ M-CL ribbon with wind | cheap / ↑ medium | seed | ribbon width 3–10% of subject height (eng) | ribbon intersects subject: sweep path must stay outside bounds + margin | bounds, clear space |
| SC-06 | M-CL `use_pressure` 2–5 (tutorial snippet [S]) one-off settle for pillows; inflatables animated via pressure ramp | medium | – | – | over-inflated balloon look on cushions | soft-part map |
| SC-07 | M-SB goal-weighted jiggle or GN sim spring per vertex toward rest (demo "Jiggly Pudding" CC0) | medium | – | – | whole product jiggles (rigid parts must be pinned) | soft vs rigid part map |
| SC-08 | M-KIN bone chain / M-GNS verlet rope (repeat zone constraint solve) hanging under gravity; swing from the parent's acceleration | cheap-medium | seed | segment count ∝ length | cable through subject; limp vs stiff | **dangling parts**: thin, long components attached at one end (part boxes + connectivity; best-effort, confidence flag) |
| SC-09 | M-GNT curtain wave (low-frequency billow noise, pinned top) | cheap | seed | – | – | – (world prop) |
| SC-10 | M-GNS flat cards with flutter torque + wind (shared with PT-02) | cheap-medium | seed | – | – | – |

### 2.5 Hair, fur, grass, foliage

| ID | Method | Cost | Seed | Scale | Failure modes | Ingest must know |
|---|---|---|---|---|---|---|
| HF-01 | M-GNT on scatter instances: rotation about the base by `bend = W·(0.6 + 0.4·gust(p − windDir·t·c)) + flutter(t, id)`; gust wave speed ≈ wind speed; blade bend ∝ height (link: windy grass GN, no simulation [S]) | cheap | seed | blade height fixed world units | everything in sync (missing per-instance phase); sway direction ≠ WD-01 | – (world) |
| HF-02 | M-GNT hierarchical: trunk sway (0.1–0.3 Hz), branch (0.5–1 Hz), leaf flutter (2–6 Hz) (eng); needs tree assets with a hierarchy or vertex-colour weights | cheap | seed | frequencies drop with tree size | rigid rotating tree | – (world assets) |
| HF-03 | HF-01 + petal shiver | cheap | seed | – | – | – |
| HF-04 | Uploaded characters rarely have curve hair; card/mesh hair → bone jiggle or M-SB with goal weights; curve hair → legacy particle hair dynamics (available [P]) or 5.2 GN hair (R10) | medium-heavy | seed | – | hair through head; hair floating | hair material/mesh detection (alpha cards, "hair" names are untrusted) |
| HF-05 | M-SHD/M-GNT fur wind ripple on a fur shell (normal perturbation), no dynamics | cheap | seed | – | – | fur-like material (fabric-like + high-frequency alpha) |
| HF-06 | CD-07 + bend-away from the tyre path over time (stateless via path) | cheap | seed | – | – | path |
| HF-07 | M-KIN bone jiggle | cheap | seed | – | – | dangling parts |

### 2.6 Particles

Shared build: **M-GNS** point sim (spawn by rate, gravity, drag, wind from WD-01, collide with
subject SDF via 5.0 `Mesh to SDF Grid` + `Sample Grid` gradient push, or Raycast [P]), instanced
cards/meshes, `velocity` attribute (R7). Cost medium (bake seconds–minutes for ≤ 100k points).
Stateless alternative for ambient weather: **analytic streams** (position = spawn + v·t wrapped in
a box that follows the camera), no bake at all.

| ID | Method specifics | Cost | Scale / numbers | Failure modes | Ingest |
|---|---|---|---|---|---|
| PT-01 | Stateless: points in a camera-following box, brownian drift 1–3 cm/s, visible only in shaft volume (density × shaft mask); spec v1 `dust_motes` | cheap | mote size 20–100 µm, rendered 1–3 px blur discs (eng) | snow-globe density; motes in shadow visible | – |
| PT-02 | M-GNS leaf cards: fall 0.5–2 m/s (eng), sideways oscillation period 0.5–1.5 s, flutter vs tumble chosen per leaf (FL [S]: flutter→tumble transition near a Froude-like number ≈ 0.67); advected by WD-01; land, slide, stop; collide with subject | medium | leaf 3–12 cm (real leaves) — do **not** scale leaves with the subject; they are scale cues | all leaves identical; perfect sine paths; leaves through car; leaves "hovering" in calm | bounds/SDF |
| PT-03 | **M-KIN procedural hop-roll** (preferred over Bullet): path downwind across the frame, planned to pass in front of or behind the subject (never through bounds + margin), speed 0.3–0.7 × wind (eng; TW tested 1–6 m/s), hop heights 0.1–0.5 r at random spacing, roll angle = distance/r, squash on landings 5%, ground height by Raycast. ↑ M-RB with low density + wind force for tumbleweeds interacting with obstacles | cheap / ↑ medium | tumbleweed Ø 0.3–1 m (eng) | smooth ball roll (bounces more than rolls on rough ground, TW [S]); against the wind; clipping the subject | bounds, ground height |
| PT-04 | Stateless analytic snow box: fall 0.5–1.5 m/s (LH [S]), lateral wobble, wind drift; flakes 2–15 mm. Accumulation: GN layer on faces with n·up > 0.7, thickness = rate·t (stateless), rounded edges | cheap | real-size flakes (scale cue) | snow at rain speed; accumulation on vertical faces | upward faces (surface normals exist) |
| PT-05 | as PT-02 with petal meshes; slower fall 0.3–1 m/s (eng) | medium | – | – | – |
| PT-06 | M-GNS confetti: burst impulse, strong drag, flutter torque, two-sided cards with metallic/matte mix | medium | 1–3 cm pieces | falling like stones (no drag) | – |
| PT-07 | M-SHD glitter (voronoi flakes with random normals → twinkle as camera moves) on surfaces; airborne glitter = PT-06 with tiny metallic cards | cheap | flake 0.2–1 mm | constant-brightness dots (needs normal randomisation) | – |
| PT-08 | M-GNS sparks: emitter at contact, speed 3–15 m/s, gravity, drag, bounce 2–3× on ground (Raycast), die 0.3–1.5 s; render as points/short curves with emission by age (blackbody ~1800 K → dark), motion blur via velocity (sparks tutorial [S] https://www.blenderguru.com/tutorials/how-to-make-sparks) | medium | real-size | round dots without streaks (velocity missing) | contact point (marker or detail point) |
| PT-09 | Stateless floaters, emissive, slow curl drift; embers rise 0.3–1 m/s with flicker | cheap | – | uniform | – |
| PT-10 | M-GNS bubbles: rise 8–33 cm/s by size (BUB [S]), zig-zag/wobble for mm-size bubbles, grow as they rise in soda; glass material with thin-film for soap bubbles | medium | bubble 0.5–5 mm (drinks) | rising in straight lines at constant speed | liquid volume region (for drinks) |
| PT-11 | M-VOL low sand haze + M-GNS grains saltating near the ground (hop 1–10 cm) | medium | – | – | – |
| PT-12 | M-MFG coloured smoke with a burst emitter, or M-GNS 100k–1M tiny points → `Points to Volume` [P] for a stateless-render billow | heavy / medium | – | spheres visible | – |
| PT-13 | as PT-09 | cheap | – | – | – |
| PT-14 | Animated assets on keyed paths (butterfly flap cycle) or M-PS BOIDS for flocks | medium | seed | real-size animals are scale cues | animals intersect subject | – |
| PT-15 | as PT-04 with grey flakes, slower | cheap | – | – | – |

### 2.7 Gases

| ID | Method | Cost | Seed | Scale | Failure modes | Ingest |
|---|---|---|---|---|---|---|
| GS-01 | Background/ambient: **M-VDB** smoke plumes (CC0) placed behind/around, retimed, rotated per seed; wisps near subject: M-VOL curl-noise ribbons (stateless). ↑ M-MFG with subject collider when the smoke must wrap the subject or the subject drives through it; domain voxel ≈ 0.5–1% of domain size (e.g. 2 m domain → res 128–256, eng; manual: larger domains need more divisions [S]); `use_noise` upres ×2 [P] | medium / ↑ heavy | clip + offsets from seed; Mantaflow bake seed | VDB scaled to scene, but plume width must stay physically plausible (a campfire VDB scaled ×10 reads wrong) | same VDB repeated; smoke through subject (VDB has no collision: keep clear of bounds); volume noise/flicker (needs samples) | bounds, collision proxy |
| GS-02 | M-VOL steam: thin density from a mask above the hot surface, advected upward 0.2–0.5 m/s (eng) by noise, fade by 10–20 cm | cheap | seed | fixed real size (a cup's steam is cup-scale) | thick grey smoke | hot surface: product top opening (detail point / marker) |
| GS-04 | M-VOL ground fog with height falloff, advected noise in wind direction (render-studio `rain_atmosphere.py`) [R] | cheap-medium (volume render) | seed | fog layer 0.1–1.5 m (real) | uniform slab | – |
| GS-05 | Cheap: M-VOL fog flowing down a guide surface (stateless flow along negative gradient of the ground); ↑ M-MFG with negative buoyancy (cold, heavy gas) | medium / ↑ heavy | seed | – | rising dry-ice | ground + subject proxy |
| GS-06 | M-VDB fire (CC0) + point light with flicker intensity from the VDB's emission integral (or seeded noise 5–12 Hz, eng); candles: M-SHD flame card + flicker light | medium | seed | real-size flames | fire without light change (LM-08) | – |
| GS-07 | M-VDB explosions (CC0) | heavy (volume render) | clip | real-size | – | – |
| GS-08 | M-GNS fine droplets (10–100 µm → render as volume via Points to Volume) in a cone from the nozzle + M-VOL haze; brief (0.3–0.8 s) | medium | seed | – | spray as smoke | nozzle point (marker) |
| GS-09 | M-MFG coloured smoke or M-VDB tinted | heavy | seed | – | – | – |
| GS-10 | M-VDB cloud assets (CC0 JangaFX cloud pack) or procedural cloud volume | heavy (volume) | seed | – | – | – |
| GS-11 | M-VOL small puffs at mouth, periodic 3–5 s | cheap | – | – | – | mouth point (character) |

### 2.8 Fluids

| ID | Method | Cost | Seed | Scale | Failure modes | Ingest |
|---|---|---|---|---|---|---|
| FL-01 | Existing render-studio rain (`rain_look.py`, spec §4.3) generalised: stateless streak sheets in a camera box; drop speed 4–9 m/s by size (GK [S]); **streak length = v × shutter time** (30 fps, 180° ⇒ 1/60 s ⇒ 6.5 m/s drop ⇒ 11 cm streak); slant = wind/fall speed; visible by backlight (LM-05). Procedural rain incl. splashes/ripples (BlenderNation GN tutorial [S]) | cheap-medium | seed | drops are real-size: never scale with subject | streaks too long (film-rate mismatch); rain inside the car interior; rain through roof (mask by subject: kill streaks inside bounds + below surfaces) | bounds, top surfaces |
| FL-02 | Stateless: seeded impact events (position, time) on ground + subject top faces (Raycast from sky); crown splash flipbook or small instanced mesh 3–8 frames; ring ripple in the ground shader (M-SHD) at the same events | cheap-medium | seed | impact rate ∝ rain rate × area | impacts on vertical faces; splashes under cover | **upward-facing surface samples** (exists: normals) |
| FL-03 | GN distribute on faces weighted by n·up and a noise mask; droplet = flattened hemisphere (contact angle 60–110° by surface: waxed paint/glass high, eng), 1–4 mm; glass/water material; M-SHD normal-map droplets for distant surfaces | cheap | seed | droplet size fixed in mm; density per cm² | droplets on undersides; droplets floating off curved surfaces (use `Sample Nearest Surface` to snap) | surface normals, material class (glass/paint/fabric absorbs), UV not needed |
| FL-04 | **M-GNS runners** (the "liquid running down a can" build): seed 3–30 drops; each step: tangential gravity `g_t = g − (g·n)n`, stick-slip (random pause 0.1–1 s), speed 1–10 cm/s (eng), re-project onto surface with `Sample Nearest Surface` [P], merge when within radius, shrink by leaving trail; trail = curve → thin mesh + wetness attribute that darkens/glosses the surface; bake per shot. ↑ M-MFL thin film only for hero macro | medium | seed | mm-scale drops regardless of product size | drops sliding straight in screen space ignoring curvature; drops leaving the surface on convex edges (must detach and fall: become FL-20 drips); runners on dry shoulder above fill line (P-M03) | normals, curvature (exists: `_poly_curvature`), material zones (label vs glass), **fill line** for containers (marker or taxonomy default: full) |
| FL-05 | GN distribute micro-droplets 20–60 /cm² (P-M03 [R]) + fog film (roughness/transmission change) **only below the fill line**; plus a few FL-04 runners | cheap-medium | seed | fixed mm scale | condensation on cap/shoulder | fill line, material zones, glass class |
| FL-06 | M-SHD wetness on ground and subject: albedo × 0.6–0.85 on porous, roughness × 0.1–0.4, clear-coat water layer, puddle mask in low areas (noise + ground normal); ground wetness 0.6–1.0 in wet worlds (vehicles.md) [R] | cheap | seed for puddle mask | – | wet world, dry subject (must couple) | material classes per zone |
| FL-07 | M-SHD puddles with ripple normals driven by FL-02 impact events; Poly Haven/ambientCG wet ground textures | cheap | seed | – | mirror-flat puddles in rain | – |
| FL-08 | **M-MFL** (FLIP; `resolution_max` 150–300 for the pour region, `mesh_scale` 2, time scale 0.1–0.2, viscosity for syrups [P]); pour source as inflow along a curve; glass as obstacle (proxy). ↑ M-FLIP for whitewater | heavy (bake 30 min – hours, eng) | seed for inflow jitter | domain sized to the pour, not the whole scene; voxel ≈ 1–2 mm for a glass-scale pour (eng) | volume loss, blobby mesh at low res; liquid leaking through thin glass walls (proxy must be thick + closed); preview/final res mismatch (R9) | container interior volume, opening, fill level (markers); **manifold container**: uploads often have single-sided glass ⇒ build a thick proxy |
| FL-09 | M-MFL splash with product as moving obstacle (keyed drop); time scale 0.1 | heavy | seed | – | – | as FL-08 |
| FL-10 | M-MFL drop onto thin film at high res; or M-GND procedural crown (stateless, stylised) | heavy / cheap stylised | seed | – | – | – |
| FL-11 | Stateless "liquid sculpture": GN tube/sheet along a seeded spline with animated noise displacement and flow texture, rendered as liquid; ↑ M-MFL guided | cheap-medium / ↑ heavy | seed | – | noisy blob look | bounds |
| FL-12 | World: M-VOL absorption/scatter (colour loss with depth), animated caustic gobo on a spot light (M-SHD voronoi), bubbles (PT-10), particulates (PT-01) | medium (volume) | seed | – | – | – |
| FL-13 | M-MFG gas with gravity ≈ 0, low dissipation, vorticity 0.1–0.5 [P range 0–4], rendered with dark density; ↑ M-GRID custom advection (experimental) (BlenderNation ink tutorial https://www.blendernation.com/2017/04/20/tutorial-ink-dropping-water-simulation/ [S]; BlenderDiplom https://www.blenderdiplom.com/en/tutorials/all-tutorials/615-tutorial-ink-drop-effect-with-cycles.html [S]) | heavy | seed | – | reads as smoke (too fast; time scale 0.2–0.4) | – |
| FL-14 | M-MFL with `use_viscosity` [P] (honey/caramel) ↑ M-FLIP viscosity; ref12 shows grey-clay fluid reads real without texturing [R] | heavy | seed | – | water-like splashes | obstacle proxy |
| FL-15 | M-OCN (time-driven, foam attribute) | cheap-medium | seed | spectrum by wind speed | tiling | – |
| FL-16 | M-GNS droplet stream hitting subject (Raycast) + FL-04 runners after impact | medium | seed | – | spray through body | proxy |
| FL-17 | PT-10 inside liquid volume + surface foam ring (M-SHD) | medium | seed | – | – | liquid region |
| FL-18 | M-RB ice cubes bobbing (kinematic buoyancy M-KIN cheaper) | medium | seed | – | – | liquid region |
| FL-19 | M-GND melt (displace down + FL-04 drips) | medium | seed | – | – | – |
| FL-20 | M-GNS drips: spawn at lowest points of convex edges (curvature + n·up < −0.3), grow, detach every 0.5–3 s, fall with gravity, impact FL-02 | cheap-medium | seed | drop 3–5 mm | drips from mid-panel | low convex edges (curvature + normals exist) |

### 2.9 Wind (WD-01)

One scene-level field built by the compiler before any effect: **(1)** Blender WIND field
(direction, `strength`, `noise` for gusts, seeded 1–128 [P]) + optional TURBULENCE field for legacy
particles, cloth and rigid bodies; **(2)** a shared Geometry Nodes group `valora_wind(p, t)` that
returns the same vector field (mean + gust wave `noise(p − dir·t·speed)` + turbulence) for every
GN-based effect. Both are generated from the same script params so they cannot disagree.
Parameters: `directionDeg`, `speedMs` 0–14 (Beaufort 0–6, BF [S]), `gustiness` 0–1,
`turbulence` 0–1. Cost cheap. **Failure mode to guard:** Blender force-field `strength` is not
m/s; calibrate per consumer (cloth, particles, GN) so that one `speedMs` produces Beaufort-true
visuals (flags extend at F3, leaves scatter at F4–5). Calibration runs once per consumer with a
test render; record the mapping table in the block.

### 2.10 Light–matter

| ID | Method | Cost | Notes / failure modes | Ingest |
|---|---|---|---|---|
| LM-01 | **M-MNEE** shadow caustics: flag caster (glass/liquid subject), receiver (floor), light [P]; limits: refractive only, only in shadows, ≤ 4 bounces, needs smooth normals [S]. Moving water caustics: animated voronoi gobo on a spot light (M-SHD) | medium (adds samples) | faceted normals on uploads ⇒ noisy caustics: auto smooth shading on the caster proxy | glass/transmission class (exists) |
| LM-02 | **M-COMP** Displace with animated noise, masked to hot zones, strength by Z depth for long-distance road haze (tutorials [S]) | cheap | whole-frame wobble; displacing the subject when the haze is behind it (use depth mask) | – |
| LM-03 | Rule + M-VOL: shafts need a light within ~30° of the camera's reverse direction (vehicles.md V-W02 [R]); anisotropy 0.3–0.7 | medium (volume) | front-lit haze gives flat fog | – |
| LM-04 | Material rule: droplets/sparks/glitter use sharp specular (roughness ≤ 0.05) | cheap | – | – |
| LM-05 | Rain streak brightness from backlight/practicals; hide front-lit streaks (eng) | cheap | – | – |
| LM-06 | M-COMP lens drops (refraction map from droplet normal texture + blur) | cheap | overused cliché; ≤ 1 shot per clip (taste) | – |
| LM-07 | Lighting rule (glass_field P-L08/P-L09) [R] | cheap | – | liquid-in-glass detection (marker/category) |
| LM-08 | Flicker light tied to fire (GS-06) | cheap | – | – |
| LM-09 | M-SHD thin film: Principled BSDF `Thin Film Thickness` / `Thin Film IOR` sockets [P] (soap film ~100–1000 nm, eng) | cheap | – | – |
| LM-10 | R7 velocity attributes + TIERS T2-05 shutter | cheap-medium | strobing sparks/rain | – |

### 2.11 Secondary motion

| ID | Method | Cost | Ingest |
|---|---|---|---|
| SF-01/02/03 | M-KIN spring chain on the dangling part: base follows the parent; tip lags with f 1–3 Hz, ζ 0.2–0.4 (eng); gravity hang at rest; collision-free by limiting angle | cheap | **dangling part detection** (thin, attached at one end, part boxes) with confidence; skip when low |
| SF-04 | M-KIN pendulum (RB-11) | cheap | pivot |
| SF-05 | M-KIN overshoot 3–10% of travel then settle in 0.2–0.5 s (P-M01 "2 f damped landing shake") [R] | cheap | – |
| SF-06 | M-KIN rotation of detected mechanism parts: seconds hand 6 °/s sweep (mechanical watch smooth sweep 6–8 beats/s) or 1 tick/s (quartz), fan 5–25 rev/s blurred (eng) | cheap | part pivot and axis (hard; markers can supply) |
| SF-07 | M-MFL slosh (heavy) or M-GND tilt-compensated liquid surface (stateless fake: surface plane tilts opposite the container acceleration, damped) | cheap / heavy | liquid region |

### 2.12 Other

| ID | Method | Cost |
|---|---|---|
| OT-01 | M-SHD growth mask (noise threshold rising with t) blending frost material + displacement | cheap |
| OT-02 | M-SHD dirt mask growing on lower body from contact direction | cheap |
| OT-03 | Keyed traffic assets on lanes (asset library) | medium |
| OT-04 | Animated sun rotation within the world block | cheap |
| OT-05 | M-KIN (magnetic snap = ease-in-expo + overshoot) | cheap |
| OT-06 | GN curve growth + instanced leaves/flowers along length | medium |
| OT-07/08 | Rules R4 | – |

---

## 3. What ingest must add (summary for the SubjectProfile owner)

Existing (engine/ingest/measure.py): true size, bounds, surface samples with normals, material
classes, parts (≤ 64 boxes), wheels (centre/radius/axis/confidence), detail points, reflection
targets, curvature.

| New field | Used by | How (eng) |
|---|---|---|
| `wheels[].tyreBand`, `wheels[].separable`, `wheels[].width` | CD-02, VD-01..05, CD-05 | tyre = rough non-metal vertices in radius band 0.62–1.0 r within the wheel cylinder; separable = mesh islands inside the cylinder |
| `bodySeparable` (vehicle body vs wheels) | VD-01, VD-04/05 | islands outside all wheel cylinders |
| `vehicleClass` hint (sport / comfort / offroad / toy) | VD-01, VD-04 | ground clearance ÷ wheel radius, length, true size (< 1 m ⇒ toy, no dynamics) |
| `softParts[]` (fabric-like zones with face-up regions) | CD-03, CD-04, CD-10, SC-06/07 | material class + part boxes + normals |
| `danglingParts[]` + pivot + confidence | SC-08, SF-01..03 | long thin parts attached at one end (connectivity of islands) |
| `restPose` + `supportPolygon` | RB-01, RB-03 | lowest-sample hull |
| `principalAxes`, `rollAxis` + `rollRadius` | RB-02, RB-04 | PCA of samples; cylinder/sphere fit |
| `collisionProxy` (hash of a decimated, closed shell) | every sim (R6, R8) | voxel remesh / SDF at 0.5–1% of longest |
| `upFacing` sample subset + `lowConvexEdges` | FL-02..05, FL-20, PT-04 | normals + curvature (exists) |
| `container` hint: opening point, interior volume, fill line | FL-04/05/08/17 | from markers first; category default "full" |
| `emitterPoints`: exhaust tips, nozzle, hot surfaces | VD-08/09/10, GS-02, GS-08 | best-effort detail points; markers override |
| `hairLike`, `furLike` zones | HF-04/05 | alpha-card hair / high-frequency alpha on fabric-like |

Every new field carries a confidence; a physics default that needs a low-confidence field is
skipped (the video is still valid), and a *requested* effect that needs it goes to `unsupported`
with a plain note (PHASING §4).
