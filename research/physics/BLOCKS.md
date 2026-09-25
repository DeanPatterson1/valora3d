# Physics catalog additions: kinds, blocks, capability tags, checker and harness

Researched 2026-09-24. Builds on `engine/catalog.py` (kinds `world, lighting, camera, motion,
effect, grade, edit`; required manifest keys `id, kind, description, params, subjectSizeM,
aspects, costWeight, tags, tierMax`) and the phase-3 plan's capability contract
(`docs/superpowers/plans/2026-09-25-director-phase3-director.md` Task 12: `capabilities` tags of the
form `area.name`, `directorSelectable`, `requiresProfile`, `engine/director/vocabulary.json`, the
`unsupported` list). That plan says: "When `research/physics/` publishes its taxonomy, add each of
its capability tags here." §4 below is that list.

Phenomenon IDs (CD-02, FL-04 …) refer to `TAXONOMY.md`; method keys (M-KIN, M-GNS …) to
`METHODS.md`.

---

## 1. New kinds and script fields

| Kind / field | Why a separate kind | Director-selectable? | Script location |
|---|---|---|---|
| **`realism`** (new kind) | Always-on defaults (TAXONOMY class a). They need manifests (ranges, `tierMax`, cost, golden renders) like any block, but **the director never chooses them**: the compiler applies each one whose `appliesWhen` matches the SubjectProfile, world and motion. | **No** (`directorSelectable: false`) | Checker writes the resolved list into `realism: [{id, params, reason}]` as `realism_applied` repairs, so the script shows what was done and the harness can grade it |
| **`field`** (new kind, one block: `wind`) | One global wind per clip that every wind-driven block reads (WD-01). A singleton, like `grade`. | Yes (values only); always present, calm by default | `wind: {id: "wind", params}` |
| **`sim`** (new kind) | Stateful, subject-interacting simulations that need a **bake stage**, a collider proxy, a time scale and a heavy cost class (spec §8 phase-2 sim; spec §4.2 already reserves simulation effects). Kept apart from `effect` so the checker can budget them and the pipeline can bake them before the farm split (METHODS R2). | Yes | `sims: [{id, params, startS, endS}]` (≤ 1 heavy sim per clip at first; eng) |
| `effect` (existing) | Grows with weather, particles, gases and surface states that are stateless or lightly baked | Yes | `effects: [...]` (exists) |
| `motion` (existing) | Grows with physical subject motions (drive, roll, topple, toss, float) | Yes | `subject.motion` (exists) |
| `world` (existing) | Gains physics-relevant params: `groundType`, `hasFoliage`, `temperature`, `wetness`, `windDefault` | Yes | `world.params` |

`catalog.KINDS` becomes `("world", "lighting", "camera", "motion", "effect", "grade", "edit",
"realism", "field", "sim")`; `Catalog.load` rejects unknown kind folders today, so the folders
`engine/blocks/realism/`, `field/`, `sim/` must land with the kind change.

### 1.1 New optional manifest keys (all blocks)

```jsonc
"capabilities": ["weather.rain"],            // phase-3 Task 12 (exists in plan)
"directorSelectable": true,                  // phase-3 Task 12
"requiresProfile": ["wheels"],               // phase-3 has a string; allow a list of profile facts
"physics": {
  "taxonomy": ["FL-01", "FL-02"],            // TAXONOMY ids this block delivers
  "state": "stateless",                      // stateless | baked   (METHODS R1/R2)
  "touchesSubject": false,                   // needs the collider proxy (R6/R8)
  "windDriven": true,                        // reads the one wind field
  "timeScaleParam": null,                    // name of the param that sets sim time scale (R4)
  "bakeCostS": 0,                            // measured bake seconds per 10 s clip (fill after measuring)
  "couplings": ["wet_surface", "droplets"],  // blocks the checker adds when this one is present
  "requiresWorld": {"hasGround": true, "groundType": ["asphalt", "dirt", "grass", "sand", "snow"]},
  "excludes": ["snow"],                      // cannot co-exist in one clip
  "maxPerClip": 1
},
"appliesWhen": {"profile": "wheels", "placement": "ground"}   // realism kind only
```

Unknown keys are ignored by today's loader except where `_check_manifest` validates; the new keys
need validators (types, id references resolve, `taxonomy` ids exist in a checked-in list).

### 1.2 Example manifests

```jsonc
// engine/blocks/realism/tyre_contact/block.json
{ "id": "tyre_contact", "kind": "realism", "directorSelectable": false,
  "description": "Loaded tyres: a flat contact patch where each tyre meets the ground and a slight sidewall bulge. Applied to every wheeled subject on the ground.",
  "params": {
    "patchLenFrac": {"type": "number", "min": 0.3, "max": 0.6, "default": 0.45},
    "bulgeFrac":    {"type": "number", "min": 0.1, "max": 0.4, "default": 0.25}
  },
  "appliesWhen": {"profile": "wheels", "placement": "ground"},
  "requiresProfile": ["wheels"],
  "physics": {"taxonomy": ["CD-02", "VD-14"], "state": "stateless", "touchesSubject": true,
              "windDriven": false, "timeScaleParam": null, "bakeCostS": 0},
  "capabilities": ["contact.tyre"],
  "subjectSizeM": [0.1, 30.0], "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "costWeight": 1.0, "tierMax": "T3",
  "tags": {"mood": [], "energy": [], "palette": []} }

// engine/blocks/effect/falling_leaves/block.json
{ "id": "falling_leaves", "kind": "effect",
  "description": "Real-size leaves or petals drifting down and blowing with the wind, fluttering and tumbling, landing and sliding. Use sparse density near camera for depth; heavier in autumn worlds.",
  "params": {
    "variety": {"type": "enum", "values": ["autumn", "green", "cherry_petals", "rose_petals"], "default": "autumn"},
    "density": {"type": "number", "min": 0.05, "max": 1.0, "default": 0.3},
    "layer":   {"type": "enum", "values": ["foreground", "background", "both"], "default": "both"},
    "landOnGround": {"type": "bool", "default": true}
  },
  "physics": {"taxonomy": ["PT-02", "PT-05"], "state": "baked", "touchesSubject": true,
              "windDriven": true, "timeScaleParam": null, "bakeCostS": 60,
              "requiresWorld": {"hasGround": true}},
  "capabilities": ["particles.leaves", "particles.petals"],
  "subjectSizeM": [0.05, 30.0], "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "costWeight": 1.6, "tierMax": "T3",
  "tags": {"mood": ["autumn", "nostalgic", "calm"], "energy": ["calm", "medium"], "palette": ["warm"]} }
```

### 1.3 Script fragment (valora.scene/1 additions)

```jsonc
"wind":    { "id": "wind", "params": { "directionDeg": 250, "speedMs": 4.0, "gustiness": 0.4, "turbulence": 0.3 } },
"effects": [ { "id": "rain", "params": { "rateMmH": 6, "dropSizeMm": 2.0 } },
             { "id": "falling_leaves", "params": { "variety": "autumn", "density": 0.2 } } ],
"sims":    [ { "id": "drape_reveal", "startS": 0.0, "endS": 3.0, "params": { "fabric": "silk", "pull": "rear_to_front" } } ],
"realism": [ { "id": "tyre_contact", "params": { "patchLenFrac": 0.45 }, "reason": "profile.wheels" },
             { "id": "suspension",  "params": { "rideHz": 1.4 }, "reason": "profile.wheels+bodySeparable" },
             { "id": "wet_surface", "params": {}, "reason": "coupled:rain" } ]
```

---

## 2. Block list

Columns: **Default?** `auto` = realism, applied without asking; `dir` = director-selectable;
`coupled` = auto-added by another block's `couplings`. `tierMax` is what the block can reach when
built to the METHODS spec. Params show ranges; defaults in bold.

### 2.1 `realism` (always-on)

| Block | Taxonomy | appliesWhen | Params (range, **default**) | tierMax | Cost |
|---|---|---|---|---|---|
| `contact_ground` | CD-01, CD-10 | placement = ground | `occlusion` 0.5–1.0 **0.8**; `pileSinkMm` 0–15 **auto from floor type** | T3 | cheap |
| `ground_conform` | CD-07, HF-06 | world `hasFoliage` or `groundType ∈ {grass, snow, sand, gravel}` | `sinkMm` 0–30 **by ground type**; `flattenRadiusFrac` 0.02–0.2 | T3 | cheap |
| `tyre_contact` | CD-02, VD-14 | `wheels` + ground | `patchLenFrac` (L/r) 0.3–0.6 **0.45**; `bulgeFrac` 0.1–0.4 **0.25** | T3 | cheap |
| `suspension` | VD-01, VD-04, VD-05, VD-06 | `wheels` + `bodySeparable` + longest ≥ 1.5 m | `rideHz` 0.7–2.2 **by vehicleClass**; `damping` 0.2–0.6 **0.4**; `rollDegPerG` 0.5–7 **by class**; `sagFracR` 0–0.03 **0.015** | T4 | cheap |
| `wheel_roll` | VD-02, VD-03 | `wheels` + subject translates | `strobeGuard` bool **true** | T3 | cheap |
| `landing_settle` | RB-01 settle, SF-05, CD-04 | any subject motion ends or drop-in | `overshootFrac` 0.02–0.10 **0.05**; `settleS` 0.15–0.6 **0.3**; `squash` 0.8–1.0 **0.92 soft / 1.0 rigid** | T3 | cheap |
| `soft_rest` | CD-03, SC-06 (static) | `softParts` present | `sinkFrac` 0.02–0.15 **0.06** | T3 | cheap |
| `dangling_hang` | SC-08, SF-01..03 | `danglingParts` with high confidence | `stiffness` 0–1 **0.4**; `swingHz` 0.5–3 **1.5** | T3 | cheap |
| `foliage_sway` | HF-01..03, SC-09 | world `hasFoliage` or interior with open window | (reads wind) `flutter` 0–1 **0.5** | T3 | cheap |
| `sim_hygiene` | RB-12, LM-10, OT-07, OT-08 | any `sim` or particle effect | none: enforces collider proxy, velocity blur attributes, true-scale gravity, explicit time scale | – | – |
| `glass_caustics` | LM-01 (shadow), LM-07 | glass/transmission material share ≥ 5% | `strength` 0.5–1.0 **1.0** | T3 | medium |

### 2.2 `field`

| Block | Taxonomy | Params | Default? | tierMax | Capabilities |
|---|---|---|---|---|---|
| `wind` | WD-01 | `directionDeg` 0–360 (world azimuth; **seeded**), `speedMs` 0–14 **0.8** (Beaufort 0–6), `gustiness` 0–1 **0.3**, `turbulence` 0–1 **0.2** | always present; director may set values | T3 | `wind.breeze`, `wind.strong` |

### 2.3 `effect` (weather, atmosphere, particles, gases, surface states)

| Block | Taxonomy | Key params (range, **default**) | State | Couplings / deps | tierMax | Cost | Capabilities |
|---|---|---|---|---|---|---|---|
| `rain` | FL-01, FL-02, LM-05 | `rateMmH` 0.5–50 **4**; `dropSizeMm` 0.5–4 **2**; `impacts` bool **true** | stateless | wind; couples `wet_surface`, `droplets` (subject outdoors), `runners` (few); `excludes: snow` | T3 | medium | `weather.rain` |
| `snow` | PT-04 | `rate` 0.1–1 **0.4**; `flakeMm` 2–15 **6**; `accumulationMm` 0–30 **5** | stateless | wind; requires `temperature=cold` world or sets it | T3 | medium | `weather.snow` |
| `wet_surface` | FL-06, FL-07, FL-20 | `wetness` 0.3–1 **0.8**; `puddles` 0–1 **0.4**; `drips` bool **true** | stateless | coupled by rain; also "after the rain" alone | T3 | cheap | `surface.wet` |
| `droplets` | FL-03, LM-04 | `density` 0.1–1 **0.5**; `sizeMm` 0.5–4 **1.5**; `zone` enum [all, glass, paint, **up_facing**] | stateless | coupled by rain; standalone "dew/fresh" | T3 | cheap | `liquid.droplets` |
| `runners` | FL-04 | `count` 1–30 **6**; `speed` 0.2–1 **0.5**; `trail` bool **true** | baked (M-GNS) | requires a water source in the clip (rain, droplets, condensation, spray) or the ask itself | T4 | medium | `liquid.run_down` |
| `condensation` | FL-05 | `density` 20–60 /cm² **35**; `fillLevel` 0–1 **marker or 1.0**; `frost` bool **false** | stateless + few runners | requires glass/metal container zone; couples `runners(count 3)` | T4 | medium | `liquid.condensation`, `surface.frost` |
| `frost_growth` | OT-01 | `growS` 1–8 **3** | stateless | temperature cold | T4 | cheap | `surface.frost` |
| `haze_volume` (exists) | LM-03 | + reads wind drift | stateless | – | T3 | medium | `atmosphere.haze` |
| `ground_fog` | GS-04 | `heightM` 0.1–1.5 **0.4**; `density` 0–1 **0.4** | stateless | wind | T3 | medium | `atmosphere.fog` |
| `dust_motes` | PT-01 | `density` 0–1 **0.2** | stateless | visible only in shafts | T3 | cheap | `particles.dust_motes` |
| `falling_leaves` | PT-02, PT-05 | see §1.2 | baked | wind; ground | T3 | medium | `particles.leaves`, `particles.petals` |
| `tumbleweed` | PT-03 | `count` 1–3 **1**; `sizeM` 0.3–1.0 **0.6**; `lane` enum [**background_cross**, foreground_cross] | stateless (M-KIN) | wind ≥ 2 m/s (auto-raise); `requiresWorld.groundType ∈ {dirt, sand, asphalt, gravel}` | T3 | cheap | `rigid.tumbleweed` |
| `blowing_debris` | PT-11, SC-10, PT-15 | `kind` enum [sand, paper, ash, dust] **dust**; `density` 0–1 **0.3** | baked | wind ≥ 3 m/s | T3 | medium | `particles.blowing_debris` |
| `confetti` | PT-06 | `burstS` 0–30; `palette` enum; `count` 200–5000 **1500** | baked | wind | T3 | medium | `particles.confetti` |
| `glitter` | PT-07 | `mode` enum [**airborne**, surface]; `density` | baked / stateless | – | T3 | cheap | `particles.glitter` |
| `sparks` | PT-08 | `source` enum [marker, ground_contact]; `rate`; `speedMs` 3–15 **8** | baked | needs an emitter point | T4 | medium | `particles.sparks` |
| `embers` | PT-09, PT-13 | `density`; `rise` bool **true** | stateless | wind | T3 | cheap | `particles.embers` |
| `bubbles` | PT-10, FL-17 | `mode` enum [**in_liquid**, underwater, soap]; `sizeMm` 0.5–10 | baked | liquid region or water world | T4 | medium | `particles.bubbles` |
| `steam` | GS-02 | `strength` 0–1 **0.5** | stateless | emitter: container opening / marker; wind | T3 | cheap | `smoke.steam` |
| `smoke_plume` | GS-01 (ambient) | `clip` enum (VDB library) **seeded**; `placement` enum [background, **side**, behind_subject] | stateless (VDB) | wind rotates plume; must stay outside bounds + margin | T3 | heavy (volume) | `smoke.plume` |
| `dry_ice` | GS-05 | `depthM` 0.05–0.6 **0.25** | stateless fake (↑ sim later) | wind < 4 m/s else warn | T3 | medium | `smoke.dry_ice` |
| `fire` | GS-06, LM-08 | `clip` enum [candle, campfire, fire_plume] ; `flickerLight` bool **true** | stateless (VDB/card) | adds flicker light; optional `heat_haze` | T3 | heavy | `fire.flames` |
| `explosion` | GS-07 | `clip` enum | stateless (VDB) | brand-safety flag | T4 | heavy | `fire.explosion` |
| `heat_haze` | LM-02, VD-08 | `strength` 0–1 **0.4**; `zone` enum [exhaust, road, fire] | stateless (compositor) | exhaust needs `emitterPoints.exhaust` | T4 | cheap | `light.heat_haze` |
| `exhaust` | VD-07, VD-09 | `mode` enum [**idle_vapour**, rev, backfire_pop] | stateless | `wheels`; temperature cold ⇒ vapour | T4 | cheap | `vehicle.exhaust` |
| `lens_drops` | LM-06 | `amount` 0–1 **0.3**; `maxShots` 1 | stateless | rain or spray present | T4 | cheap | `camera.lens_drops` |
| `water_caustics` | LM-01 (animated), FL-12 | `scale`, `speed` | stateless | water world or pool | T3 | cheap | `light.caustics` |

### 2.4 `motion` (subject motion; director-selectable)

| Block | Taxonomy | Params | Couplings | tierMax | Capabilities |
|---|---|---|---|---|---|
| `drive` (CATALOG-GAPS rank 5) | VD-02..06, VD-11/12 | `speedKmh` 5–120 **40** (capped by size/world); `path` enum [**straight**, arc_left, arc_right, s_curve, stop]; `accel` enum [**cruise**, launch, brake_to_stop] | `wheel_roll`, `suspension`, `tyre_contact` (realism); world wet ⇒ `tyre_spray`; dirt ⇒ `dust_kick`; snow/sand/mud ⇒ tracks (CD-05) | T4 | `motion.drive` |
| `drop_settle` (spec `drop_in`) | RB-01 | `heightFrac` 0.2–1.5 **0.6** of subject height; `bounces` 0–3 **1**; `timeScale` 0.3–1 **0.5** | `landing_settle` | T3 | `motion.drop` |
| `roll` | RB-02 | `distanceFrac` 0.5–4 **1.5**; `direction` enum | needs `rollAxis` with high confidence | T3 | `motion.roll` |
| `topple` | RB-03 | `direction`; `rock` bool **true** | needs support polygon | T3 | `motion.topple` |
| `toss_tumble` | RB-04 | `arcHeightFrac` 0.5–3; `spins` 0.5–3 | `landing_settle` | T3 | `motion.tumble` |
| `float_drift` (spec `hover_bob` generalised) | RB-08 | `bobFrac` 0.01–0.03; `yawDegS` 0–20 | may add `debris_float` | T3 | `motion.float` |
| `explode_assembly` (CATALOG-GAPS rank 19) | RB-09, OT-05 | P-M01 timings | needs separable parts | T3 | `motion.explode` |
| `mechanism_run` | SF-06 | `rate` preset per mechanism | needs a part + axis (marker) | T3 | `secondary.mechanism` |
| `door_open` | VD-15 | `part` marker | needs articulated part + hinge axis | T3 | `vehicle.doors` |

### 2.5 `sim` (baked, subject-interacting)

| Block | Taxonomy | Key params | Bake | tierMax | Cost | Capabilities |
|---|---|---|---|---|---|---|
| `rigid_scatter` | RB-05, RB-12 | `pieces` enum [beans, ice, gems, coins, pills, candies, pebbles] **seeded by category**; `count` 30–500 **150**; `zone` enum [around, **onto**, behind]; `timeScale` 0.3–1 **0.5** | Bullet → keyframes | T4 | medium | `rigid.scatter` |
| `debris_float` | RB-07 | `count` 5–60; `sizeFrac` 0.02–0.15 | none (M-KIN) — kept here only because it pairs with scatter sets | T3 | cheap | `rigid.float_debris` |
| `drape_reveal` | SC-02 | `fabric` enum [**silk**, satin, canvas]; `pull` enum [rear_to_front, **side**, up]; `colour` | cloth, 100–300 f | T4 | heavy | `cloth.drape_reveal` |
| `flag` | SC-01 | `size`, `pole` placement | stateless wave (↑ cloth) | T3 | cheap | `cloth.flag` |
| `silk_ribbon` | SC-05 | `count` 1–3; `widthFrac` 0.03–0.1 | stateless (↑ cloth) | T4 | cheap | `cloth.ribbon` |
| `jiggle` | SC-07 | `softness` 0–1 | soft body | T4 | medium | `soft.jiggle` |
| `liquid_pour` | FL-08, FL-17 | `liquid` enum [water, **soda**, juice, milk, coffee, wine, oil]; `timeScale` 0.1–0.5 **0.2**; `source` marker | Mantaflow FLIP | T4 | heavy | `liquid.pour` |
| `liquid_splash` | FL-09, FL-10 | `mode` enum [**drop_in**, crown, wave_hit] | Mantaflow | T4 | heavy | `liquid.splash` |
| `liquid_sculpture` | FL-11 | `style` enum [ribbon, **wave**, crown_ring] | stateless fake (↑ guided sim) | T4 | medium | `liquid.swirl` |
| `viscous_flow` | FL-14 | `liquid` enum [**honey**, caramel, chocolate, paint] | Mantaflow + viscosity | T4 | heavy | `liquid.viscous` |
| `ink_cloud` | FL-13 | `colour`; `timeScale` 0.2–0.4 | Mantaflow gas | T4 | heavy | `liquid.ink` |
| `spray` | FL-16, GS-08 | `mode` enum [**mist**, jet, sprinkler]; `source` marker | M-GNS | T4 | medium | `liquid.spray` |
| `smoke_sim` | GS-01 (interactive), GS-09 | `colour` enum [white, **grey**, coloured]; `source` enum [ground, marker, tyres] | Mantaflow gas | T4 | heavy | `smoke.interactive`, `smoke.coloured` |
| `tyre_smoke` | VD-10 | `intensity` 0–1 | VDB library (↑ Mantaflow) | T4 | heavy | `vehicle.tyre_smoke` |
| `tyre_spray` | VD-12 | `intensity` | M-GNS (coupled by `drive` on wet) | T4 | medium | `vehicle.spray` |
| `dust_kick` | VD-11 | `intensity` | M-GNS + VDB billows (coupled by `drive` on dirt) | T4 | medium | `vehicle.dust` |
| `powder_burst` | PT-12 | `colour`; `burstS` | M-GNS → Points to Volume | T4 | heavy | `particles.powder` |
| `shatter` | DS-01..03 | `target` enum [**prop_wall**, prop_glass, prop_ice]; never the subject by default | pre-fracture + Bullet | T4 | heavy | `destruct.shatter` |

### 2.6 World params added to world blocks

`groundType` enum [studio, asphalt, dirt, gravel, sand, snow, grass, water, interior_floor, rug];
`hasFoliage` bool; `temperature` enum [cold, **mild**, hot]; `wetness` 0–1; `windDefault`
(speedMs range the world suits). These drive `appliesWhen` for realism blocks and the auto
couplings (spray on wet, dust on dirt, tracks on snow/sand, breath and exhaust vapour when cold,
heat haze on hot roads).

---

## 3. Dependencies

```
wind ─┬─► rain (slant) ─► wet_surface, droplets, runners(few), impacts/ripples  [coupled]
      ├─► snow (drift, accumulation)
      ├─► falling_leaves / tumbleweed / blowing_debris / confetti / embers
      ├─► smoke_plume, steam, ground_fog, haze drift, dry_ice (warn if > 4 m/s), exhaust vapour
      ├─► flag, silk_ribbon, drape (cloth), dangling_hang
      └─► foliage_sway (grass, trees, flowers, curtains)

drive ─► wheel_roll + suspension + tyre_contact [realism]
      ├─► wet world ⇒ tyre_spray        ├─► dirt world ⇒ dust_kick
      └─► snow/sand/mud ⇒ tracks (CD-05) └─► grass ⇒ ground_conform parting

condensation ─► runners(3)     fire ─► flicker light (+ heat_haze, embers optional)
any sim / particle ─► sim_hygiene (collider proxy, velocity blur, true-scale g, explicit time scale)
```

Rules: the director may set only `wind` params, never per-effect wind; a coupled block is added by
the checker (repair `coupled_added`) and may be *tuned* by the director but not removed while its
parent is present.

---

## 4. Capability tags for `engine/director/vocabulary.json`

Format per the phase-3 contract: tag `area.name` (`[a-z_]+\.[a-z_]+`), `phrases` (regex fragments),
`note` (plain sentence shown when unsupported). **Existing tags are kept**; new fine-grained tags are
added so an ask is only reported "supported" when a block truly delivers it (e.g. a condensation
block must not make "pour" look supported via a coarse `sim.liquid`).

### 4.1 Changes to existing tags (with test impact)

| Existing tag | Proposal | Test impact (phase-3 Task 12 tests) |
|---|---|---|
| `sim.liquid` (liquid, water, drip, pour, splash, condensation, droplets, wet) | Keep as the **generic fallback** with phrases `liquid`, `water`, `fluid` only; move the rest to `liquid.*` / `surface.wet` below | `test_detect("liquid running down the can")` expects exactly `{"sim.liquid"}`; after the change it yields `{"sim.liquid", "liquid.run_down"}` — update that case |
| `sim.particles` (particles, sparks, confetti, glitter, dust) | Keep with `particles?` only; move sparks/confetti/glitter/dust to `particles.*` | none of the listed tests use these words |
| `sim.smoke_fire` | Keep for `explo…` only; `fire`/`flames` → `fire.flames`, `smoke` → `smoke.plume` | none listed |
| `sim.cloth` | Keep for `cloth`; flag/curtain/billowing → `cloth.flag` / `foliage.sway`-style tags | none listed |
| `sim.rigid` | Keep; add `rigid.scatter`, `destruct.shatter` | none listed |
| `sim.debris_wind` (leaves, debris, tumbleweeds, blowing …, wind(y)) | Keep (tests assert leaves / tumbleweed → this tag); **also** emit the fine tags `particles.leaves`, `rigid.tumbleweed`; move `wind(y|blown)` to `wind.breeze` | tests use `in`, so extra tags pass; but a prompt "windy day" will now yield `wind.breeze`, not `sim.debris_wind` — no listed test covers it |
| `sim.rolling` | Keep; alias of `motion.roll` + `motion.drop` (bounce) | `test_physics_asks_are_detected("ball bouncing")` still passes |
| `sim.tyre_contact` | Keep; provided by `realism/tyre_contact`. Because realism blocks are not director-selectable, `Catalog.capabilities()` must count **realism blocks whose `appliesWhen` matches the profile** as providers, or an ask for tyre squish is wrongly reported unsupported | new test: capabilities(profile with wheels) ⊇ {`sim.tyre_contact`} |

### 4.2 New tags

| Tag | Phrases (regex fragments) | Note when unsupported |
|---|---|---|
| `wind.breeze` | `wind(?:y\|blown)?`, `breez(?:e\|y)`, `gust(?:s\|y)?` | "Wind isn't available yet, so the air is still." |
| `wind.strong` | `storm(?:y)?`, `gale`, `hurricane`, `strong wind` | "Strong wind isn't available yet." |
| `surface.wet` | `wet`, `after (?:the )?rain`, `puddles?`, `soaked` | "Wet surfaces aren't available yet, so everything is dry." |
| `surface.frost` | `frost(?:y\|ed)?`, `icy`, `frozen` | "Frost isn't available yet." |
| `liquid.droplets` | `droplets?`, `dew(?:y)?`, `water beads?`, `beading` | "Water droplets aren't available yet." |
| `liquid.run_down` | `running down`, `run(?:s)? down`, `dripping down`, `trickl(?:e\|es\|ing)`, `rivulets?` | "Water running down surfaces isn't available yet." |
| `liquid.condensation` | `condensation`, `ice[- ]cold`, `sweating (?:can\|bottle\|glass)`, `chilled` | "Condensation isn't available yet, so the drink looks dry." |
| `liquid.pour` | `pour(?:s\|ing)?`, `being poured` | "Liquid pours aren't available yet." |
| `liquid.splash` | `splash(?:es\|ing)?`, `dropped into (?:water\|milk\|liquid)`, `milk crown`, `crown splash` | "Splashes aren't available yet." |
| `liquid.swirl` | `liquid (?:swirl\|ribbon\|wave)`, `wave of (?:juice\|water\|milk)` | "Liquid swirls aren't available yet." |
| `liquid.viscous` | `honey`, `caramel`, `chocolate (?:pour\|drip)`, `syrup`, `paint (?:pour\|drip)` | "Thick liquid pours aren't available yet." |
| `liquid.ink` | `ink (?:in\|into) water`, `ink cloud`, `ink drop` | "Ink-in-water isn't available yet." |
| `liquid.spray` | `spray(?:s\|ing)?`, `mist(?:er)?`, `sprinkler`, `perfume spray`, `hose` | "Sprays aren't available yet." |
| `particles.leaves` | `(?:falling\|blowing\|autumn) leaves`, `leaves (?:fall\|falling\|blowing\|flying)` | "Falling leaves aren't available yet." |
| `particles.petals` | `petals?`, `cherry blossoms?` | "Falling petals aren't available yet." |
| `particles.dust_motes` | `dust (?:motes\|particles)`, `floating dust`, `specks` | "Floating dust isn't available yet." |
| `particles.blowing_debris` | `sand(?:storm)?`, `blowing (?:sand\|dust\|paper)`, `ash(?:es)? falling` | "Blowing sand and debris aren't available yet." |
| `particles.confetti` | `confetti`, `streamers` | "Confetti isn't available yet." |
| `particles.glitter` | `glitter(?:y\|ing)?`, `sparkl(?:e\|es\|ing\|y)` | "Glitter isn't available yet." |
| `particles.sparks` | `sparks?`, `welding`, `grinder` | "Sparks aren't available yet." |
| `particles.embers` | `embers?`, `fireflies`, `glowing particles` | "Embers aren't available yet." |
| `particles.bubbles` | `bubbl(?:e\|es\|y\|ing)`, `fizz(?:y\|ing)?`, `carbonat(?:ed\|ion)` | "Bubbles aren't available yet." |
| `particles.powder` | `powder (?:burst\|explosion)`, `holi`, `colou?r powder` | "Powder bursts aren't available yet." |
| `rigid.tumbleweed` | `tumbleweeds?` | "Tumbleweeds aren't available yet." |
| `rigid.scatter` | `(?:beans\|candies\|coins\|pills\|gems\|ice cubes) (?:falling\|raining\|scatter(?:ing)?\|pouring)`, `raining (?:down )?(?:beans\|coins\|candies)` | "Falling and scattering pieces aren't available yet." |
| `rigid.float_debris` | `floating (?:debris\|rocks\|pieces)`, `asteroids?` | "Floating debris isn't available yet." |
| `destruct.shatter` | `shatter(?:s\|ing\|ed)?`, `smash(?:es\|ing)?`, `breaks? through`, `burst(?:s)? through` | "Shattering and break-throughs aren't available yet." |
| `cloth.drape_reveal` | `unveil(?:s\|ing)?`, `(?:sheet\|cover\|cloth) (?:pulled\|comes) off`, `drape reveal` | "Cloth-unveil reveals aren't available yet." |
| `cloth.flag` | `flags?`, `banners?` | "Flags and banners aren't available yet." |
| `cloth.ribbon` | `silk`, `ribbons?`, `flowing fabric` | "Flowing silk and ribbons aren't available yet." |
| `soft.jiggle` | `jiggl(?:e\|y\|ing)`, `wobbl(?:e\|y\|ing)`, `jelly` | "Jiggle effects aren't available yet." |
| `smoke.plume` | `smok(?:e\|y\|ing)` | "Smoke isn't available yet, so it was left out." |
| `smoke.steam` | `steam(?:ing\|y)?`, `hot (?:coffee\|drink\|tea)` | "Steam isn't available yet." |
| `smoke.dry_ice` | `dry ice`, `low fog`, `fog (?:rolling\|pouring)` | "Low dry-ice fog isn't available yet." |
| `smoke.interactive` | `(?:drives\|driving\|moves) through (?:the )?smoke` | "Smoke that reacts to the subject isn't available yet." |
| `smoke.coloured` | `colou?red smoke`, `smoke bombs?` | "Coloured smoke isn't available yet." |
| `fire.flames` | `fire`, `flames?`, `burning`, `candles?`, `fireplace`, `campfire` | "Fire isn't available yet, so it was left out." |
| `fire.explosion` | `explo(?:de\|des\|ding\|sion)`, `fireball` | "Explosions aren't available yet." |
| `light.heat_haze` | `heat (?:haze\|shimmer\|distortion)`, `mirage` | "Heat shimmer isn't available yet." |
| `light.caustics` | `caustics?`, `pool light`, `underwater light` | "Water-light patterns aren't available yet." |
| `camera.lens_drops` | `(?:rain\|water) on (?:the )?lens`, `lens (?:drops\|splash)` | "Drops on the lens aren't available yet." |
| `vehicle.exhaust` | `exhaust`, `revv?(?:ing\|s)`, `engine running`, `backfire` | "Exhaust effects aren't available yet." |
| `vehicle.tyre_smoke` | `burnouts?`, `(?:tyre\|tire) smoke`, `drift(?:ing)? smoke` | "Tyre smoke isn't available yet." |
| `vehicle.spray` | `(?:road\|tyre\|tire) spray`, `splash(?:ing)? through puddles` | "Road spray isn't available yet." |
| `vehicle.dust` | `dust (?:cloud\|trail)`, `kick(?:s\|ing)? up dust`, `off[- ]road` | "Dust trails aren't available yet." |
| `vehicle.doors` | `doors? open(?:s\|ing)?`, `(?:hood\|bonnet\|trunk) open` | "Opening doors or panels isn't available yet." |
| `motion.drop` | `drops? (?:in\|down\|onto)`, `falls? (?:in\|onto\|down)`, `falling` | "Drop-in animations aren't available yet." |
| `motion.roll` | `roll(?:s\|ing)? (?:in\|across\|down\|away\|over)` | "Rolling motion isn't available yet." |
| `motion.topple` | `topple(?:s\|ing)?`, `tips? over`, `falls? over` | "Toppling isn't available yet." |
| `motion.tumble` | `toss(?:ed\|es)?`, `thrown`, `tumbl(?:e\|es\|ing)`, `flips? in the air` | "Toss-and-tumble motion isn't available yet." |
| `motion.float` | `float(?:s\|ing)?`, `levitat(?:e\|es\|ing)`, `zero[- ]?g(?:ravity)?`, `anti[- ]?gravity`, `hover(?:s\|ing)?` | "Floating motion isn't available yet." |
| `secondary.mechanism` | `tick(?:s\|ing)`, `hands? moving`, `(?:fan\|propeller\|gears?) (?:spin\|spinning\|turning)` | "Moving mechanisms aren't available yet." |
| `contact.tyre` (block-only) | — | — |
| `contact.ground`, `contact.soft`, `secondary.follow_through`, `foliage.sway`, `vehicle.suspension` (block-only, realism) | — | — |

**Phrase collisions to watch** (write tests for each): "rolling fog" must not trigger
`motion.roll` (phrase requires `in|across|down|away|over`); "drift" is already `motion.drive` (keep
"drift smoke" for tyre smoke); "falling" alone → `motion.drop` could misfire on "falling leaves"
(add a negative look-ahead or let both fire — reporting an extra unsupported ask is safer than
dropping one); "smoky" moods ("smoky jazz bar look") may be a grade ask — acceptable false positive
because the note is honest; "sparkle" as a mood word → `particles.glitter`.

---

## 5. Checker validation (spec §4.6 style)

Script-level, pure Python, milliseconds. Codes are proposals.

| Code | Severity | Rule |
|---|---|---|
| `realism_applied` | repaired | resolve every realism block whose `appliesWhen` matches; write to `realism[]` with reason |
| `realism_skipped_low_confidence` | info | a realism block's profile fact exists but is low confidence (e.g. `wheels[].confidence == low` ⇒ `suspension` skipped, `tyre_contact` flatten-only) |
| `wind_missing` | repaired | add `wind` with the world's `windDefault` (calm) |
| `wind_param_on_effect` | error | any effect/sim param named like a wind direction/speed (only `wind` owns wind) |
| `coupled_added` | repaired | add each `couplings` block of a present block (rain ⇒ wet_surface, droplets …) |
| `coupling_removed` | error | the script removes a coupled block while its parent is present |
| `effect_needs_world` | error | `requiresWorld` unmet (tumbleweed on a studio cyc, rain indoors, spray on a dry world) |
| `effect_needs_profile` | error → `unsupported` | `requiresProfile` unmet (`roll` without `rollAxis`; `runners` without up-facing samples; `condensation` without a glass/metal zone) — the ask is moved to `unsupported` with its note, never dropped |
| `effect_needs_source` | error | `runners` with no water source; `steam`/`spray`/`sparks` with no emitter point or marker |
| `exclusive_effects` | error | `excludes` pairs (rain + snow, unless a future `sleet`) |
| `sim_budget` | error | > 1 heavy `sim` per clip, or total `costWeight` over the tier's budget (budget numbers come from spec §4.7 cost logging) |
| `sim_window` | repaired | `startS/endS` clamped to the clip; bake range = union of shots that see it + pre-roll (smoke/cloth 1–3 s, rigid 0.5 s; eng) |
| `time_scale_weather` | error | weather effects (rain, snow, fog, wind) with time scale ≠ 1.0 |
| `time_scale_range` | repaired | sim time scale clamped to block range; hero liquids default 0.1–0.2 (METHODS R4) |
| `spawn_in_subject` | error | an emitter volume, drop zone, tumbleweed lane or VDB placement intersects subject bounds + 10% (cheap maths on bounds, like B-04) |
| `path_through_subject` | error | kinematic paths (tumbleweed, toss, debris) sampled at 12 points per shot enter bounds + margin |
| `effect_off_screen` | warning | a requested effect is never inside any shot's frustum while active (the user asked for it; it must be seen) |
| `wheel_strobe` | repaired | drive speed nudged ±3% out of the spoke-strobe band (vehicles.md V-M01) |
| `vehicle_speed_cap` | repaired | `drive.speedKmh` capped by world length and camera caps (T3-14: arc ≤ 80 °/s) |
| `surface_state_continuity` | error | wet/frost/snow state differs between shots without a declared change (TIERS T4-01) |
| `wind_implausible` | warning | `dry_ice` with wind > 4 m/s; `flag` with wind < 2 m/s (flag hangs limp: allowed but warn) |

**Compile-probe checks [C]** (new class: run in Blender after compile and bake, before render; fast,
no rendering):

| Check | Pass condition (initial; calibrate first) |
|---|---|
| `tyre_patch_present` | per tyre, evaluated mesh has a flat region at z ≈ 0 of length `patchLenFrac · r ± 20%` and the tyre never dips below z = −1 mm |
| `grounded` | lowest evaluated vertex of subject in [−sinkMm, +1 mm] on every frame of a `ground` placement |
| `no_particles_in_subject` | for every baked particle frame, count of points inside the collider SDF (5.0 `Mesh to SDF Grid` + `Sample Grid` [P]) = 0 (tolerance 0.1%) |
| `sim_stable` | no NaN positions; max speed per frame below 3× the block's expected max; rigid pile kinetic energy decays below ε by the block's end; cloth max edge stretch < 2.5× rest; liquid volume change < 15% over the sim |
| `velocity_present` | every particle/point geometry that moves has a `velocity` attribute; every moving volume has a velocity grid |
| `wind_coherent` | mean displacement direction of wind-driven points within 45° of the wind vector (when speed ≥ 1.5 m/s) |
| `bake_cost` | record bake seconds per block (feeds `physics.bakeCostS`) |

---

## 6. What the harness should measure (spec §9, TIERS §2)

| Item | Method | Measure |
|---|---|---|
| **PH-01 tyre contact visible** | [M] | in low side/rear shots, object-index mask of the wheel + depth: the tyre's lowest silhouette is a straight segment touching the ground of length ≥ 0.25 r in pixels (eng) — plus [V] "Do the tyres look weighed down by the car?" |
| **PH-02 grounded subject** | [M] | TIERS T1-X2 contact shadow detected under the subject; ground-seam darkness ratio ≥ 1.3 (eng) |
| **PH-03 particles not intersecting subject** | [C] + [M] | [C] above; [M] no particle pixels with depth greater than the subject depth inside the subject mask when the particle should be in front (depth-order sanity) |
| **PH-04 sim stable / flicker-free** | [C] + [M] | [C] `sim_stable`; [M] B-03 flicker on the effect's region; volume noise (temporal luminance std inside the volume mask vs a converged reference) |
| **PH-05 motion blur on fast physics** | [M] | streak length of sparks/rain ≈ v × shutter / pixel scale within ±40% |
| **PH-06 wind coherence** | [M] | optical-flow angle of wind-driven elements (leaves, rain slant, smoke) agree within 45° across the frame and across shots |
| **PH-07 requested effect visible** | [M] | the effect's object-index/cryptomatte coverage > 0.5% of frame in ≥ 1 shot, or a [V] yes |
| **PH-08 weather coupling** | [V] | "It is raining: does the subject look wet (droplets, sheen) and does the ground have ripples?" |
| **PH-09 physical plausibility** | [V] | "Do falling/rolling things move with believable weight for their size (not too fast, not floaty)?" — the true-scale / time-scale rule (OT-07/08) |
| **PH-10 vehicle weight** | [V] | "When the car stops or turns, does its body move on its suspension?" |
| **PH-11 cost** | log | bake seconds + GPU seconds per physics block (spec §4.7) |
| **PH-12 unsupported honesty** | eval | recall of physics asks in the eval prompt list: every ask is either delivered (PH-07 passes) or appears in `unsupported` (phase-3 Task 30–31 recall metric) |

Eval prompts to add to `harness/prompts/v1.json` (phase-3 Task 30): "a car parked in the rain",
"leaves blowing past the chair", "a tumbleweed rolls by the truck", "the can drips with
condensation", "liquid running down the can", "the sneaker drops and bounces", "smoke rolls
around the car", "a silk sheet slides off the watch", "sparks fly", "confetti falls on the
sofa", "windy", "ice-cold drink", "burnout" — plus the owner's own phrases from 2026-09-24.
