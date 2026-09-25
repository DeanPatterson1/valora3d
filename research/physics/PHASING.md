# Physics build order: what lands in which phase

Researched 2026-09-24. Current build order (spec §10): 1 foundations, 2 compiler + first blocks,
**3 director**, **4 variety**, **5 catalog growth**, **6 farm**. Owner leaning (2026-09-24):
subject motion + weather early in phase 5, a dedicated physics/sim phase before the farm, and the
always-on realism defaults (contact patch, contact shadow, suspension settle) as early as possible.
This file agrees with that leaning and adds the evidence and the ranking behind it.

IDs: phenomena from `TAXONOMY.md`, methods from `METHODS.md`, blocks and tags from `BLOCKS.md`.

---

## 1. Ranking method: value × cost

- **Value (1–5)** = how much it moves renders toward T3/T4 (TIERS.md) × how common it is in the
  reference genres (TAXONOMY genre marks + owner refs) × reach (an always-on default applies to
  every qualifying render; a requestable effect only when asked or rolled).
- **Cost (1–5)** = build effort + render/bake cost (METHODS cost class) + new ingest facts it
  needs + failure risk on arbitrary uploads.
- **Score = Value × (6 − Cost)** (max 25). Scores are judgement until the §9a corpus counts
  replace the genre estimates (TAXONOMY §15) and spec §4.7 cost logging replaces the cost guesses.

| Rank | Block / package | IDs | Value | Cost | Score | Why |
|---|---|---|---|---|---|---|
| **1** | `contact_ground` + `ground_conform` | CD-01, CD-07, CD-10 | 5 | 1 | **25** | Every render; its absence is a T1 signature (T1-X2). Mostly compiler plumbing |
| **2** | `tyre_contact` | CD-02 | 4 | 1 | **20** | Owner-requested; every vehicle; stateless GN deformer; ingest already finds wheels |
| **3** | `wind` field | WD-01 | 4 | 1 | **20** | Cheap singleton that makes every later weather/particle/cloth block coherent; avoids a retrofit |
| **4** | Rain package: `rain` + `wet_surface` + `droplets` (+ impacts/ripples) | FL-01..03, FL-06, FL-07, LM-05 | 5 | 2 | **20** | 4 of 11 owner refs carry weather or wet surface state (ref03 fog + snow, ref04 wet grimy paint in snow, ref06 droplets, ref10 rain streaks; the MANIFEST also says ref09 is rainy but its corpus record shows it dry) and the T2 reference is a rain film; code exists in render-studio |
| **5** | `landing_settle` + `drop_settle` | SF-05, RB-01, CD-04 | 4 | 1 | **20** | Every subject motion that stops; P-M01/P-C11 craft rules; kinematic |
| **6** | `suspension` + `wheel_roll` | VD-01..06 | 4 | 2 | **16** | "Suspension sells the CG car" (CB); needs `bodySeparable` ingest |
| **7** | `smoke_plume` (CC0 VDBs) + `steam` | GS-01 (ambient), GS-02 | 4 | 2 | **16** | Owner ask ("smoke moving"); JangaFX CC0 library; steam is a cheap procedural volume |
| **8** | `drive` (with its couplings) | VD-02..06 | 5 | 3 | **15** | 3 of 11 refs drive (ref03, 09, 11); CATALOG-GAPS rank 5; realism blocks from ranks 2/6 make it look right |
| **9** | `foliage_sway` | HF-01..03, SC-09 | 3 | 1 | **15** | Outdoor worlds (golden_field) look like stills without it; ref02/04/05 |
| **10** | Simple subject motions: `roll`, `topple`, `toss_tumble`, `float_drift` | RB-02..04, RB-08 | 3 | 1 | **15** | Owner ask ("an object rolling or falling"); kinematic; big variety gain for products |
| 11 | `glass_caustics` (shadow caustics) | LM-01, LM-07 | 3 | 1 | 15 | Glass/liquid products look fake without them (ref12); one object flag set |
| 12 | `dust_motes` + `ground_fog` | PT-01, GS-04 | 3 | 1 | 15 | Spec v1 effects; atmosphere is T2-07 |
| 13 | `falling_leaves` + `tumbleweed` | PT-02, PT-03 | 3 | 2 | 12 | Owner asks; needs the wind field; leaves need a small GN bake |
| 14 | `snow` (+ accumulation) | PT-04 | 3 | 2 | 12 | ref03, ref04 |
| 15 | `runners` + `condensation` | FL-04, FL-05 | 4 | 3 | 12 | Owner ask ("liquid running down a can"); beverage staple (BBM, FSH); new ingest facts |
| 16 | `rigid_scatter` | RB-05 | 4 | 3 | 12 | ref01 (beans), ref02 (fruit); Bullet → keyframes |
| 17 | Particle pack: `sparks`, `confetti`, `glitter`, `embers`, `bubbles` | PT-06..10 | 3 | 2 | 12 | Shared M-GNS base; each is small once the base exists |
| 18 | `heat_haze` + `exhaust` | LM-02, VD-07..09 | 2 | 1 | 10 | Cheap compositor/volume; car polish |
| 19 | `tyre_spray` / `dust_kick` / `tyre_smoke` | VD-10..12 | 3 | 3 | 9 | Needs `drive`; spray matters for wet-night car films (the GT3 RS rain film) |
| 20 | `dangling_hang` + `soft_rest` | SC-08, SF-02/03, CD-03 | 3 | 3 | 9 | Needs new ingest facts (dangling/soft parts) with confidence |
| 21 | `drape_reveal` | SC-02 | 4 | 4 | 8 | Launch-reveal staple; cloth bake + proxy + failure risk on thin parts |
| 22 | `liquid_pour` / `liquid_splash` | FL-08..10 | 5 | 5 | 5 | Highest wow for products (ref01, ref12) but heavy bakes and manifold problems |
| 23 | `viscous_flow`, `ink_cloud`, `smoke_sim` (interactive) | FL-13/14, GS-01 | 4 | 5 | 4 | Heavy Mantaflow; after the bake stage is proven |
| 24 | Character garments + hair | SC-04, HF-04 | 3 | 5 | 3 | Needs rigged uploads and probably Blender 5.2 GN XPBD (§5) |
| 25 | `shatter` / destruction | DS-01..04 | 2 | 5 | 2 | Prop-only; heavy; brand-risky |

**Top 10 by value × cost:** contact_ground, tyre_contact, wind field, rain package, landing/drop
settle, suspension + wheel_roll, smoke VDB + steam, drive, foliage_sway, simple subject motions.

---

## 2. Recommended phasing

### Phase 3 — Director (now): detect and report, build nothing heavy

- Add every physics capability tag from BLOCKS.md §4 to `engine/director/vocabulary.json` with its
  phrases and plain note (the phase-3 plan already asks for this). Update the one `test_detect`
  case that the split changes ("liquid running down the can").
- Reserve the script keys `wind`, `sims`, `realism` in `valora.scene/1`. The checker rejects
  `sims` until sim blocks exist, exactly as it rejects `audio` today (`RESERVED` in
  `engine/script.py`).
- Add the physics eval prompts (BLOCKS §6 list) to the director eval, scored on PH-12
  (unsupported honesty).

### Phase 3½ — Realism defaults (parallel with phases 3–4; owner: "as early as possible")

They are **not director-selectable**, so they don't touch the director, the rulebook or the dice;
they only need the phase-2 compiler. All stateless, all cheap, no bake.

1. `realism` kind + `appliesWhen` resolution in the checker (`realism_applied` repairs).
2. `contact_ground` + `ground_conform` (CD-01/07/10).
3. `tyre_contact` (CD-02) — ingest adds `wheels[].tyreBand`, `wheels[].separable`, `width`.
4. `landing_settle` (SF-05) and static suspension sag (VD-01 static part) — ingest adds
   `bodySeparable`, `vehicleClass`, `restPose`.
5. `wind` field (calm default) wired into `haze_volume` drift so the field has a consumer from day 1.
6. `glass_caustics` (LM-01 shadow caustics) — one flag set per glass subject.
7. Compile-probe checks `tyre_patch_present`, `grounded` + harness PH-01, PH-02.

### Phase 4 — Variety

- Add dice axes that physics will fill: **weather state** (dry / wet / rain / snow / fog),
  **wind strength** (calm / breeze / windy), **season dressing** (leaves, petals, snow). Until the
  phase-5 blocks land, only the "dry / calm" values are rollable; the axes exist so variety memory
  records them from the start.

### Phase 5 — Catalog growth (physics goes **early** in the phase)

**5a Subject motion** (with the worlds that need them):
`drop_settle`, `float_drift`, `roll`, `topple`, `toss_tumble`, `drive` + dynamic `suspension` +
`wheel_roll` (+ `rolling_track` camera from CATALOG-GAPS rank 5). Ingest: `rollAxis`,
`principalAxes`, `supportPolygon`.

**5b Weather and ambient physics** (port render-studio rain first, spec §10 step 5):
`rain` + `wet_surface` + `droplets` (+ impacts/ripples), `ground_fog`, `dust_motes`, `snow`,
`foliage_sway` (lands with `golden_field`), `falling_leaves`, `tumbleweed`, `steam`,
`smoke_plume` (VDB), `heat_haze`, `exhaust`. All stateless or seconds-long GN bakes that run on the
render machine; no farm needed.

Everything in 5a/5b stays within METHODS R1 (stateless where possible), so preview and final agree
and nothing depends on the bake stage yet.

### Phase 6 — Physics & simulation (NEW, before the farm)

The farm has to be designed around baked caches, so the bake stage must exist and be measured
first.

1. **Pipeline:** add stage **4b BAKE** between checker and render (compile → bake → preview on the
   same bake, METHODS R9). Caches are hashed job assets. Bullet bakes to keyframes.
2. **Ingest:** `collisionProxy` (closed voxel shell), `upFacing` samples, `lowConvexEdges`,
   `container` hints (opening, fill line; markers first), `emitterPoints`, `softParts`,
   `danglingParts` — each with a confidence.
3. **`sim` kind + `sim_hygiene`** (collider, velocity blur, true-scale g, explicit time scale).
4. Order inside the phase (by score): `runners` + `condensation` → `rigid_scatter` → particle
   pack (`sparks`, `confetti`, `glitter`, `embers`, `bubbles`) → `tyre_spray` / `dust_kick` /
   `tyre_smoke` (own VDB library baked once) → `dangling_hang` + `soft_rest` → `drape_reveal` →
   `liquid_pour` / `liquid_splash` (Mantaflow FLIP/APIC) → `viscous_flow`, `ink_cloud`,
   `smoke_sim`.
5. Compile-probe checks `no_particles_in_subject`, `sim_stable`, `velocity_present`,
   `wind_coherent`, `bake_cost`; harness PH-03..PH-11.
6. **Exit gate:** each heavy sim has an owner-graded golden render (spec §4.3 "a block ships only
   with at least one golden render") and a measured bake time.

### Phase 7 — Farm (was phase 6)

Physics adds three requirements: **(a)** bake once on one machine, ship caches to every worker by
hash (METHODS R2); **(b)** Bullet, cloth and Mantaflow bake on the **CPU**, so the farm needs a CPU
bake worker class separate from GPU render workers, or long GPU-idle time is billed; **(c)** cost
per clip splits into bake-seconds and GPU-seconds (spec §4.7 logging).

### Phase 8+ — Later physics

Character garments and hair (SC-04, HF-04) after a Blender 5.2 decision; destruction (DS-*);
FLIP Fluids purchase if Mantaflow liquids fail the owner's grade; articulated parts (VD-15 doors,
SF-06 mechanisms); frost growth, ocean/underwater worlds, powder bursts, interactive smoke at scale.

---

## 3. What the director must do today with asks we can't do yet

Contract (phase-3 plan Task 12, restated for physics):

1. **Detect** every physics ask with the vocabulary phrases (BLOCKS §4), plus any the LLM adds
   (`merge_llm`: the LLM can add asks, never remove them). Marker text counts too
   (`source: "marker:<id>"`).
2. **Never silently drop** it. Put it in `unsupported` as `{ask, capability, note, source}` and
   mirror it in `assumptions`.
3. **Say what the video does instead**, in the note, in plain words. Examples:
   - "Rain isn't available yet, so the video is dry." (existing note)
   - "Water running down surfaces isn't available yet; the can has condensation droplets but they
     don't move." (partial support — condensation exists, runners don't)
   - "Tumbleweeds aren't available yet." (no substitute)
   - "Tyre smoke isn't available yet; the car drives with a clean road."
4. **Never substitute a different physics effect silently.** Picking haze when fog was asked is
   allowed only if the note says so (the existing `atmosphere.fog` note does).
5. **Realism defaults are never reported** — they are not asks. The one exception: the user
   explicitly asks for one and the profile can't support it (e.g. "make the tyres squish" on a
   model where ingest found no wheels) → `unsupported` with "We couldn't find separate wheels on
   this model, so the tyres can't deform."
6. **Profile-blocked asks are unsupported, not errors.** If `roll` exists but the model has no
   roll axis, the ask goes to `unsupported` with a reason ("this shape can't roll convincingly"),
   and the render proceeds.

---

## 4. Risks

| Risk | Mitigation |
|---|---|
| Uploads are non-manifold / huge, so sims explode or leak | Collider proxies only (METHODS R6); `sim_stable` compile probe; fallback = drop the sim and report it in `unsupported` rather than ship a broken frame |
| Heavy bakes blow the per-clip cost | `sim_budget` checker rule; ≤ 1 heavy sim per clip until cost logging says otherwise; prefer VDB/stateless fakes |
| Preview/final mismatch on sims | Same bake for preview and final (METHODS R9) |
| Physics looks toy-like at true scale | Explicit time scale per block (R4); PH-09 VLM question |
| Wind incoherence across blocks | One field; `wind_param_on_effect` error; PH-06 metric |
| Force-field strength ≠ m/s | Calibrate the wind mapping once per consumer and store it in the block (METHODS §2.9) |
| Always-on defaults misfire (a chair's casters read as wheels) | `_axle_pattern` already guards wheels; every realism block needs its profile fact at high confidence, else skipped |

## 5. Decisions for the owner

1. **Blender 5.0 vs 5.2 LTS.** 5.2 LTS adds geometry-nodes hair and cloth dynamics (XPBD, still
   experimental) and has rigid bodies and fluids on the roadmap
   (https://code.blender.org/2026/07/geometry-nodes-physics/ [F]). Staying on 5.0 is fine for
   phases 3½–6 (every method in METHODS.md is 5.0). Upgrading matters only for character cloth and
   hair (phase 8). Recommend: stay on 5.0 now; re-evaluate 5.2 at phase 6's start, since an
   upgrade later means re-baking the golden renders.
2. **Insert phase 6 "Physics & sim" before the farm** (farm becomes phase 7). This matches the
   owner's leaning; the reason is that the farm's design depends on how caches are baked and
   shipped.
3. **FLIP Fluids licence** (paid; addon GPL, engine MIT) — only if Mantaflow liquids fail the
   owner's grade in phase 6.
