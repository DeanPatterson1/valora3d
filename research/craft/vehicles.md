# Vehicles: parameterised craft rules

Researched 2026-09-24. Scope: any vehicle-like upload (cars first; bikes and trucks reuse most rules).
Tiers per `docs/superpowers/specs/2026-09-24-director-layer-design.md` §2a. Default target is T3.

**How to read a rule**
- `ID [tier]` then the rule, then `params:` (ranges a block or the checker can use), then `src:`.
- Numbers marked **(src)** are stated by the source. Numbers marked **(eng)** are our translation
  of a qualitative source into scene units. Every (eng) number is a starting range to calibrate
  against golden renders (spec §4.8), not a fact.
- `[F]` = URL fetched and read on 2026-09-24. `[S]` = URL returned by search only (fetch refused or
  not attempted); the quoted fact came from the search result text.
- Units: metres, degrees, seconds, 35 mm-equivalent focal length. `L` = car length, `W` = width,
  `H` = height, all from SubjectProfile bounds.

---

## 1. Lighting: studio and cyc worlds

**V-L01 [T3] Light what the paint sees, not the paint.** Build body lighting from large emissive
planes placed where the camera's reflection rays land. Do not light the body with point or spot
keys (accents excepted, V-L05). Indirect/reflected light is what makes gradient highlights and
controllable reflections.
params: `bodyKeyType = "area|emissive_card"`, `pointKeysOnBody ≤ 0` (accents separate), area
lights `visible_glossy = true`, `visible_camera = false` (eng)
src: https://visualeducation.com/how-to-light-and-photograph-cars/ [F]

**V-L02 [T3] One huge overhead plane is the base.** A single large soft source above the car,
tilted and moved until it reflects cleanly along the styling lines of roof, hood and bootlid.
params: `overhead.length = 1.1–1.5 L`, `overhead.width = 0.9–1.4 W`, `heightAboveRoof = 0.8–2.5 m`,
`tiltTowardCameraDeg = 0–15`, overhead exposure so hood reflection peaks at 0.85–0.95 display
value (below clip) (all eng)
src: https://www.lightmap.co.uk/blog/lighting-for-automotive-rendering/ [F]

**V-L03 [T3] Side strips for the flanks and shoulder line.** Two rectangle lights, one per side,
fill the dark flanks and put a reflection along the side of the body.
params: `strip.length = 0.8–1.3 L`, `strip.aspect ≥ 8:1`, `strip.centerHeight = 0.9–1.3 ×
shoulderHeight`, `distanceFromFlank = 1–3 m`, one strip per visible flank (eng)
src: https://irendering.net/how-to-set-up-automotive-studio-lighting-in-unreal-engine-part-1/ [F]

**V-L04 [T3] Few big planes; more makes it flat.** Too many large rect lights flatten the car.
params: `count(planes with area > 0.25 × side area) ≤ 3` (eng); the rest of the rig is accents
and negative fill
src: https://irendering.net/how-to-set-up-automotive-studio-lighting-in-unreal-engine-part-1/ [F]

**V-L05 [T3] Per-panel accent lights, placed by reflection.** Pro CG car lighting adds one small
light per problem panel: A-pillar, each bumper corner, grille, each wheel, a side panel. Sizes in
the tutorial run 10×10 (A-pillar) to 35×35 (bumper) against a 50×50 main softbox, i.e.
0.2–0.7× the key (src).
params: `accents = 3–10`, `accent.size = 0.2–0.7 × key.size` (src ratio), each accent placed with
the reflection solver below; wheels get their own area light at close distance
src: https://www.lightmap.co.uk/learning/blender-tutorial-02/ [F]

**Reflection solver (compiler maths for V-L02/03/05, eng).** For a target body point `P` with
normal `N` and camera `C`: `d = normalize(P − C)`, `R = d − 2(d·N)N`, light centre
`= P + R·dist`, light faces `−R`. Solve at the shot's mid-frame camera; re-check at start/end so the
highlight does not leave the panel. Targets come from SubjectProfile (needs: shoulder-line
curve, hood centre, A-pillar, wheel centres; see CATALOG-GAPS).

**V-L06 [T3] Darken the lower environment hemisphere.** Multiply the lower half of the HDRI or
environment by ~0.1 so tyres, sills and the lower body read dark and grounded.
params: `envLowerHemisphereGain = 0.05–0.2` (src 0.1), blend over ±5–10° around the horizon (eng)
src: https://www.lightmap.co.uk/learning/blender-tutorial-03/ [F]

**V-L07 [T3] Amplify the sun hotspot for crisp glints.** Boost a weak HDRI sun with a small
round light over the sun position (tutorial: 2×2 size, 3,200 vs HDRI 400, i.e. ~8×).
params: `sunBoost = 4–10×` (src ~8×), `sunBoost.angularSizeDeg = 0.5–1.5` (eng)
src: https://www.lightmap.co.uk/learning/blender-tutorial-03/ [F]

**V-L08 [T3] Glancing angles are the strong reflections.** Panels facing away from camera
(Fresnel) reflect most, and light at a glancing angle gives mirror-like lines. Put the brightest
planes where they hit visible panels at high incidence.
params: `targetIncidenceDeg = 60–85` for flank strips (eng)
src: https://www.lightmap.co.uk/blog/lighting-for-automotive-rendering/ [F]

**V-L09 [T3] Hard lines from tubes.** Fluorescent-tube-like sources produce a hard reflection
line; use them for crisp character lines, soft planes for broad gradients.
params: `tube.aspect ≥ 30:1`, `tube.edgeSoftness = 0–0.1` (eng); max 2 tubes per shot (eng)
src: https://www.lightmap.co.uk/blog/lighting-for-automotive-rendering/ [F]

**V-L10 [T3] Negative fill is half the rig.** Keep a planned black region in what the body
reflects so gradients have a dark end and edges read. On set this is black floppies on the
fill side.
params: `darkReflectionShare = 0.3–0.6` of the reflected hemisphere below 5% of key luminance
(eng); `negFill` cards on the camera-side flank for dark moods
src: http://wanderingdp.com/podcast/wandering-dp-podcast-episode-139-car-lighting/ [F]

**V-L11 [T3] Dark-cyc rim over the roofline.** For black backgrounds, a rim light over the top of
the car from behind, a subtle continuous fill, and a white wall kept for bounce.
params: `rim.azimuthFromCameraDeg = 150–180`, `rim.elevationDeg = 30–60`,
`fillRatio (key:fill) = 4:1–8:1` (eng)
src: https://visualeducation.com/class/professional-car-photography-side-view/ [F]

**V-L12 [T3] Travelling light sweep.** A tube light whose lit segment moves from one end to the
other, placed above the car, so a highlight runs down the body.
params: `sweep.durationS = 1.5–4`, `sweep.direction = front→rear | rear→front`,
`sweep.count ≤ 1 per shot` (eng)
src: https://www.soundstripe.com/blogs/how-to-shoot-a-car-commercial [F]

## 2. Lighting: exterior and night worlds

**V-L13 [T2] Low sun.** Golden hour: sun ~10–12° altitude one hour after sunrise/before sunset;
~3,500 K golden hour, ~2,000 K right at sunrise/sunset, ~5,500 K midday (src).
params: `sun.elevationDeg = 2–15` for warm moods, `sun.cct = 2000–3500 K`; midday 5,500 K only for
hard-light moods
src: https://en.wikipedia.org/wiki/Golden_hour_(photography) [F]

**V-L14 [T2] Avoid hard high sun on paint; side-light the car.** Shoot at golden hour or under
heavy overcast to keep paint highlights tame; angle the car 30–45° to the light to sculpt it.
params: `sunAzimuthToCarAxisDeg = 30–45` (src); overcast world = large dome, no sun disc
src: https://www.photoworkout.com/car-photography-tips/ [F]

**V-L15 [T3] Night means wet ground.** Wet pavement reflects instead of absorbing light, doubling
every practical and lifting the blacks; it also hides flaws in the ground.
params: `ground.wetness = 0.6–1.0`, `puddle.roughness = 0.02–0.1`, `dry.roughness = 0.5–0.8`,
≥ 3 practicals (street lights, signs) in the reflected field (eng)
src: https://picturestoryteller.com/2025/12/02/why-do-filmmakers-always-wet-the-asphalt/ [F]

**V-L16 [T2] Haze for separation.** Haze plus a fan on a night street separates foreground
from background and sells "driving at night in fog".
params: see V-W02
src: https://www.soundstripe.com/blogs/how-to-shoot-a-car-commercial [F]

## 3. Camera

**V-C01 [T3] Focal length by shot.** Front 3/4 hero ~50 mm; side profile 70–100 mm; detail
close-ups 85–135 mm (src).
params: `lensMm: hero34 = 45–70, profile = 70–100, detail = 85–135`
src: https://www.spyne.ai/blogs/car-photography-angles [F]

**V-C02 [T3] Never wide and close on the whole car.** Wider than ~24 mm distorts a full car (the
nose dominates); move back and zoom in instead.
params: checker rule: full-car framing requires `lensMm ≥ 28` unless block is `fpv|rolling_wide`
(eng threshold from src 24 mm)
src: https://tunedrides.com/blog/car-photography-guide/ [F]

**V-C03 [T3] Front 3/4 hero geometry.** Camera 40–45° off the front axis, lens slightly below
hood height; front wheels steered 15–20° toward camera so the rim face shows.
params: `azimuthFromNoseDeg = 40–45`, `cameraHeight = 0.7–1.0 × hoodHeight`,
`frontWheelSteerDeg = 15–20` (toward camera) (all src)
src: https://www.spyne.ai/blogs/car-photography-angles [F]

**V-C04 [T3] Side profile geometry.** 90° to the car, door-handle height, wheels straight.
params: `azimuthDeg = 90 ± 3`, `cameraHeight = doorHandleHeight ≈ 0.45–0.55 H` (eng),
`steerDeg = 0`
src: https://www.spyne.ai/blogs/car-photography-angles [F]

**V-C05 [T3] Low hero and rear stance.** Low front shot: camera on or near the ground, pointing
slightly up; rear angles go lower to emphasise stance.
params: `lowHero.height = 0.15–0.5 m`, `pitchUpDeg = 2–10` (eng)
src: https://tunedrides.com/blog/car-photography-guide/ [F]

**V-C06 [T3] Aperture by motion.** Static hero and details f/2.8–4 for separation; moving shots
(rolling, tracking, fly-by) f/5.6–8 so the whole car stays sharp.
params: `fstop.static = 2.8–4`, `fstop.moving = 5.6–8` (src, apply at true scale)
src: https://www.modmycar.app/blog/how-to-shoot-cinematic-car-video [F]

**V-C07 [T3] Anti-miniature DOF gate.** Shallow focus on a big object reads as a scale model
(the brain associates shallow DOF with close-up small objects; a high angle adds to it). A
full-car frame must hold the whole car in focus.
params: checker: if subject is vehicle-sized (>2.5 m) and fully framed, require computed DOF
≥ 1.1 × subject depth along view; forbid `elevationDeg > 30` with `fstop < 4` (eng)
src: https://en.wikipedia.org/wiki/Miniature_faking [S]

**V-C08 [T2] 180° shutter; wheels must blur to discs.** Shutter = 2× frame rate; at 1/50 wheels
blur into discs and the road streaks. Fast shutters freeze spokes and make pans stutter.
params: Blender `motion_blur_shutter = 0.5` default (180°); `0.5–0.75` for tracking/rolling
shots (eng); never `< 0.35` on a moving car
src: https://www.modmycar.app/blog/how-to-shoot-cinematic-car-video [F]

**V-C09 [T3] Rolling shot recipe.** Car-to-car at 25–40 mph for detail-rich roads, 50–70 mph for
maximum motion; wide lens (author favours 17 mm) from close; shutter 1/20–1/40 in stills.
params: `subjectSpeedKmh = 40–65 | 80–110` (src mph converted), `lensMm = 17–28`,
`cameraOffsetM = 1.5–4`, video shutter `0.5–0.75` (eng: stills shutter is too long for video)
src: https://www.mackeydesigns.com/blog/2018/9/5/how-to-capture-automotive-rolling-shots-10-rules-by-josh-mackey [F]

**V-C10 [T3] Fly-by.** Low roadside angle, focus pre-set on the pass point, wide framing, pan
through and past the car's exit.
params: `height = 0.2–0.6 m`, `panSweepDeg = 60–120`, focus locked at pass point, pan continues
≥ 0.3 s after the car's tail leaves centre (eng)
src: https://www.modmycar.app/blog/how-to-shoot-cinematic-car-video [F]

**V-C11 [T3] Physical camera-car limits.** A real Russian-arm style rig swings at up to 80°/s and
lifts at 1.3 m/s; staying inside these keeps CG arcs believable.
params: checker caps: `arcAngularSpeed ≤ 80 °/s`, `verticalSpeed ≤ 1.3 m/s` for any camera
moving relative to a moving car (src); `≤ 40 °/s` default (eng)
src: https://theasc.com/article/the-tyr-russian-arm/ [F]

**V-C12 [T3] Detail inventory.** Standard car detail shots: engine bay/hood, interior, emblems,
brake calipers, exhaust tips, side mirrors.
params: `detailTargets = [badge, headlight, taillight, caliper, wheel, exhaust, mirror, interior]`;
pick 1–3 per 10 s clip; detail wheel shots `fstop 2.8–4`
src: https://www.drivenfilms.tv/blog/car-videography-how-to-film-cars [F]

**V-C13 [T2] Operator camera = real recorded shake.** Layer captured handheld shakes on the
camera; presets include `INVESTIGATION`, `THE_CLOSEUP`, `THE_WEDDING`, `WALK_TO_THE_STORE`,
`HANDYCAM_RUN`, `OUT_CAR_WINDOW` (read from `shake_data.py`). Shake data is CC0, add-on code GPL-3.
params: `shake.preset ∈ {THE_CLOSEUP, INVESTIGATION, WALK_TO_THE_STORE}` for hero/detail,
`OUT_CAR_WINDOW` for car-mounted; `shake.influence = 0.15–0.6`, `shake.scale = 0.5–1.5` (eng)
src: https://github.com/EatTheFuture/camera_shakify [F]

**V-C14 [T3] Drive-in on a locked camera.** A static camera lets the car drive into frame; the
car carries the motion.
params: `camera.move = static`, car enters from frame edge, stops or passes with ≥ 40% of frame
width travel (eng)
src: https://www.drivenfilms.tv/blog/car-videography-how-to-film-cars [F]

## 4. Subject motion

**V-M01 [T3] Wheels roll, never slide; avoid wagon-wheel strobing.** Wheel angular speed must
match ground speed. Sampled at a frame rate, spokes can look stopped or reversed when the
spoke-passing rate is near a multiple of fps.
params: `ω = v / r_tyre` (hard rule, checker); with `n` spokes, `f = n·ω/2π`; require
`frac(f / fps) ∉ [0.9, 1.1]` and `∉ [0, 0.1]` unless motion blur shutter ≥ 0.5 (eng)
src: https://en.wikipedia.org/wiki/Wagon-wheel_effect [F]

**V-M02 [T4] Body roll and pitch.** Body rolls toward the outside of a turn. Roll gradient: about
4–7°/g for comfort cars, under 2°/g for race cars (src); performance road cars sit between.
params: `rollDeg = gradient × lateralG`, `gradient = 1–3 °/g` sports, `4–7` comfort, `< 2` race;
`lateralG ≤ 0.9` road cars (eng); pitch under braking/launch same order (eng)
src: https://suspensionsecrets.co.uk/calculating-ideal-spring-and-roll-bar-rates/ [S]

**V-M03 [T4] Suspension sells the CG car.** On Fate of the Furious the CG cars needed heavy
suspension and body-roll control, tuned per car type from reference footage; directors mistook
CG foreground cars for practical ones.
params: suspension rig per vehicle class (`classic_soft | luxury | sport`), secondary bounce on
bumps `0.5–1.5 Hz`, `damping ratio 0.3–0.5` (eng)
src: https://www.cartoonbrew.com/vfx/can-pick-real-car-shot-150045.html [F]

## 5. Worlds and atmosphere

**V-W01 [T2] Studio: dark cyc with a white wall kept for bounce.** A black backdrop keeps the rim
defined; a white wall off-camera is used as a large reflector.
params: `studio_cyc.tone = black`, `bounceWall = on`, floor gloss 0.1–0.4 (eng)
src: https://visualeducation.com/class/professional-car-photography-side-view/ [F]

**V-W02 [T2] Atmosphere as depth.** Smoke/haze lightens and desaturates the background while the
foreground stays crisp; shafts only show when backlit toward camera; keep it mostly in the
background.
params: `haze.density` tuned so background (> 15 m) contrast drops 25–50% vs foreground (eng);
at least one light within 30° of the camera's reverse direction when shafts are wanted (eng)
src: https://neiloseman.com/lighting-techniques-5-smoke/ [F]

## 6. Edit: shot list, order, rhythm

**V-E01 [T3] Wide first, then tighter.** Establish location with a wide shot, then cut to
medium or close-up.
params: shot 1 or 2 must be `scale ∈ {LS, FS}`; ≥ 1 of `{CU, ECU}` later
src: https://www.drivenfilms.tv/blog/car-videography-how-to-film-cars [F]

**V-E02 [T3] 15 s car edit template.** Wide establishing → elevated angle → tight nose detail →
fly-by conclusion.
params: see templates below
src: https://www.modmycar.app/blog/how-to-shoot-cinematic-car-video [F]

**V-E03 [T3] Cut rhythm.** Cinematic social ads average 17.9 s, 15.2 shots, 1.2 s per shot
(99-ad sample) (src). The owner's F40 reference (ref05) cuts every ~2.5 s.
params: 10 s clip `shots = 4–7`, `shotLenS = 0.8–3.0`, median `1.4–2.5`; hero/last shot
`≥ 2.0 s` (eng from src)
src: https://arxiv.org/html/2608.24329 [F]

**V-E04 [T3] Motivated cuts.** Most common techniques in that corpus: cut on action 52.2%,
montage 37.4%, cut to beat 22.2%, movement match cut 18.2%.
params: ≥ 1 cut per clip where camera or car motion direction continues across the cut
(flow-direction difference < 45°) (eng); beat-aligned cuts once audio exists
src: https://arxiv.org/html/2608.24329 [F]

**V-E05 [T3] 30° rule.** Consecutive shots of the same subject move the camera ≥ 30° or change
framing; otherwise the cut reads as a jump cut.
params: checker: `|Δazimuth| ≥ 30°` or `scale ratio ≥ 1.5×` between adjacent shots
src: https://en.wikipedia.org/wiki/Jump_cut [F]

**V-E06 [T3] Screen direction.** Keep the camera on one side of the line so a driving car keeps
its left→right or right→left direction across cuts.
params: checker: sign of car screen-space velocity x constant across adjacent moving shots unless
a neutral (head-on/tail-on) shot sits between (eng)
src: https://en.wikipedia.org/wiki/180-degree_rule [F]

## 7. Grade

**V-G01 [T3] Hero separation.** Keep the car 10–20% more vibrant/separated than its surroundings;
tame competing greens and sky saturation; darken the road.
params: `subjectChroma / backgroundChroma = 1.10–1.20`, background saturation `−10 to −25%`,
road luminance `−10 to −20%` (src %; split eng)
src: https://mixinglight.com/color-grading-tutorials/colorist-look-inspiration-car-commercials/ [F]

**V-G02 [T3] No blown paint highlights.** Blown highlights on the curved metal are unacceptable;
use highlight control and luma keys on bonnet and roof.
params: pixels ≥ 0.99 inside car mask `< 0.5%` of mask (eng); AgX view transform (bright colours
roll to white like a camera)
src: https://mixinglight.com/color-grading-tutorials/colorist-look-inspiration-car-commercials/ [F]

**V-G03 [T3] Selective sharpening.** Sharpen headlights, badges, wheels and chrome only.
params: compositor unsharp on `detailMask`, `amount 0.2–0.5`, radius 0.5–1.0 px at 1080p (eng)
src: https://mixinglight.com/color-grading-tutorials/colorist-look-inspiration-car-commercials/ [F]

**V-G04 [T2] Roll highlights, do not clip.** AgX (Blender default since 4.0) handles
over-exposure better than Filmic: bright colours go toward white like real cameras. Not for HDR
output.
params: `view_transform = AgX`, `look ∈ {Base Contrast, Medium High, High}` per mood (eng)
src: https://developer.blender.org/docs/release_notes/4.0/color_management/ [F]

**V-G05 [T3] Halation on lamps at night.** Film halation is an orange halo near bright sources
turning red further out; threshold it to the brightest sources on dark backgrounds.
params: `halation.threshold = top 0.5–2% luminance`, `radius = 0.3–1.2% frame width`,
`hueNear = orange (≈25°)`, `hueFar = red (≈5°)`, `strength 0.1–0.35` (eng)
src: https://blog.dehancer.com/articles/halation/ [F]

---

## Shot templates

**Default 9:16, 10 s (T3), studio or world.** Evidence: V-E01..E05, V-C01..C12.

| # | t (s) | shot | camera block | lens | notes |
|---|---|---|---|---|---|
| 1 | 0–2.0 | hook: low front 3/4, slow push | low_hero_push | 35–50 | subject on screen by 0.5 s; wheels steered 15–20° |
| 2 | 2.0–3.5 | detail: headlight/DRL or badge | macro_slide | 85–135 | f/2.8–4; light sweep optional |
| 3 | 3.5–5.5 | side profile slide or rolling | profile_slide / rolling_track | 70–100 / 17–28 | motion blur 0.5–0.75 if moving |
| 4 | 5.5–7.0 | detail: wheel/caliper or tail light | macro_slide | 85–135 | cut on motion continuing shot 3 |
| 5 | 7.0–10.0 | hero landing: rear or front 3/4, arc then settle | arc_orbit (≤40°) | 50–70 | ends ≥ 1 s camera-still |

**30 s spot (T3, 16:9 or 9:16).** 12–20 shots (V-E03).
1. 0–3 s cold open: 2–3 fast details (0.8–1.2 s each) or the world establishing wide.
2. 3–8 s establishing wide / drive-in on locked camera (V-C14).
3. 8–18 s motion block: rolling track, fly-by, top-down, low chase (1.2–2.5 s each), cuts on action.
4. 18–24 s detail run: 4–6 details (badge, lamp, caliper, interior, exhaust) 0.8–1.5 s each, one light sweep.
5. 24–30 s hero: front 3/4 hero (V-C03) held 2–3 s, then end frame / packshot 2–3 s.
