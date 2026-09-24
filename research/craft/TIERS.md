# Quality tiers T1–T4: observable definitions and grading checklist

Researched 2026-09-24. Implements spec §2a ("Observable T1–T4 definitions and a per-tier grading
checklist live in `research/craft/TIERS.md`. The eval harness (§9) scores every render against
it."). Craft evidence for each threshold lives in the four subject rulebooks
(`vehicles.md`, `products.md`, `furniture.md`, `characters.md`); rule IDs are cited inline.

**Tiers are cumulative.** A render is T3 only if it passes every T2 and T3 item. T1 is not a
target; its items are *failure signatures*.

**Thresholds are initial.** Per spec §4.8 and the calibrate-before-you-model rule, every numeric
threshold below is a starting value. Before any item gates a render, measure it on the known-good
set (owner refs + golden renders) and on known-bad T1 renders, and move the threshold so it
separates them. Until then items report, not block.

---

## 1. Observable definitions

| Dimension | T1 Basic | T2 Cinematic | T3 Professional ad (default target) | T4 Film/VFX |
|---|---|---|---|---|
| **Set-ups / shots** | 1 shot | 1–2 shots, one world | ≥ 3 distinct set-ups per 10 s (typ. 4–6); ≥ 2 shot scales incl. a detail | T3 + coverage that cuts together like one physical shoot |
| **Light on reflective surfaces** | uniform; highlights are blobs or absent | motivated key; environment visible in reflections | shaped: long continuous gradient highlights following form lines, planned dark regions (negative fill), no clipped blobs; glass edge-defined | per-panel control; physically consistent between shots |
| **Camera motion** | constant-speed rotation of subject or camera (turntable) | operator feel: eased moves, real micro-shake, motivated paths | motion with intent: one dominant move per shot (push, arc, rise, slide, track), eased, ends still on the hero; moves chosen per shot purpose | physically plausible rigs (speed caps), vehicle dynamics, lens breathing |
| **Cut rhythm** | none | none or one cut | 0.8–3.5 s shots, ≥ 1 motivated cut (action/match/beat), 30° rule respected, hook ≤ 2 s, hero ending | edited to music; match cuts across set-ups |
| **Grade** | none / neutral | one mood grade (palette + contrast) | finished: subject separated from background, no clipped speculars, consistent across shots, selective finishing (halation/sharpen) | film-grade pipeline (print emulation, grain structure), shot-matched |
| **DOF** | none or everything sharp | focus on subject, some background falloff | scale-correct: shallow on details, whole-subject sharp on full vehicle frames (anti-miniature), racks as intent | optical: breathing, cat's-eye bokeh |
| **Atmosphere** | none | present (haze, rain, fog, dust) | present and depth-graded: background lower contrast than foreground | simulated interaction (rain on body, dust kicked up) |
| **Continuity** | n/a | n/a | lighting direction, time of day and wetness consistent across shots; screen direction held | full continuity incl. surface state across shots |

Reference anchors: T2 = the Porsche GT3 RS rain film (spec §2a). T3 = owner refs ref05 (F40,
5 shots in 12.5 s, ~2.5 s cadence) and ref10 (Rolex macro, surface perfection);
`assets-in/refs/MANIFEST.md`.

---

## 2. Grading checklist

Method tags: **[S]** script-level (checker, before render, from the `valora.scene/1` JSON and
SubjectProfile); **[M]** frame metric (needs object-index + depth passes, spec §4.8);
**[V]** VLM critic question on sampled frames (answer yes/no with frame ids). Every [V] item must
be validated against owner grades before use (spec §9).

Masks: `subj` = subject object-index mask; `bg` = everything else; `gloss` = subj pixels on
materials with metallic ≥ 0.5 or roughness ≤ 0.3 (SubjectProfile material classes).

### 2.0 Baseline defects (all tiers; from spec §1, §4.8)
- **B-01 [M]** No black/empty frame: frame mean luminance > 0.02 and subj coverage > 0 on every frame.
- **B-02 [M]** Clipping: frame share of pixels ≥ 0.99 < 2%, ≤ 0.01 < 5% (except intentional black
  cards / black cyc: bg excluded when world tone = black).
- **B-03 [M]** Flicker: frame-to-frame mean-luminance jump < 3% beyond what the shot's optical flow
  explains, excluding cut frames.
- **B-04 [S]** Camera outside subject bounds + 10%; subject in frame at 12 samples per shot.
- **B-05 [M]** Subject coverage: subj mask ≥ 25% of frame along its dominant screen axis.

### 2.1 T1 failure signatures (any hit caps the render at T1)
- **T1-X1 [S]** Single shot whose only motion is a constant-angular-velocity rotation (camera or
  subject) sweeping > 180°. (`products.md` P-C05: never 360.)
- **T1-X2 [M]** bg is uniform: bg luminance std < 0.02 and no ground contact shadow detected
  under the subject.
- **T1-X3 [S]** Lighting is one static preset with key:fill < 1.5:1 and no rim (flat).

### 2.2 T2 checklist
- **T2-01 [S]** World block has ground or environment (`hasGround` or env with non-uniform
  radiance); subject grounded (lowest point at z = 0, spec §4.6).
- **T2-02 [M]** Environment visible in reflections: gloss-mask luminance std ≥ 0.08 (not a flat
  grey reflection).
- **T2-03 [S]** Every camera keyframe pair eased (Bezier/ease in-out); no linear interpolation
  except blocks declaring `linearByDesign` (searchlight sweeps). (P-C11)
- **T2-04 [S]** Operator feel: either a real recorded shake layer (Shakify CC0 data, influence
  0.15–0.6) or a motivated path (push/arc/rise) on every shot. (V-C13)
- **T2-05 [S]** Motion blur on, shutter 0.5 (180°) ± 0.25. (V-C08, C-C03)
- **T2-06 [M]** Focus on subject: Laplacian variance inside subj ≥ 1.5× bg on shots whose script
  fstop ≤ 5.6.
- **T2-07 [S+M]** Atmosphere present: an effect block (haze/fog/rain/dust) or a world with
  built-in volume; [M] bg local contrast at depth > 70th percentile ≤ 0.8× that at depth < 30th.
  (V-W02)
- **T2-08 [M]** Mood grade present: grade is not identity; per-clip mean saturation or hue
  distribution differs from the ungraded render by ΔE(mean) ≥ 3, or AgX look ≠ None.
- **T2-09 [V]** "Does this look like one real place photographed with a real camera?"

### 2.3 T3 checklist
**Set-ups and coverage**
- **T3-01 [M]** Shot count via cut detection (run ffmpeg scene score at both 0.12 and 0.3, union,
  then verify each cut against the script's cut times): 10 s clip has 3–7 shots (pilot notes §1).
  Script-generated renders can read cut times from the script directly [S].
- **T3-02 [S]** Shot lengths: median 1.0–3.0 s; none < 0.5 s unless inside a `beat_cut` block;
  last shot ≥ 1.5 s. (V-E03: ad corpus mean 1.2 s; ref05 ~2.5 s)
- **T3-03 [S+M]** Scale variety: ≥ 2 distinct shot scales (LS/FS/MS/CS/ECS, MovieShots class
  names) and ≥ 1 detail shot where subj mask exceeds frame bounds or covers ≥ 60% of frame.
- **T3-04 [S]** 30° rule: adjacent shots differ by ≥ 30° camera azimuth about the subject or by
  ≥ 1.5× in subject screen size. (V-E05)
- **T3-05 [S]** Screen direction: a moving subject keeps the sign of its screen-x velocity across
  adjacent shots unless a neutral head-on/tail-on shot intervenes. (V-E06)

**Light shaped for reflections**
- **T3-06 [M]** Highlight form: in gloss mask, threshold at 0.85 luminance; connected components'
  mean elongation (major/minor axis) ≥ 3 for vehicles and ≥ 2 for products (strip-like
  gradients, not blobs). (V-L02, V-L03, P-L02)
- **T3-07 [M]** Planned darks: ≥ 25% of gloss-mask pixels below 0.15 luminance (negative fill is
  present), and ≥ 15% above 0.6 (highlights present). (V-L10, P-L01)
- **T3-08 [M]** No blown speculars on the hero: gloss-mask share ≥ 0.99 < 0.5%. (V-G02, P-G01)
- **T3-09 [M]** Silhouette separation: mean luminance or chroma contrast across the subj mask
  boundary (3 px band in/out) ≥ 0.1 on ≥ 60% of the boundary (rim/edge lighting). (V-L11, P-L07)
- **T3-10 [V]** "Do the reflections on the subject follow its body lines as long smooth
  gradients, with clean dark areas between them?"

**Motion with intent**
- **T3-11 [S]** Each shot declares one dominant move from the CameraBench primitive set (dolly,
  pedestal, truck, pan, tilt, roll, zoom, arc, lead/tail/side/aerial-tracking, static) plus
  optional shake; no shot mixes > 2 primitives.
- **T3-12 [M]** Smoothness: optical-flow magnitude over a shot has no frame-to-frame jump > 25%
  of its range except at cuts or declared impacts (crash zoom).
- **T3-13 [S]** Ending: final 1.0 s camera speed < 2% of the shot's peak ("true stillness ≥ 30 f").
  (P-E07)
- **T3-14 [S]** Physical caps: arc ≤ 80 °/s, vertical ≤ 1.3 m/s relative to a moving vehicle;
  wheels ω = v/r. (V-C11, V-M01)

**Edit rhythm and structure**
- **T3-15 [M]** Hook: subj coverage ≥ 10% of frame by 0.5 s; first frame not black. (P-E02)
- **T3-16 [S]** Last shot is a hero framing (full subject visible, 3/4 or profile, ≥ 1.5 s).
- **T3-17 [M]** ≥ 1 motivated cut: across a cut, the dominant flow direction differs by < 45°
  (movement match / cut on action), or the cut is a declared transition block. (V-E04)
- **T3-18 [M]** Mobile safe framing (9:16): subject centroid and any text inside the TikTok
  (108/320/60/120 px) ∩ Reels (220/420 px, 1010 wide) safe boxes at 1080×1920. (P-E08)

**Finished grade and DOF**
- **T3-19 [M]** Subject separation: mean chroma(subj) / mean chroma(bg) ≥ 1.10 (target 1.10–1.20),
  or luminance-contrast equivalent for monochrome looks. (V-G01)
- **T3-20 [M]** Grade consistency: per-shot mean Lab of bg within ΔE 10 of the clip mean (unless
  script declares a mood change at a cut, F-M02).
- **T3-21 [S]** Anti-miniature: vehicle-sized subject fully framed ⇒ computed DOF ≥ 1.1× subject
  depth; no `elevation > 30°` with `fstop < 4`. (V-C07)
- **T3-22 [M]** Detail shots shallow: on shots with lens ≥ 85 mm, bg sharpness ≤ 0.5× subj.
- **T3-23 [V]** "Would this pass as a frame from a paid commercial for this product category?"
  (judge against the 12 owner refs; owner grades are ground truth, spec §9).

### 2.4 T4 checklist
- **T4-01 [V]** Continuity: key-light direction, time of day, weather and surface state
  (wet/dry, dust) match across all shots (checker: [S] same world + lighting params across shots
  unless a declared change).
- **T4-02 [S]** Vehicle dynamics: body roll = roll gradient × lateral g (1–3 °/g sports), pitch on
  accel/brake, suspension secondary bounce. (V-M02, V-M03)
- **T4-03 [S]** Simulation touches the subject: rain beading/running, condensation below fill
  line, dust or fluid interacting. (P-M02, P-M03)
- **T4-04 [M]** Lens realism: halation only around the brightest 0.5–2% on dark areas, orange near
  → red far; grain present and temporally varying. (V-G05)
- **T4-05 [V]** Lookdev micro-detail: clearcoat, flake, edge wear, fabric fuzz visible in
  macro shots without looking CG-clean.
- **T4-06 [V]** "Could a viewer tell which shots are CG?" (answer must be no on ≥ 90% of shots).

---

## 3. Scoring

- Per item: pass / fail / not-applicable (e.g. T3-06 n/a if the subject has no gloss material).
- Tier reached = highest tier whose items all pass, with at most **one** [V] failure allowed per
  tier while the VLM judge is still being calibrated.
- Report the failing item IDs; the director's repair loop (spec §4.6) maps [S] failures back to
  params (e.g. T3-04 → move camera azimuth), [M]/[V] failures to a reroll of the offending shot.

## 4. Conflict found with the spec's taste-guide example

Spec §4.4 lists "never more than 3 shots in 10 s" as an example taste rule. The ad evidence
contradicts it: the 99-ad cinematic corpus averages 1.2 s per shot (vehicles V-E03), and the
owner's T3 reference ref05 has 5 shots in 12.5 s. Recommend replacing it with "3–7 shots per
10 s; slower (3–5) for furniture/rooms, faster (5–7) for vehicles" (T3-01, T3-02).
