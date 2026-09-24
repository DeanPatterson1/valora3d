# Furniture and interiors: parameterised craft rules

Researched 2026-09-24. Scope: single furniture pieces (chair, sofa, table, lamp, 0.3–3 m) shown
either on a studio set or in a room world. The eval set's lounge chair is the first test subject.

Conventions as in `vehicles.md`: `ID [tier]`, `params:`, one `src:` per rule; **(src)** = stated
by the source, **(eng)** = our translation; `[F]` fetched, `[S]` search-returned only.
`H` = piece height, `S` = largest dimension.

Furniture has two modes. **Studio piece** (T3 product-style): reuse `products.md` lighting and
camera rules, with the overrides below. **In a room** (T2/T3 archviz-style): the room world
carries realism, and the camera behaves like an architectural camera (level, slow, deliberate).

---

## 1. Camera

**F-C01 [T2] Room camera height.** Start at 1.2–1.5 m (roughly chest height, or halfway between
floor and ceiling); go higher where people stand and surfaces matter (kitchens, counter tops).
params: `room.cameraHeightM = 1.2–1.5` (src); `+0.2–0.4` for counters/tables seen from above (eng)
src: https://www.hdrsoft.com/learn/best-height-for-shooting-real-estate-interiors.html [F]

**F-C02 [T3] Verticals stay vertical.** Keep the camera level so wall edges and door frames don't
lean; tilting up or down is what makes them converge. Frame with lens shift, not pitch.
params: `camera.pitchDeg = 0 ± 1` for room shots; compose with Blender `shift_y ∈ [−0.25, 0.25]`
(eng); checker flags pitch > 3° in `interior` worlds unless block is `top_down|low_hero`
src: https://www.hdrsoft.com/learn/best-height-for-shooting-real-estate-interiors.html [F]

**F-C03 [T3] Lens: as long as tells the truth.** 16–24 mm full-frame covers most interiors, but
wider is not better; a true view beats stretched furniture.
params: `room.lensMm = 20–35` (eng: start of src range raised to protect the hero piece);
hero piece in a room `≥ 35`; studio piece `50` (F-C05)
src: https://www.nickdalephotography.com/blog/how-to-photograph-interiors-10-tips-for-better-interior-photos [F]

**F-C04 [T2] Walkthrough eye height and speed.** Architectural walkthroughs hold 1,750–1,800 mm
eye height with slow, consistent motion; no abrupt turns or speed changes.
params: `walk.cameraHeightM = 1.75–1.8` (src) for room-scale moves; `speed ≤ 0.5 m/s`,
`yawRate ≤ 15 °/s` (eng)
src: https://blog.chaos.com/3d-architectural-visualization-walkthrough [F]

**F-C05 [T3] Studio piece: 50 mm, deep focus.** A 50 mm captures furniture properly without a
distracting background; f/10–16 keeps everything in focus.
params: `studio.lensMm = 45–70`, `fstop = 8–16` at true scale (src 50 mm, f/10–16)
src: https://www.perfectretouching.com/blog/furniture-product-photography-shoot-large-product-perfectly [F]

**F-C06 [T3] Coverage: 5–6 angles per piece incl. close-ups.**
params: shot list draws ≥ 3 distinct yaw angles (front 3/4, profile, rear 3/4) plus ≥ 1 detail
per 10 s (eng from src 5–6 per piece)
src: https://www.perfectretouching.com/blog/furniture-product-photography-shoot-large-product-perfectly [F]

**F-C07 [T3] Walkthrough structure.** Exterior/context first, move smoothly between spaces, end on
an atmospheric shot; use panning shots for interior details and orbits for exterior form.
params: `shot1 = establishing wide`, `last = atmospheric hero`, orbit only around the hero piece
(`sweepDeg 20–60`, eng)
src: https://blog.chaos.com/3d-architectural-visualization-walkthrough [F]

**F-C08 [T3] Slider reveal for width and depth.** Slow lateral moves reveal depth; a foreground
object near the lens exaggerates small moves; move predictably.
params: `lateral.distance = 0.3–1.0 m` for room shots, foreground prop (plant, chair back) at
0.3–1.0 m from lens (eng)
src: https://gvmled.com/every-move-has-a-purpose-video-camera-slider-guide/ [F]

## 2. Lighting

**F-L01 [T3] Studio piece: top key, two sides, bounce.** One large overhead softbox for a soft
gradient that shapes the piece, two more softboxes either side, reflectors opposite.
params: `top.size = 1.2–2 S`, `sides = 2 × (0.6–1 S)` at `azimuth ±60–100°`,
`topKey : sides = 2:1–3:1` (eng)
src: https://www.perfectretouching.com/blog/furniture-product-photography-shoot-large-product-perfectly [F]

**F-L02 [T3] Top light is the natural key for furniture.** Large sources to keep shadows and
highlights soft; consistent colour temperature so the upholstery colour is true.
params: one CCT for all studio lights `5000–5600 K` (eng; see F-L05), no mixed CCT in studio
src: https://www.colborlight.com/blogs/articles/furniture-photography-lighting-setup [F]

**F-L03 [T3] Texture: raking side light.** Fabric weave and stitching need light from the side and
slightly above; front light flattens it.
params: detail shots on `fabric-like` or `wood` materials: `key.azimuthFromCameraDeg = 60–100`,
`key.elevationDeg = 10–30` (eng)
src: https://productshotai.app/blog/product-photography-lighting/ [F]

**F-L04 [T3] Light sweeps show materials.** CG furniture spots pass light over fabric or leather so
texture reads on a phone, and sweep light across surfaces to show how finishes shift.
params: `light_sweep.durationS = 2–4`, one sweep per detail shot, grazing elevation 5–20° (eng)
src: https://cgifurniture.com/service/3d-animation-for-social-media/ [F]

**F-L05 [T2] Room daylight colour.** Daylight ~5,500 K midday, ~3,500 K golden hour, ~2,000 K near
sunrise/sunset (src). Warm practicals only when the time of day justifies them.
params: `sun.cct` from time of day; practical lamps `2700–3200 K` (eng) only in blue-hour/evening
directions (F-L07)
src: https://en.wikipedia.org/wiki/Golden_hour_(photography) [F]

**F-L06 [T3] Let shadows live; put the sun on the hero.** Common archviz mistakes: lighting
everything, fearing over-exposure, overusing HDRI skies, lamps on in daytime, forgetting the
exterior. Fixes: clear time of day, intentional over-exposure in simple areas, dappled
foliage light, sunlight placed on the focal point.
params: `sunPatch` must intersect the hero piece's mask in the hero shot (eng); allow window
clipping only in areas with no detail; `gobo = foliage` option
src: https://www.blog.poliigon.com/blog/7-mistakes-in-lighting-archviz [F]

**F-L07 [T3] Blue hour for lamps on.** If lamps should be on, use blue hour so a camera can
plausibly expose inside and outside together.
params: `timeOfDay = blue_hour` when `practicals = on`; exterior sky `cct 9000–12000 K` (eng)
src: https://www.blog.poliigon.com/blog/7-mistakes-in-lighting-archviz [F]

**F-L08 [T3] Low sun for depth.** Low morning/late-afternoon sun gives long shadows, warmth and
depth; higher sun reads neutral.
params: `sun.elevationDeg = 8–25` for hero room shots (eng)
src: https://novedge.com/blogs/design-news/v-ray-tip-interior-daylight-with-v-ray-sun-and-sky [S]

## 3. Subject motion

**F-M01 [T3] Show function, not a spin.** CG furniture spots show a chair rotating, changing
height or stacking; drawers extending; table leaves pulling out; headboards moving.
params: `motion ∈ {mechanism, stack, open_close}` when SubjectProfile finds movable parts
(future ingest); otherwise `static` with camera doing the work (eng)
src: https://cgifurniture.com/service/3d-animation-for-social-media/ [F]

**F-M02 [T3] Mood shifts on one set.** The same set can switch relaxed / formal / playful through
quick lighting and décor changes.
params: `lightingStateChange` at a cut (never mid-shot) between two lighting presets (eng)
src: https://cgifurniture.com/service/3d-animation-for-social-media/ [F]

## 4. Edit and grade

**F-E01 [T3] Pace slower than product/vehicle.** Architectural pieces reward slow, readable moves.
params: 10 s clip `shots = 3–5`, `shotLenS = 1.5–3.5` (eng; faster ad corpus in vehicles V-E03
does not transfer to room shots)
src: https://blog.chaos.com/3d-architectural-visualization-walkthrough [F]

**F-G01 [T3] Hold window detail.** Keep enough highlight detail in windows that the exterior still
connects to the room; use tone-mapping highlight compression.
params: window pixels `≥ 0.99` share `< 30%` of window area; AgX (eng)
src: https://novedge.com/blogs/design-news/v-ray-tip-interior-daylight-with-v-ray-sun-and-sky [S]

---

## Shot templates

**Studio piece, 9:16, 10 s (T3).** 1) 0–2.5 s low 3/4 push on the piece (35–50 mm, level
horizon); 2) 2.5–4.5 s raking detail on fabric/wood with a light sweep (85–100 mm); 3) 4.5–7 s
function moment or profile slide (50–70 mm); 4) 7–10 s hero 3/4, top-key gradient, ≥ 1 s still.

**In a room, 9:16, 10 s (T3).** 1) 0–3 s establishing wide at 1.2–1.5 m, slow lateral slide with
a foreground prop; 2) 3–5.5 s dolly-in toward the piece in a sun patch; 3) 5.5–7.5 s material
detail with raking light; 4) 7.5–10 s atmospheric hero, low sun or blue hour.

**30 s (T3).** Context wide → 2 approach moves → 4–6 details (joinery, fabric, mechanism) →
mood shift (day → blue hour at a cut) → hero 3/4 held 3 s.
