# Catalog gaps: what stops the 6 starter blocks reaching T3

Researched 2026-09-24. Implements spec §2a "Catalog order": catalog growth is ordered by what
moves renders from T2 to T3, per this file.

**Starter blocks today** (`engine/blocks/*/block.json`): `studio_cyc` (world), `softbox_three_point`
(lighting), `low_hero_push` and `arc_orbit` (camera), `static` (motion), `neutral_film` (grade).

**What they can reach.** One world, one generic three-point rig, two camera programmes, a neutral
grade. That supports a clean T2-minus studio clip: multi-shot is possible in the schema, but there
is no detail shot, no reflection-shaped light, no atmosphere, no mood grade, no transition, and
nothing vehicle-specific. Against `TIERS.md` it fails T2-07 (atmosphere), T2-08 (mood grade), and
the T3 items for reflections (T3-06..10), scale variety (T3-03), motivated cuts (T3-17) and
separation (T3-19).

**Ranking method.** Impact = number of T3 checklist items the block unblocks × how many subject
families use it, weighted toward vehicles and products (main customers). Rule IDs refer to
`vehicles.md` (V-), `products.md` (P-), `furniture.md` (F-), `characters.md` (C-). Prior-art
numbers refer to `research/prior-art/PRIOR-ART.md`.

---

## 1. Ranked gap list

| Rank | Block (kind) | What it adds | Rules implemented | TIERS items unblocked | Prior-art seed |
|---|---|---|---|---|---|
| **1** | `reflection_rig` (lighting) | Overhead plane + side strips + 3–10 accents + negative fill, each placed by the reflection solver (`vehicles.md` §1) against SubjectProfile targets. Params: overhead size ×L, strip aspect, accent count, darkShare, keyFill. Replaces three-point for any glossy subject | V-L01–L05, V-L08–L11, P-L01–P-L06, F-L01 | T3-06, T3-07, T3-08, T3-09, T3-10 | #12 cc-blender-skill per-material lighting profiles; #17 BlenderAlchemy lighting-refinement loop; Lightmap tutorials (craft sources) |
| **2** | `sequence` (new `edit` kind) | Per-family shot-list templates (vehicles/products/furniture/characters, 10 s and 30 s), cut-length ranges, hook ≤ 2 s, hero ending, 30° rule, screen direction. The director fills shots from it; the checker enforces it | V-E01–E06, P-E01–E03, P-E07, F-E01, C-E01 | T3-01–T3-05, T3-13, T3-15, T3-16 | #6 video-shotcraft `trailer-grammar-moves`, `montage-rhythm-moves`; #26 Cinemetrics (rhythm priors); #10 E.T. (duration stats, offline only) |
| **3** | `macro_detail` (camera) + ingest detail finder | Long-lens slide/push on a detail target: brightest glossy, emissive lamp, badge, wheel, texture. Needs SubjectProfile detail points. (Spec v1 names it `macro_slide`; not built yet) | V-C01, V-C12, P-C01, P-L11, F-L03, F-C06, C-C01, C-C02 | T3-03, T3-22 | #6 shotcraft `graze-face-tour`; #13 kevinbadi `slow-zoom`; #7 CameraBench `truck`/`dolly` |
| **4** | `mood_grade` family (grade) | Hero separation (subject chroma ×1.10–1.20 over bg via object-index mask), AgX look choice, highlight guard, selective sharpen, halation, film grain; 6 presets per spec v1 | V-G01–G05, P-G01–G03, C-G01 | T2-08, T3-08, T3-19, T3-20, T4-04 | #3 AgX/ACES; #4 spectral_film_lut (own LUTs); render-studio `rain_look.py` compositor (spec §4.3) |
| **5** | `rolling_track` (camera) + `drive` (motion) | Vehicle driving with wheels at ω = v/r (spoke-strobe guard), camera-car tracking (side/lead/tail) and fly-by, speed caps 80 °/s / 1.3 m/s, shutter 0.5–0.75 | V-C08–V-C11, V-C14, V-M01 | T3-11, T3-12, T3-14, T3-17 | #7 CameraBench `side/lead/tail-tracking`; #8 CinemaTraj parametric moves + occlusion; #20 RealEstate10K motion noise |
| **6** | `haze_volume`, `ground_fog` (effect) | Depth-graded atmosphere; background contrast −25–50%; shafts need a backlight | V-W02, V-L16, C-L06 | T2-07, T3 world realism | render-studio `rain_atmosphere.py` (spec §4.3) |
| **7** | Worlds: `night_street` (wet), `rain_courtyard` (generalised), `exterior_sun` (golden/overcast), `interior_daylight` | Wet ground 0.6–1.0 with practicals; low sun 2–15°, CCT by time of day; lower-hemisphere env gain 0.05–0.2 and sun boost; interior sun patch on hero, blue hour for lamps | V-L06, V-L07, V-L13–L15, V-W01, F-L05–F-L08, F-G01 | T2-01, T2-02, T2-07, T3-23 | #1 Poly Haven HDRIs; #2 ambientCG surfaces; #18 Infinigen (offline pool) |
| **8** | Transitions (`edit` kind): `focus_handoff`, `whip`, `hidden_cut`, `flash`, `dark_tunnel`, `black_card` | Frame budgets per seam taken from neighbours; one technique per seam | P-E04, P-E05, V-E04 | T3-17 | #6 shotcraft `shot-transitions`, `transition-hidden-cut` |
| **9** | `handheld_operator` (camera modifier) | Layer captured real shake (Shakify presets, CC0 data) at influence 0.15–0.6 on any camera block. In spec v1 list; not built | V-C13, C-C03 | T2-04 | **New:** Camera Shakify https://github.com/EatTheFuture/camera_shakify (code GPL-3 → re-implement loader; shake data CC0 → can ship). Not in PRIOR-ART.md yet |
| **10** | `light_sweep` (lighting, animated) | A strip whose lit segment or position travels 1.5–4 s over the subject; ≤ 1 per shot, ≤ 2 light effects per clip | V-L12, P-L13, F-L04 | T3-06 (animated), T3-10 | #6 shotcraft `light-play-moves` (sheen sweep); Manfrotto light-on-track (craft source) |
| **11** | `hero_settle` / `pull_back_isolation` (camera) | Landing shot: eased arrival on 3/4 hero, ≥ 1 s true stillness; or pull-back with surroundings falling dark | P-C04, P-E07, V-C03 | T3-13, T3-16 | #6 shotcraft `tension-camera-moves` (D), `logo-shrink-wordmark-lockup` for end-card timing |
| **12** | `crane_rise` + `drone_dive` (camera) | Detail→whole rise (hold 0.7 s, rise 2.7–4.3 s ease-out quad); overhead dive 82/18 travel split with 220° blur | P-C07, P-C08 | T3-03, T3-11 | #6 shotcraft `crane-rise-reveal`, `space-camera-moves`; #13 kevinbadi `crane-shot`; #7 CameraBench `pedestal` |
| **13** | `profile_slide` (camera) | Lateral slide at 90° profile or parallax slide with optional foreground layer; layer speed ratio ≥ 2× | V-C04, P-C09, P-C10, F-C08 | T3-03, T3-04 | #6 shotcraft `depth-layer-moves`; #7 CameraBench `truck` |
| **14** | `edge_reveal` (lighting, animated) | Silhouette → edges → fill ramps in last 25–40% (Apple-style product reveal) | P-L12 | T3-09, T3-15 | Manfrotto (craft source); #6 shotcraft `spotlight-sweep-moves` |
| **15** | `glass_field` (lighting) | Bright-field / dark-field glass modes, bottle edge strip + neg card + liquid backlight + high label light | P-L08, P-L09 | T3-06, T3-09 | #12 cc-blender-skill glass profile |
| **16** | `crash_zoom` (camera) + impact bloom (grade pulse) | 4–8 f punch to 60–75% fill, ≤ 2 per clip, blur only during punch | P-C06, P-G03 | T3-11 variety | #6 shotcraft `crash-zoom-punch`, `light-play-moves` (D) |
| **17** | `portrait_rig` (lighting) | Key 15–45°/15–45°, fill 2:1–8:1, motivated rim/kicker, eye light | C-L01–C-L05, C-L07 | T3-09 | #14 arjun988 lighting skills; #15 prompt packs (vocabulary only) |
| **18** | `interior_camera` constraints (camera modifier) | Level camera, lens shift for framing, 1.2–1.5 m height, lens ≥ 20 mm | F-C01–F-C04 | T3-04 (rooms) | #7 CameraBench `pedestal`/`truck`; #20 RealEstate10K |
| **19** | `explode_assembly` (motion) | Staggered part separation along axes, hover, reassemble; needs parts split at ingest | P-M01 | T3-11 | #6 shotcraft `space-camera-moves` (A) |
| **20** | T4: `suspension` (motion), `rain_on_body`, `condensation`, `liquid_pour` (effect/sim) | Roll gradient × lateral g, bounce 0.5–1.5 Hz; droplets below fill line; 0.1–0.2 sim time scale | V-M02, V-M03, P-M02, P-M03 | T4-02, T4-03 | render-studio rain scene; spec §8 phase-2 sim |

**Top 5 by impact on T3:** `reflection_rig`, `sequence` (edit kind), `macro_detail`, `mood_grade`,
`rolling_track` + `drive`.

---

## 2. Changes needed outside new blocks

**Schema (`valora.scene/1`).**
- Block kinds are `world | lighting | camera | motion | effect | grade` (spec §4.3). T3 needs an
  **`edit` kind** for sequence templates and transitions (ranks 2, 8). Add per-shot
  `transitionIn` and a `purpose` tag (`hook | establish | detail | motion | hero | packshot`) so the
  checker can enforce T3-15/T3-16.
- Lighting blocks need **animation params** (ranks 10, 14): time-varying intensity/position.

**SubjectProfile (ingest, spec §4.1)** must add, or ranks 1, 3, 5 cannot place anything:
- gloss mask share and **reflection targets**: hood/roof centre, shoulder-line curve, A-pillar,
  bumper corners (vehicles); largest glossy face, edges (products);
- **detail points**: emissive parts (lamps), brightest glossy region, small high-curvature
  features (badges), textured regions;
- **wheels**: centres, radius, spoke count (V-M01);
- **eyes** for characters (C-C02); anisotropy direction for brushed metal (P-L10);
- **separable parts** for explode (rank 19).

**Checker (spec §4.6)** gains [S] items from TIERS.md: T3-02, T3-04, T3-05, T3-13, T3-14,
T3-21 (anti-miniature DOF), wheel ω = v/r, full-vehicle lens ≥ 28 mm (V-C02).

## 3. Parameter fixes to the 6 starter blocks

| Block | Change | Rule |
|---|---|---|
| `studio_cyc` | add `envLowerHemisphereGain 0.05–0.2`, `bounceWall on/off`; tone `black` + rim is the T3 car studio | V-L06, V-W01 |
| `softbox_three_point` | express `fillRatio` as key:fill `2:1–8:1`; add `rimAzimuthDeg 120–180`, `rimElevationDeg 30–60`; mark `tierMax = T2` for glossy subjects (not reflection-shaped), T3 for matte | P-L04, P-L05, C-L02 |
| `low_hero_push` | add `easing` (default in-out; `in_quad` for tension push), `pushFrac` default 0.10–0.15; checker: full vehicle frame needs `lensMm ≥ 28` | P-C03, V-C02 |
| `arc_orbit` | add `easing in_out_cubic` and `apexHoldS 0–0.4`; product default sweep 45–90°; vehicles cap by 80 °/s | P-C05, V-C11 |
| `static` | none (valid T3 for drive-ins, V-C14) | — |
| `neutral_film` | add `agxLook` enum and a subject-separation param; keep as the `clean` preset of `mood_grade` | V-G01, V-G04 |

Suggested `tierMax` once fixed: `studio_cyc` T3, `softbox_three_point` T2 (T3 matte),
`low_hero_push` T3, `arc_orbit` T3 (sweep ≤ 90°, eased), `static` T3, `neutral_film` T2.
