# Characters and collectibles: parameterised craft rules

Researched 2026-09-24. Scope: rigged or unrigged humanoids, creatures, mascots and collectible
figures. Two modes:
- **Collectible / toy** (static figure, hand scale): shoot like a product (`products.md`) with
  the portrait lighting below. Shallow DOF is fine here because it matches the real scale.
- **Character performance** (rigged, human scale): portrait/film lighting, framing by lens,
  eye-line and motion principles below.

Conventions as in `vehicles.md`: `ID [tier]`, `params:`, one `src:` per rule; **(src)** stated by
source, **(eng)** our translation; `[F]` fetched, `[S]` search-returned only.

---

## 1. Camera

**C-C01 [T3] Lens by framing.** 135 mm+ tight headshot; 85 mm head and shoulders; 50 mm half
body; 35 mm full body; 24 mm and wider for groups with environment. Portrait lenses 85–135 mm.
params: `lensMm: ECU ≥ 135, CU 85–105, MS 50–70, FS 35–50, group 24–35` (src)
src: https://marmoset.co/posts/cinematic-presentation-for-3d-art-in-marmoset-toolbag/ [F]

**C-C02 [T3] Focus the nearest eye.** Put the focal plane on the eye closest to camera.
params: `focus.target = nearestEye` when the SubjectProfile finds eyes (future ingest);
fallback `head centre` (eng)
src: https://marmoset.co/posts/cinematic-presentation-for-3d-art-in-marmoset-toolbag/ [F]

**C-C03 [T2] 180° shutter.** 1/60 at 30 fps, 1/125 at 60 fps.
params: Blender `motion_blur_shutter = 0.5` (src 180°)
src: https://marmoset.co/posts/cinematic-presentation-for-3d-art-in-marmoset-toolbag/ [F]

**C-C04 [T3] Height carries meaning.** Up/down angles convey scale and emotion; establishing
shots stay wide with the subject not filling the frame.
params: `heroic → camera below eye line (−5…−20° pitch up)`, `vulnerable → above (+10…+30°)`,
eye-level default (eng)
src: https://marmoset.co/posts/cinematic-presentation-for-3d-art-in-marmoset-toolbag/ [F]

**C-C05 [T3] Toys may use shallow focus; humans at human scale may not fake it.** Shallow DOF
makes a scene read as small (miniature faking). That helps a toy read as a real hand-scale
object and hurts a human-scale character if overdone at wide framings.
params: collectible `< 0.4 m`: `fstop 1.4–4` allowed at any framing; human-scale full-body shots:
DOF must cover the whole figure (eng)
src: https://en.wikipedia.org/wiki/Miniature_faking [S]

## 2. Lighting

**C-L01 [T2] Key off-axis.** A light in line with the camera flattens the face; place the key
slightly above and to the side.
params: forbid `key.azimuthFromCameraDeg < 10` unless mood = `flat_fashion` (eng)
src: https://www.creativeshrimp.com/character-lighting-techniques.html [F]

**C-L02 [T3] Three-point positions and ratios (as a start, not a formula).** Key 15–45° to the
side and 15–45° above camera; fill opposite, lower than the key, from 1/2 to 1/8 of the key
(2:1 to 8:1); back light behind and above, as bright as the glints need.
params: `key.az 15–45, key.el 15–45, fill.az −(30–70), fill.ratio 2:1–8:1, back.az 150–180,
back.el 30–60` (src for key/ratio; others eng)
src: https://www.3drender.com/light/3point.html [F]

**C-L03 [T3] Kicker/rim needs a reason.** A strong light behind and to the side traces head,
shoulder and jaw and separates the character; it should be motivated by a believable source.
params: `rim.azimuthFromCameraDeg = 120–160`, world block must expose a practical/sky/window in
that direction (checker link world→rim) (eng)
src: https://www.creativeshrimp.com/character-lighting-techniques.html [F]

**C-L04 [T3] Eye light.** A small area light that registers as a glint stops glassy, dead eyes.
params: `eyeLight.size = 0.02–0.05 × headHeight`, near camera axis, low intensity so it adds a
catchlight only (eng)
src: https://www.creativeshrimp.com/character-lighting-techniques.html [F]

**C-L05 [T3] Softness from size and distance.** Large area light close = soft, gradual shadows;
small or distant = crisp contrast; close lights fall off fast from face to chest.
params: `key.size = 0.5–2 × headHeight` beauty, `≤ 0.2` dramatic; `key.distance = 1–3 ×
key.size` for visible falloff (eng)
src: https://www.creativeshrimp.com/character-lighting-techniques.html [F]

**C-L06 [T2] Haze for separation.** Volume scatter adds depth and separates the character.
params: `haze_volume.density` low; background contrast drop 15–35% (eng)
src: https://www.creativeshrimp.com/character-lighting-techniques.html [F]

**C-L07 [T3] Kicker variant.** A kicker can sit on the key's side covering 50–60% of the key's
area, or behind-side as a rim.
params: `kicker.side = key|opposite`, `kicker.coverage = 0.5–0.6 × key` (src)
src: https://www.asc.ohio-state.edu/palazzi.1/key_fill_kick.html [F]

## 3. Motion

**C-M01 [T3] Motion principles.** Anticipation before major actions; follow-through and
overlapping action after stops (hair, cloth, limbs settle later); slow in and slow out.
params: any procedural character motion block: anticipation `0.1–0.3 s` opposite to the action,
settle `0.2–0.6 s` with secondary overshoot `≤ 10%` (eng)
src: https://www.adobe.com/creativecloud/animation/discover/principles-of-animation.html [S]

**C-M02 [T2] Static figures: the camera performs.** An unrigged figure never spins at constant
speed (T1). Use eased partial orbits and a push, as for products.
params: reuse `products.md` P-C03/P-C05; `arc_orbit.sweepDeg = 30–90` (eng)
src: https://renderedgestudio.com/what-is-apple-style-3d-animation/ [F]

## 4. Edit and grade

**C-E01 [T3] Eye-line continuity.** Editors flag misaligned eye gaze across consecutive shots.
params: checker: character facing direction in screen space consistent across cuts (180° rule,
see vehicles V-E06) (eng)
src: https://arxiv.org/html/2608.24329 [F]

**C-G01 [T3] Lens imperfections in moderation.** Presentation tools offer AgX/ACES tone mapping,
film vs digital grain, chromatic aberration, distortion and vignette to simulate optics.
params: `grain = film, 0.02–0.06 intensity`, `CA ≤ 0.5 px at 1080p edges`, `vignette 0.1–0.3`
(eng)
src: https://marmoset.co/posts/cinematic-presentation-for-3d-art-in-marmoset-toolbag/ [F]

---

## Shot templates

**Collectible, 9:16, 10 s (T3).** 1) 0–2.5 s low hero push, rim-lit on dark (85 mm); 2) 2.5–4.5 s
face/eye macro, eye light glint (100–135 mm, shallow); 3) 4.5–7 s eased orbit 45–60° revealing
the silhouette; 4) 7–10 s hero 3/4 on a base, ≥ 1 s still.

**Rigged character, 9:16, 10 s (T3).** 1) FS 35–50 mm establishing in world with haze;
2) MS 50–70 mm action with anticipation; 3) CU 85 mm reaction, nearest eye in focus; 4) hero
low-angle hold. Keep eye-line and facing direction continuous.
