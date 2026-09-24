# Products: parameterised craft rules

Researched 2026-09-24. Scope: hand-scale and tabletop objects (0.02–1 m): electronics, bottles,
cosmetics, watches, shoes, tools, packaging. Collectible characters also borrow from here
(characters.md).

Conventions as in `vehicles.md`: `ID [tier]`, `params:`, one `src:` per rule; **(src)** = stated
by the source, **(eng)** = our translation to scene units; `[F]` fetched, `[S]` search-returned
only. `S` = subject's largest dimension from SubjectProfile.

video-shotcraft cards (Apache-2.0, Remotion/2.5D) are cited for timing/easing only. Their
parameters were tuned on flat UI footage; treat them as starting values for 3D and re-verify
(the cards say so themselves).

---

## 1. Lighting

**P-L01 [T3] Polished surfaces: one big white plane, everything else controlled black.** Fill
the reflection zone with one large soft white plane and let the rest go to black: that gives a
clean white-to-black gradient across curves. Small hard lights give harsh bounded blobs.
params: `keyPlane.size = 1.5–4 S`, `darkReflectionShare = 0.4–0.7` (eng); forbid bare point
lights as key on `metallic ≥ 0.8` materials (eng)
src: https://nightjar.so/blog/how-to-photograph-glossy-and-reflective-products-without-killing-reflections [F]

**P-L02 [T3] Strip + diffusion sets the edge.** A strip box facing a diffusion panel 20–30 cm away
gives a soft strip reflection; move it away for softer, touch the panel for a hard cut-off.
params: area light with gradient-edge texture; `edgeFalloff = 0.05–0.4 × stripWidth`
(eng mapping of the 20–30 cm distance); `strip.aspect = 3:1–8:1` (src 10×36 in ≈ 3.6:1 in P-L08 source)
src: https://petapixel.com/how-to-create-gradients-of-light-product-photography/ [F]

**P-L03 [T2] Size and distance set softness.** The larger the source relative to the product and
the closer it is, the softer; a softbox about product size is the starting point.
params: `key.size = 1.0–3.0 S`, `key.distance = 1.0–3.0 S` (eng around src "about product size")
src: https://productshotai.app/blog/product-photography-lighting/ [F]

**P-L04 [T2] Key position.** Key 15–45° to the side of camera and 15–45° above it; fill from the
opposite side, lower than the key; back light behind and above.
params: `key.azimuthDeg = 15–45`, `key.elevationDeg = 15–45`, `fill.azimuthDeg = −(20–60)`,
`fill.elevation < key.elevation`, `back.azimuthDeg = 150–180`, `back.elevationDeg = 30–60` (src
ranges for key; others eng)
src: https://www.3drender.com/light/3point.html [F]

**P-L05 [T3] Key:fill ratio by mood.** Fill at most half the key (2:1), down to 1/8 (8:1).
params: `keyFill = 2:1` clean/bright, `4:1` premium, `8:1` dramatic dark (src bounds)
src: https://www.3drender.com/light/3point.html [F]

**P-L06 [T3] Two elevated back-corner lights.** Common product setup: one diffused light 45° behind
the product, the other in the opposite corner, both elevated and aimed down.
params: `rimPair.azimuthDeg = ±135`, `elevationDeg = 30–50` (eng), both soft
src: https://www.practicalecommerce.com/product-photography-part-4-angles-and-viewpoints [F]

**P-L07 [T3] Black products get a rim from behind.** Front light loses the edges of black
objects; rim from behind keeps the silhouette.
params: if SubjectProfile mean albedo `< 0.1`, require `rim.strength ≥ 1.5 × key` on edges (eng)
src: https://productshotai.app/blog/product-photography-lighting/ [F]

**P-L08 [T3] Bottles and glass: light what the glass sees.** Tall strip behind diffusion
(20–30 cm) for a gradient edge; black card opposite for a deep dark edge; silver card behind to
light the liquid; label light high and angled down so its reflection falls below frame.
params: `edgeStrip` one side, `negCard` other side, `liquidBacklight` behind (strength
0.5–1.5 × key), `labelLight.elevationDeg = 50–70` (eng)
src: https://foodshot.ai/blog/bottle-photography [F]

**P-L09 [T3] Clear glass: bright field or dark field.** Bright field = lit white background with
black flags both sides for a crisp dark contour. Dark field = dark background with grazing
backlight for bright edges. Add front light only for a specific detail.
params: `glassMode ∈ {bright_field, dark_field}`; auto-pick dark_field when world tone is black
(eng); `frontLight = off` by default for `transmission ≥ 0.8` materials
src: https://nightjar.so/blog/how-to-photograph-glossy-and-reflective-products-without-killing-reflections [F]

**P-L10 [T3] Brushed metal: key across the grain.** Move the key across and along the grain and
keep the angle that shows the finish; even diffusion hides directional texture.
params: requires anisotropy direction from SubjectProfile; `key.azimuthToGrainDeg = 60–90`
(eng)
src: https://nightjar.so/blog/how-to-photograph-glossy-and-reflective-products-without-killing-reflections [F]

**P-L11 [T3] Texture needs side light.** Fabrics and textured surfaces need light from the side
and slightly above so micro-shadows show weave and stitch; flat front light kills it.
params: for `fabric-like` coverage `> 30%`: `key.azimuthFromCameraDeg = 60–100`,
`key.elevationDeg = 10–35` (eng)
src: https://productshotai.app/blog/product-photography-lighting/ [F]

**P-L12 [T3] Reveal by backlight, fill last.** Apple-style reveal: three backlights on the
product's edges (not centre) first, fill faded in only at the final reveal; lights on a linear
track for moving light-lines across surfaces in details.
params: sequence `silhouette (edges only) → edges + partial → full` over 1.5–4 s; `fill` ramps
0 → target in last 25–40% of the shot (eng)
src: https://www.manfrotto.com/global-uk/stories/how-to-shoot-cinematic-tech-videos-like-apple/ [F]

**P-L13 [T3] One sheen sweep, not many.** A 45° highlight band sweeps across the hero once
(115° gradient, peak 0.32 on dark ink, 40–68 f in-out cubic in the card); all light effects in a
film total ≤ 2, because light effects cheapen fastest.
params: `sheen.count ≤ 1 per shot`, `lightEffects.total ≤ 2 per clip`, `sheen.durationS = 0.8–1.2`,
ease in-out cubic; dark subjects/backgrounds only (src)
src: https://github.com/Vincentwei1021/video-shotcraft/blob/main/references/shots/effects/light-play-moves.md [F]

## 2. Camera

**P-C01 [T3] Lenses.** Bottles: ~100 mm full frame, f/11–14 for sharp label, edges and stopper.
Product photographers generally sit at 90–100 mm macro.
params: `lensMm.hero = 50–100`, `lensMm.detail = 85–150`; `fstop` so DOF covers the label plane
(eng); DOF computed at true scale (never normalised to 1 m; spec §4.1)
src: https://foodshot.ai/blog/bottle-photography [F]

**P-C02 [T3] Angle vocabulary.** Low-angle hero (below midline, looking up); eye-level straight;
3/4 at 45°; top-down; top-front hybrid 20–30° down; Dutch 15–45°; symmetrical front; floating;
macro detail.
params: `elevationDeg: lowHero −15…−2, eyeLevel 0, topFront 20–30, topDown 85–90`,
`productYawDeg (3/4) = 45`, `dutchRollDeg = 15–45` (src) with Dutch ≤ 1 shot per clip (eng)
src: https://cybertizemedia.com/blog/product/product-shot-angles/ [F]

**P-C03 [T3] Slow push-in that builds.** 4 s accelerating push (scale 1.00→1.14, ease-in quad,
vignette deepening), released by a hard cut at the peak. Linear speed reads as an ordinary zoom;
more than ~1.2× reads as an ordinary push.
params: `durationS = 3–5`, `distanceReduction = 10–15%`, easing `in_quad`, cut at peak (src
mapped from 2D scale to dolly distance, eng)
src: https://github.com/Vincentwei1021/video-shotcraft/blob/main/references/shots/camera/tension-camera-moves.md [F]

**P-C04 [T3] Pull-back isolation ending.** From close-up, pull back (scale 2.2→0.62 over 110 f,
ease-out cubic) while surroundings fall dark; hold ≥ 40 f at the end.
params: `durationS = 3–4`, distance ×3.5, `easing out_cubic`, end hold `≥ 1.3 s` (src frames at 30 fps)
src: https://github.com/Vincentwei1021/video-shotcraft/blob/main/references/shots/camera/tension-camera-moves.md [F]

**P-C05 [T3] Freeze orbit.** Orbit sweep 0→55°→0 with in-out cubic and ~10 f apex hold; 55° is
the minimum that reads as "seeing the side".
params: `arc_orbit.sweepDeg = 45–90` for products (never 360; that is T1); easing
`in_out_cubic`; optional apex hold 0.3 s (src 55°; range eng)
src: https://github.com/Vincentwei1021/video-shotcraft/blob/main/references/shots/camera/tension-camera-moves.md [F]

**P-C06 [T3] Crash zoom.** 6 f (4–8) ease-in punch to a target filling 60–75% of frame; either 3–6%
overshoot bounce or an impact shake (14 px·e^(−t/1.8 f)); motion blur only on the punch; ≤ 2 per
film; ≥ 30 f wide before, ≥ 45 f on the close-up after.
params: `punchFrames = 4–8`, `targetFill = 0.6–0.75`, `shutterAngleDeg = 200` during punch (src)
src: https://github.com/Vincentwei1021/video-shotcraft/blob/main/references/shots/camera/crash-zoom-punch.md [F]

**P-C07 [T3] Drone dive landing.** Near-vertical overhead → dive → cushion: 82% of travel in the
first 25 f (ease-in cubic), last 18% in 20 f (ease-out quint); motion blur shutter 220°. The
82/18 split matters more than frame counts.
params: `durationS = 3–5`, split `0.82/0.18`, `shutterAngleDeg = 220` (src)
src: https://github.com/Vincentwei1021/video-shotcraft/blob/main/references/shots/camera/space-camera-moves.md [F]

**P-C08 [T3] Crane rise reveal (detail → whole).** Hold 20 f on a detail, rise and pull back over
100 f with one ease-out quad progress driving position and framing together, ≥ 30 f still at the
end. Faster than 80 f loses readability; slower than 130 f drags.
params: `holdS ≈ 0.7`, `riseS = 2.7–4.3`, `easing out_quad` on a single progress parameter (src)
src: https://github.com/Vincentwei1021/video-shotcraft/blob/main/references/shots/opening/crane-rise-reveal.md [F]

**P-C09 [T3] Parallax slider.** A slow lateral move reveals depth; a foreground object close to
the lens makes a small move feel larger. Move predictably, barely noticeably.
params: `slide.distance = 0.1–0.4 S·(lens/50)`, constant speed with short eases, optional
foreground element at 0.1–0.3 of subject distance (eng)
src: https://gvmled.com/every-move-has-a-purpose-video-camera-slider-guide/ [F]

**P-C10 [T3] Layer speed gradient.** Multiplane parallax needs ≥ 2× speed ratio between layers
(card: 0.35 / 0.7 / 1.4) and blur/desaturation anchors on the far layer; ≤ 4 layers.
params: bg/subject/fg apparent speed `0.35 / 0.7 / 1.4` (src), bg desat 0.92, bg blur on
src: https://github.com/Vincentwei1021/video-shotcraft/blob/main/references/shots/camera/depth-layer-moves.md [F]

**P-C11 [T2] Slower than you think; nothing starts or stops abruptly.** Apple-style motion is
slow, physically weighted, bezier-eased; products turning feel heavy.
params: every camera/subject keyframe pair eased (no linear except deliberate searchlight
sweeps); `maxAngularSpeed.subject ≤ 45 °/s` hero shots (eng)
src: https://renderedgestudio.com/what-is-apple-style-3d-animation/ [F]

## 3. Subject motion and effects

**P-M01 [T3] Exploded assembly.** Parts separate along Z, staggered 3 f per part, 14 f ease-out-back
(1.7) each, hover a beat, reassemble in reverse with ease-in 12 f and a 2 f damped landing
shake; ~5 s total; ≤ 2 "big moves" per film.
params: `durationS = 4–6`, `stagger = 0.1 s`, `partTravel = 0.3–1.5 S` along the part's
separation axis (eng), requires parts separated at ingest (T3 when parts exist, else skip)
src: https://github.com/Vincentwei1021/video-shotcraft/blob/main/references/shots/camera/space-camera-moves.md [F]

**P-M02 [T4] Liquid hero at high frame rate.** Beverage work is captured at ~300 fps (60/120
alternatives); four core shots: hero pour (camera arcs low-front to side, or overhead to
oblique), splash, condensation macro (f/8–11, backlit), product opening.
params: `simTimeScale = 0.1–0.2` (≈300 fps into 30 fps), pour camera `arcDeg = 30–90` (eng)
src: https://bestboymedia.com/blog/beverage-commercial-production-los-angeles.html [F]

**P-M03 [T4] Condensation only where it is cold.** Droplets only up to the fill line, never on the
dry shoulder or cap.
params: droplet mask = glass area below liquid level; `density 20–60 /cm²` (eng)
src: https://foodshot.ai/blog/bottle-photography [F]

## 4. Edit

**P-E01 [T3] 15 s product structure.** 4–5 shots: low-angle hero opener → one macro detail →
in-use/context → pour/reveal if relevant → closing hero or floating shot.
params: template below; `shots = 4–5` per 15 s (src), scale to 3–5 per 10 s (eng)
src: https://cybertizemedia.com/blog/product/product-shot-angles/ [F]

**P-E02 [T3] Product on screen in 2 s; end on product.** Hook in the first 2 s, 3–5 distinct
moments of the product in motion, final frame emphasises the product.
params: checker: subject mask `≥ 10% frame` by `t = 0.5 s` (eng stricter than src 2 s); last
shot = hero framing
src: https://bestboymedia.com/blog/ecommerce-product-video-dtc-brand-guide.html [F]

**P-E03 [T3] Packshot budget.** Packshots take 2–5 s of a 30 s commercial.
params: `packshotS = 2–5` per 30 s; `1.5–2.5` per 10 s (eng)
src: https://en.wikipedia.org/wiki/Packshot [S]

**P-E04 [T3] Seam vocabulary.** Six ways to join shots: flash-cut (5 f each side), dark-tunnel
fly-through (push out 8–12 f → dark 4–8 f → in 10–14 f), focus hand-off (blur 0→8 px vs 8→0,
10–16 f window, 2–4 f offset), black title card (6–10 f fades, ≤ 2 per 30 s), whip pan (≥ 20 f
holds, 8 f whip ~1.5 screens), mask-wipe through an element (45 f). One technique per seam.
params: `transition.id ∈ {cut, flash, dark_tunnel, focus_handoff, black_card, whip, mask_wipe}` with
the frame budgets above taken from adjacent shots (src)
src: https://github.com/Vincentwei1021/video-shotcraft/blob/main/references/shots/transition/shot-transitions.md [F]

**P-E05 [T3] Hidden cut.** Hide the cut in 1–3 frames of occlusion: a foreground element wipes
across with heavy blur (14 f, shutter 300°) and the cut sits at full cover; or a warm light leak
(27 f rise, cut at peak, 43 f decay, contrast −45% / brightness +35% at peak).
params: `hiddenCut ∈ {fg_wipe, light_leak}`, ≤ 1 per clip (eng), frame budgets as src
src: https://github.com/Vincentwei1021/video-shotcraft/blob/main/references/shots/transition/transition-hidden-cut.md [F]

**P-E06 [T3] Accelerating beat cuts, once.** Cut intervals halve (16→12→8→6→4 f) on different
framings of the same product, then a ≥ 35 f hold; once per film; needs audio beats.
params: `intervalsF = [16,12,8,6,4]`, `holdAfterF ≥ 35`, `count ≤ 1` (src); disabled until audio
exists (spec §8) or used silent only with an end hold ×1.5 (eng)
src: https://github.com/Vincentwei1021/video-shotcraft/blob/main/references/shots/rhythm/beat-cut-moves.md [F]

**P-E07 [T3] Every move ends in true stillness.** After any camera programme finishes, hold
≥ 30 f truly still; after a heavy hit (crash zoom, slam), hold about double.
params: final shot camera velocity `< 2%` of peak for `≥ 1.0 s` (src 30 f at 30 fps)
src: https://github.com/Vincentwei1021/video-shotcraft/blob/main/references/shots/camera/tension-camera-moves.md [F]

**P-E08 [T3] Mobile safe framing.** Editors flag objects outside mobile safe margins. TikTok: keep
key content 108 px from top, 320 bottom, 60 left, 120 right at 1080×1920; Reels: 1010×1280 box,
220 px from top, 420 from bottom.
params: subject centre and any end-card element inside the intersection of both boxes (src px)
src: https://www.ignitesocialmedia.com/content-creation/what-are-the-safe-zones-for-tiktoks-and-instagram-reels/ [F]

## 5. Grade

**P-G01 [T2] Premium = no harsh shadows, no blown highlights; pure whites/blacks with subtle greys.**
params: subject-mask clipped share `< 0.5%`; background for minimal looks = near-white
(0.9–0.97) or near-black (0.02–0.06) with a subtle gradient (eng)
src: https://renderedgestudio.com/what-is-apple-style-3d-animation/ [F]

**P-G02 [T3] Contrast look by mood.** AgX looks add an S-curve on top of AgX: Medium High Contrast
deepens shadows and saturates mid-tones; High Contrast suits dramatic product shots; Very High
Contrast sparingly.
params: `agxLook: clean → Base/Medium High, dramatic → High, noir → Very High (≤ 1 dice
direction)` (eng)
src: https://blog.cgcookie.com/posts/the-secret-to-rendering-vibrant-colors-with-agx-in-blender-is-the-raw-workflow/ [S]

**P-G03 [T3] Impact bloom.** On a crash-stop frame: blurred bright copy (blur 22 px, brightness
1.8) scales 1→1.3 in 6 f then fades linearly to a 0.22 resting glow; expansion out-cubic, decay
linear (decoupled).
params: compositor glare pulse `attack 6 f out_cubic`, `decay 20–35 f linear`, rest `0.2–0.25`
(src), dark backgrounds only
src: https://github.com/Vincentwei1021/video-shotcraft/blob/main/references/shots/effects/light-play-moves.md [F]

---

## Shot templates

**Default 9:16, 10 s (T3).** Evidence: P-E01, P-E02, P-C01..C08.

| # | t (s) | shot | camera block | lens | lighting |
|---|---|---|---|---|---|
| 1 | 0–2.5 | low-angle hero, slow push (subject visible at 0 s) | low_hero_push | 50–85 | edge-lit reveal → fill fades in (P-L12) |
| 2 | 2.5–4.5 | macro detail on the brightest glossy / textured area | macro_slide | 100–150 | raking light (P-L11) or sheen sweep (P-L13) |
| 3 | 4.5–6.5 | motion moment: orbit 45–90°, exploded view, or pour | arc_orbit / explode / sim | 50–85 | same rig, rim stronger |
| 4 | 6.5–10 | hero/packshot: 3/4 at 45°, settle, ≥ 1 s still | hero_settle | 50–100 | full rig, clean background band for end card |

**30 s spot (T3).** 12–18 shots.
1. 0–2 s hook: fastest, most striking frame (macro glint or crash zoom).
2. 2–8 s reveal: edge-lit silhouette → full reveal (P-L12), crane rise or push.
3. 8–18 s features: 4–6 details (0.8–1.5 s), each a different angle (≥ 30°), one focus hand-off.
4. 18–25 s motion/sim moment: exploded view or pour (T3/T4), or light-sweep sequence.
5. 25–30 s packshot 2–5 s (P-E03), camera settles, end card inside safe zone (P-E08).
