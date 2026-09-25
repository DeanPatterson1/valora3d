# Physics & dynamics taxonomy for Valora3D

Researched 2026-09-24 for the director layer (`docs/superpowers/specs/2026-09-24-director-layer-design.md`).
Companion files: `METHODS.md` (how to build each in Blender 5.0), `ASSETS.md` (licensed inputs),
`BLOCKS.md` (catalog additions + capability tags), `PHASING.md` (build order).

**Owner brief (2026-09-24):** "prepare for everything with physics, even niche things like on a car the
tires kind of flatten at the ground contact point, and smoke moving, and leaves flying by, a
tumbleweed rolling by, or an object rolling or falling. Don't just take my ideas — get inspiration
from them so we cover more." Earlier asks: rain, liquid running down a can.

**Why physics matters here.** The owner's 11 unique reference clips show "something moving that
isn't the camera in 9 of 11" and "the common thread is motion and simulation, not surface
imperfection" (`assets-in/refs/MANIFEST.md`). TIERS.md places simulation touching the subject at T4
(T4-02, T4-03) and atmosphere at T2/T3 (T2-07). This taxonomy spreads physics across all three:
some items are T3 hygiene that must happen silently, others are T4 showpieces.

---

## 0. How to read this file

**Columns.**
- **ID**: stable id, reused in METHODS/BLOCKS/PHASING.
- **Wrong looks like**: what a viewer notices when it's missing or broken. This is also what the
  harness should detect.
- **Tier**: the tier at which a viewer *expects* it (T2 cinematic, T3 pro ad, T4 film/VFX). An item
  marked T3 that is missing caps the render below T3 when the scene calls for it.
- **Genres**: how often it appears per reference genre. `V` vehicles, `P` products, `F` furniture /
  interiors, `C` characters / collectibles, `S` CG showcase / abstract. `H` common, `M` regular,
  `L` niche, `-` rare / not applicable. **These are estimates** from the owner refs plus the genre
  sources below. The §9a corpus (300–500 clips) should replace them with counts; see §15.
- **Evidence**: source keys (table in §0.1). `ref01`…`ref12` are the owner's clips
  (`assets-in/refs/MANIFEST.md`, `research/corpus/refs/*.json`).
- **Class**: **(a)** always-on realism default: the compiler applies it whenever the scene
  qualifies, with no prompt needed and no director choice. **(b)** requestable effect: only when the
  prompt, a marker, or the dice ask for it. **(c)** both: a subtle always-on baseline plus a
  requestable "hero" version.

**Source marks.** `[F]` = page fetched and read on 2026-09-24. `[S]` = search-result snippet only
(not opened). `[P]` = probed locally in Blender 5.0.1 headless on 2026-09-24. `[R]` = in-repo
evidence. `(eng)` = engineering estimate, not sourced; calibrate before gating on it.

### 0.1 Source keys

| Key | Source | Mark |
|---|---|---|
| REFS | Owner reference set: `assets-in/refs/MANIFEST.md`, `research/corpus/refs/*.json` (`simulation` fields), `research/corpus/PILOT-NOTES.md` | [R] |
| CGF | CGIFurniture, "3D Animation for Product Marketing: 10 Visual Effects" (water, dust/particles, destruction, flame, fog/smoke, cloth, exploded view…) https://cgifurniture.com/blog/visual-effects-in-animation-for-product-marketing/ | [F] |
| GF | GarageFarm, liquid simulation guide https://garagefarm.net/blog/liquid-simulation-in-3d-a-practical-guide-for-artists | [S] |
| ART | Artivoxa, photorealistic liquid pouring CGI in advertising https://www.artivoxa.com/the-best-techniques-for-photorealistic-liquid-pouring-cgi-in-advertising/ | [S] |
| PIX | The Pixel Lab, 3D fluid simulation guide 2026 https://www.thepixellab.net/the-ultimate-guide-to-3d-fluid-simulation | [S] |
| BBM | Best Boy Media, beverage commercial production (300 fps pours, splash, condensation macro), via `research/craft/products.md` P-M02 https://bestboymedia.com/blog/beverage-commercial-production-los-angeles.html | [F] (craft) |
| FSH | Foodshot, bottle photography (condensation only below fill line), via products.md P-M03 https://foodshot.ai/blog/bottle-photography | [F] (craft) |
| CB | Cartoon Brew, CG cars in Fate of the Furious needed suspension/body-roll control, via vehicles.md V-M03 https://www.cartoonbrew.com/vfx/can-pick-real-car-shot-150045.html | [F] (craft) |
| NA | New Atlas, the Blackbird car rig (suspension action tuned to match any car) https://newatlas.com/blackbird-cg-vr-cgi-vfx-car-rig/44022/ | [S] |
| ACT | ActionVFX vehicle dust trails and dirt kick-ups (stock elements for car spots) https://www.actionvfx.com/collections/vehicle-dust-trails-stock-footage | [S] |
| TSB | The Studio Bridge, "What CGI and visual effects really do in commercials" (suspension compression, dust and water kick-up) https://thestudiobridge.com/cgi-visual-effects-commercials/ | [S] |
| FOOH | Fake-out-of-home CGI ads (Maybelline mascara train, Jacquemus rolling bags): https://www.marketingbrew.com/stories/2023/10/26/why-some-brands-are-embracing-fake-out-of-home , https://digiday.com/marketing/what-maybellines-faux-ooh-ads-say-about-the-future-of-advertising-in-augmented-reality/ | [S] |
| NO | Neil Oseman, lighting with smoke (shafts need backlight), via vehicles.md V-W02 https://neiloseman.com/lighting-techniques-5-smoke/ | [F] (craft) |
| TR | Tire Rack, what is a contact patch https://www.tirerack.com/upgrade-garage/what-is-a-tire-contact-patch ; contact length 60–200 mm for car tyres https://www.researchgate.net/publication/337115577_The_calculation_method_of_the_length_of_contact_of_car_tires_with_the_road_surface | [S] |
| RF | Ride frequency: passenger 1.2–1.6 Hz, sporty 1.8–2.0 Hz, Rolls-Royce < 0.8 Hz, rear 10–20% higher https://www.penskeshocks.com/blog/natural-frequency-ride-frequency-cpm-in-race-suspension , https://race.software/ulp_lesson/wheel-rate/ | [S] |
| GK | Gunn & Kinzer raindrop terminal speeds: 1 mm 4.03 m/s, 2 mm 6.49, 3 mm 8.06, 5.8 mm 9.17 https://www.researchgate.net/figure/Terminal-velocity-of-fall-for-raindrops-measurements-by-Gunn-and-Kinzer-40_fig3_257171901 | [S] |
| LH | Locatelli & Hobbs 1974 snowflake fall speeds (aggregates ≈ 1–1.5 m/s) https://www.atmos.albany.edu/facstaff/rfovell/NWP/locatelli-hobbs-1974.pdf | [S] |
| BF | Beaufort land scale (F3 3.4–5.5 m/s leaves in constant motion; F5 5.5–7.9 m/s paper and leaves scattered… ) https://www.spc.noaa.gov/faq/tornado/beaufort.html | [S] |
| FL | Falling plates/leaves: flutter vs tumble transition https://www.researchgate.net/publication/232025616_Analysis_of_transitions_between_fluttering_tumbling_and_steady_descent_of_falling_cards , https://www.science.org/content/article/how-autumn-leaves-get-lift | [S] |
| TW | Tumbleweed aerodynamics: porous wake raises drag and mobility vs solid sphere; tested at 1–6 m/s wind https://www.nature.com/articles/s41467-025-66513-1 | [S] |
| WJ | Splashes/Worthington crown; governed by Weber and Reynolds numbers https://en.wikipedia.org/wiki/Splash_(fluid_mechanics) , https://www.cambridge.org/core/journals/journal-of-fluid-mechanics/article/wrapping-up-a-century-of-splashes/EB163351FCAFD3130B7504585AA4445C | [S] |
| BUB | Air bubble terminal rise in water ≈ 8–33 cm/s by size and purity https://www.researchgate.net/publication/304106872_Experimental_studies_on_the_terminal_velocity_of_air_bubbles_in_water_and_glycerol_aqueous_solution | [S] |
| WW | Wagon-wheel effect, via vehicles.md V-M01 https://en.wikipedia.org/wiki/Wagon-wheel_effect | [F] (craft) |
| SS | Roll gradient 4–7 °/g comfort, < 2 °/g race, via vehicles.md V-M02 https://suspensionsecrets.co.uk/calculating-ideal-spring-and-roll-bar-rates/ | [S] (craft) |

---

## 1. Contact & deformation (CD)

The quietest physics and the most important for T3: it decides whether the subject *weighs*
something. Most items here are always-on.

| ID | Phenomenon | Wrong looks like | Tier | Genres V/P/F/C/S | Evidence | Class |
|---|---|---|---|---|---|---|
| CD-01 | **Contact shadow + contact occlusion** where the subject meets the ground (tight dark line, soft falloff 2–10% of subject height) | subject "floats" or looks pasted; no darkening at the seam | T2 | H/H/H/H/H | TIERS T1-X2 (no contact shadow = T1 signature); vehicles.md: "tyres, sills and the lower body read dark and grounded" [R] | (a) |
| CD-02 | **Tyre contact-patch flattening + sidewall bulge** (flat patch 60–200 mm long on a car tyre; sidewall bulges outward a few mm; tread compresses) | perfectly round tyre touching the floor at one line; car looks like a toy or is "hovering" on its wheels | T3 | H/-/-/L/- | TR [S]; owner brief; REFS: every parked car ref (04, 05, 06) shows loaded tyres | (a) for any SubjectProfile with `wheels` |
| CD-03 | **Cushion / seat / mattress sink** under a resting object or a sitter; wrinkles radiate from the load | cushion is a rigid block; an object placed on a sofa rests on top with a gap | T3 | -/L/H/M/- | CGF (cloth softness), furniture craft F-M01 "show function" [R] | (c): resting-object sink always-on when a soft part is detected; hero "sit-down" requestable |
| CD-04 | **Soft-goods squash on landing** (sneaker, plush, bag, pillow squash 5–15% then recover) | a soft object lands like a steel block; no give | T3 | -/M/M/M/M | CGF cloth; shotcraft landing shake (products.md P-M01) [R] | (c) |
| CD-05 | **Footprints / tyre tracks / impressions** in snow, sand, mud, wet ground, carpet pile | tyres roll over snow with no track; a character walks on sand with no prints | T4 | M/-/-/M/L | REFS ref04 (snowy forest, parked, tracks expected); dynamic paint docs (METHODS) | (c): tracks behind anything that moved on a soft ground are always-on; stylised trails requestable |
| CD-06 | **Slow recovery of an imprint** (memory foam, pressed pillow) | dent snaps back instantly or never | T4 | -/L/M/-/L | eng | (b) |
| CD-07 | **Ground-cover conformity**: tyres and feet sink into grass, gravel, snow crust; blades under the contact bend flat | grass pokes through tyre tread; a bottle lying in grass hovers on blade tips | T3 | H/M/L/M/- | REFS ref02 (bottle lying in grass; the corpus record says the grass is dry), ref04 (grass scatter), ref05 (flower field) | (a) whenever the world has scatter |
| CD-08 | **Press / squeeze interaction** (finger presses button, hand squeezes tube, cap unscrews) | contact without deformation; hand intersects product | T4 | -/M/-/M/- | products.md P-M02 "product opening" shot [R] | (b); needs a character or hand asset |
| CD-09 | **Dent / crumple / crush** (can crushed, box dented, car panel crumple) | stiff object passes through or breaks like glass | T4 | L/L/-/-/M | CGF (destruction shows durability) | (b) |
| CD-10 | **Ground dents under heavy weight** (furniture feet into rug pile, car on turf) | heavy chair legs sit on top of a shaggy rug | T3 | L/-/H/-/- | eng (interior photography staple) | (a) when the world has a soft floor |

## 2. Vehicle dynamics (VD)

Applies whenever ingest reports `wheels` (engine/ingest/measure.py `wheels()`), whatever the
prompt says. vehicles.md V-M01..V-M03 already sets part of this; this table widens it.

| ID | Phenomenon | Wrong looks like | Tier | V/P/F/C/S | Evidence | Class |
|---|---|---|---|---|---|---|
| VD-01 | **Static suspension sag + settle**: body sits slightly into springs; after any stop or drop-in, 1–2 damped bounces at the ride frequency (1.2–1.6 Hz passenger, 1.8–2.0 Hz sporty; rear 10–20% higher) | a car that stops or drops in with zero body motion reads as a rigid toy; or wobbles like jelly | T3 | H/-/-/-/- | CB, NA, TSB, RF [S] | (a) |
| VD-02 | **Wheel spin matched to ground speed** (ω = v/r) with spoke-strobe guard | wheels slide, spin backwards or freeze (wagon-wheel) | T3 | H/-/-/L/- | WW, vehicles.md V-M01 [R]; REFS ref11 wheel spin | (a) whenever the vehicle moves |
| VD-03 | **Steering angle** in turns (front wheels turn into the path; Ackermann) | car curves with straight wheels ("crab") | T3 | H/-/-/-/- | eng | (a) whenever the path curves |
| VD-04 | **Body roll** to the outside of a turn (roll gradient × lateral g: 1–3 °/g sports, 4–7 comfort, < 2 race) | car corners flat like a rail toy | T4 | H/-/-/-/- | SS, CB | (a) when driving on a curve |
| VD-05 | **Pitch: squat on launch, dive on braking** (same order as roll) | a car launches or stops with a level body | T4 | H/-/-/-/- | vehicles.md V-M02 [R] | (a) when speed changes |
| VD-06 | **Road-texture micro-vibration and bump response** (high-frequency body/camera buzz; wheels follow road; body filtered) | glassy, too-smooth motion; or everything shakes including the body shell rigidly | T4 | H/-/-/-/- | CB | (a) at driving speed, low amplitude |
| VD-07 | **Idle shake** (engine running: faint body shimmy, exhaust tip vibration, 10–30 Hz visible only as blur) | "engine on" shot that is perfectly still | T4 | M/-/-/-/- | eng | (b) ("engine running", "revving") |
| VD-08 | **Exhaust heat shimmer** behind tailpipes | exhaust is dead; no life at the rear | T4 | M/-/-/-/- | heat-haze tutorials (METHODS LM-02) | (b); may be default in cold/night worlds with idle |
| VD-09 | **Exhaust vapour / condensation plume** in cold air; backfire flame pop | cold-morning scene with invisible exhaust | T4 | M/-/-/-/- | REFS ref04 (snowy forest) implies cold air | (b) |
| VD-10 | **Tyre smoke** (burnout, drift, launch) | drift with no smoke; smoke that doesn't follow the wheel or wind | T4 | M/-/-/-/- | Blender burnout VDB assets exist (ASSETS); phase-3 vocabulary already maps "burnout" to `motion.drive` | (b) |
| VD-11 | **Dust / gravel kick-up and rooster tail** on unpaved ground; roadside debris swirl behind a passing car | off-road driving leaves no dust; dust not lit by the scene | T4 | H/-/-/-/- | ACT, TSB | (c): subtle dust always-on on dry dirt worlds when driving; hero rooster tail requestable |
| VD-12 | **Wet-road spray and mist trail** off tyres; wake of droplets behind the car | driving on wet road with no spray | T4 | H/-/-/-/- | TSB; wet-night driving is the GT3 RS rain film territory (spec §2a) | (a) when driving + wet world |
| VD-13 | **Brake / exhaust heat glow** (discs glowing orange after hard braking) | race scene with cold brakes (niche) | T4 | L/-/-/-/- | eng | (b) |
| VD-14 | **Tyre sidewall flex under cornering** | (only visible in close-ups at speed) | T4 | L/-/-/-/- | eng | (b), later |
| VD-15 | **Moving-part articulation with mechanical easing** (door swing with gas-strut ease and small bounce at stop; wing/spoiler deploy; hood lift) | doors swing linearly and stop dead | T3 | M/L/L/-/- | P-C11 "nothing starts or stops abruptly" [R] | (b); needs parts at ingest |
| VD-16 | **Airflow visualisation** (smoke wand streamlines over the body, wind-tunnel look) | (stylised) | T3 | L/L/-/-/M | CGF (dust/particles to show airflow) | (b) |

## 3. Rigid bodies (RB)

| ID | Phenomenon | Wrong looks like | Tier | V/P/F/C/S | Evidence | Class |
|---|---|---|---|---|---|---|
| RB-01 | **Drop and bounce / settle** (object drops in, bounces with restitution, settles) | hovers then snaps down; bounces forever; interpenetrates the floor | T3 | L/H/M/M/H | REFS ref02 (falling fruit with collision); products "drop_in" motion in spec §4.3 | (c): any drop-in settles physically (a); dramatic bounce (b) |
| RB-02 | **Roll without slip** (can, bottle, ball, wheel, orange) | slides while spinning at the wrong rate; rolls through obstacles | T3 | L/M/L/L/H | owner brief; FOOH (Jacquemus bags rolling) | (b) |
| RB-03 | **Topple / tip over** (tall object tips, rocks and settles) | pivots about its centre; no rocking settle | T3 | -/M/L/L/M | eng | (b) |
| RB-04 | **Tumble in air** (thrown/falling object spins about its principal axes; tennis-racket wobble on thin objects) | spins about an arbitrary axis at constant speed; no gravity arc | T3 | -/H/L/L/H | REFS ref01 (beans), ref02 | (b) |
| RB-05 | **Scatter / pour of many small pieces** (beans, candies, pills, coins, ice, gems, nuts) raining onto or around the product | pieces intersect each other, all identical rotation, no pile forms | T4 | -/H/L/-/H | REFS ref01 (coffee beans rigid bodies); CGF | (b) |
| RB-06 | **Chain reactions** (dominoes, Newton's cradle, marble runs) | contact order wrong; no energy loss | T4 | -/L/-/-/M | eng | (b) |
| RB-07 | **Floating debris / zero-g drift** (asteroids, pieces orbiting a product) | debris moves in lockstep; collides through subject | T3 | L/M/-/-/H | REFS ref08 (floating debris, subject drift) | (b) |
| RB-08 | **Levitation float** (product hovers with slow bob and drift; "anti-gravity") | constant-speed spin; no micro-drift | T2 | -/H/L/M/H | spec §4.3 `hover_bob` motion; PILOT-NOTES "floating product with falling particles" [R] | (b) (kinematic, not a sim) |
| RB-09 | **Ingredient burst / hero explosion** (layers of a burger, citrus slices, cosmetics ingredients fly out and hang, then reassemble) | pieces fly in straight lines at constant speed | T4 | -/H/-/-/H | CGF (exploded view), products.md P-M01 [R] | (b) |
| RB-10 | **Spin-down wobble** (coin, top, Euler's disk, watch crown) | spins at constant rate then stops dead | T4 | -/L/-/-/L | eng | (b) |
| RB-11 | **Constrained swing** (pendulum, hanging lamp, chains, hinged lid) — see also SF | swing without gravity period (period ≈ 2π√(L/g)) | T3 | L/M/M/L/M | Blender demo "Chains Compound Collision" (ASSETS) | (b) |
| RB-12 | **Collision with the subject** (anything falling near the subject hits it, not passes through it) | debris passes through the car body | T3 | H/H/H/H/H | REFS ref02 "falling fruit with collision" | (a): every sim includes the subject as a collider |

## 4. Destruction (DS)

| ID | Phenomenon | Wrong looks like | Tier | V/P/F/C/S | Evidence | Class |
|---|---|---|---|---|---|---|
| DS-01 | **Glass shatter** (radial cracks, shards with glints, powder) | uniform Voronoi chunks; no small shards | T4 | L/M/L/-/H | CGF (destruction for durability) | (b) |
| DS-02 | **Fracture / crumble** (concrete, rock, chocolate snap, cookie break) | cells too uniform; no dust | T4 | L/M/-/-/H | CGF | (b) |
| DS-03 | **Break-through reveal** (product bursts through a wall, paper, ice block, box) | no debris or dust at the breach | T4 | M/H/-/L/H | CGF; FOOH style | (b) |
| DS-04 | **Tear** (paper, fabric, packaging opened) | clean cut edges; no fibres | T4 | -/M/-/-/M | Blender demo "Space Fabric Cloth Tear" (ASSETS) | (b) |

## 5. Soft body & cloth (SC)

| ID | Phenomenon | Wrong looks like | Tier | V/P/F/C/S | Evidence | Class |
|---|---|---|---|---|---|---|
| SC-01 | **Flag / banner flutter** (travelling waves from the pole; frequency rises with wind) | sine-wave flag; flutter without wind elsewhere | T3 | L/L/-/L/M | BF ("flag waves" at F3) | (b) |
| SC-02 | **Drape reveal** (silk sheet pulled off a car/product; sheet slides over contours) | sheet passes through the subject; lifts like a rigid plane | T4 | H/H/M/L/M | car and product launch staple (eng); CGF cloth | (b) |
| SC-03 | **Static draped fabric** (throw on a sofa, tablecloth, fabric backdrop folds) | stiff, too-regular folds; fabric floating over the surface | T3 | -/M/H/-/M | CGF; furniture craft | (c): drapes are world dressing (a); animated settle (b) |
| SC-04 | **Garment dynamics** (skirt, jacket hem, sleeves on a character) | clothing frozen to the body during motion | T4 | -/-/-/H/- | characters.md C-M01 "follow-through: hair, cloth settle later" [R] | (a) when a rigged character moves and garments are separable; else unsupported |
| SC-05 | **Flowing silk ribbon / fabric swirl** around the product (perfume, cosmetics, fashion) | ribbon moves rigidly or self-intersects | T4 | L/H/-/M/H | CGF cloth; beauty-ad staple (eng) | (b) |
| SC-06 | **Inflated / pressurised soft bodies** (balloons, pillows, air cushions, inflatables) | pillows look solid | T3 | -/L/M/-/M | Blender manual cloth pressure; Blender demo "Internal Air Pressure" (ASSETS) | (c) (pillows in furniture sets always softly deformed) |
| SC-07 | **Jiggle / wobble** (jelly, pudding, gummies, soft toy, slime) | jelly moves as a rigid block | T4 | -/M/-/L/H | Blender demo "Jiggly Pudding" (ASSETS) | (b) |
| SC-08 | **Cables, cords, straps, lanyards, chains** hanging and swinging | straight rigid cable; cable through the subject | T3 | L/H/M/M/L | eng (headphones, cameras, bags, lamps) | (c): hang under gravity always (a) when detected; swing (b) |
| SC-09 | **Curtain billow** (window curtain moved by breeze) | curtains frozen in a "windy" room | T3 | -/-/H/-/- | furniture craft (interior daylight worlds) | (c) in interior worlds with an open window: subtle billow always-on |
| SC-10 | **Paper / page flutter, receipts, flyers** blowing | stiff card motion | T3 | L/L/L/-/L | BF (F5: paper scattered) | (b) (usually via wind debris) |

## 6. Hair, fur, grass & foliage (HF)

| ID | Phenomenon | Wrong looks like | Tier | V/P/F/C/S | Evidence | Class |
|---|---|---|---|---|---|---|
| HF-01 | **Grass / ground-cover sway** (low-frequency gust waves travelling across the field + per-blade flutter) | a frozen field reads as a still photo; all blades moving in sync | T3 | H/M/L/M/L | REFS ref02 (grass), ref04 (grass scatter), ref05 (flower field) | (a) in any world with scatter |
| HF-02 | **Tree / bush sway** (trunk slow, branches faster, leaves flutter; hierarchy) | whole tree rotates as one piece; leaves static | T3 | H/L/M/L/- | REFS ref04 (pine forest) | (a) in outdoor worlds with trees in frame |
| HF-03 | **Flower-field sway and petal shiver** | as HF-01 | T3 | M/M/-/L/- | REFS ref05 | (a) |
| HF-04 | **Character hair dynamics** (follow-through, wind) | helmet hair during a head turn | T4 | -/-/-/H/- | characters.md C-M01 [R] | (a) when a rigged character with hair curves moves; else static |
| HF-05 | **Fur on plush/pets** (wind ripples, secondary jiggle) | fur is a rigid shell | T4 | -/L/-/M/- | eng | (b) |
| HF-06 | **Grass flattening under contact** (see CD-07) and **parting as a car drives through** | tyres drive through grass without pushing it | T4 | M/-/-/L/- | eng | (a) when driving on grass |
| HF-07 | **Feathers / fibre tufts / tassels** | stiff | T4 | -/L/L/L/L | eng | (b) |

## 7. Particles (PT)

| ID | Phenomenon | Wrong looks like | Tier | V/P/F/C/S | Evidence | Class |
|---|---|---|---|---|---|---|
| PT-01 | **Dust motes in light** (sparse floaters visible only in shafts / against dark) | void air; or snow-globe density everywhere | T2 | M/H/H/M/M | spec §4.3 v1 effect `dust_motes`; REFS ref05 "dust visible in the sun reflection" | (c): faint motes whenever a shaft is visible (a) |
| PT-02 | **Falling / wind-blown leaves** (flutter vs tumble, drift sideways; land and slide) | leaves fall straight at constant speed, all same rotation; pass through the car | T3 | M/L/L/L/L | owner brief; REFS PILOT-NOTES "fallen leaves (06)"; FL | (b) (autumn worlds may default on) |
| PT-03 | **Tumbleweed rolling by** (porous ball bouncing and rolling downwind, 1–6 m/s wind band; bounces more than it rolls on rough ground) | rolls smoothly like a ball; moves against the wind | T3 | L/-/-/L/- | owner brief; TW | (b) |
| PT-04 | **Snowfall** (aggregates 0.5–1.5 m/s, drift, flicker; accumulation on horizontal surfaces) | rain-speed snow; no accumulation on the roof after minutes | T3 | M/L/L/L/L | LH; REFS ref03 (snowfall particles), ref04 (snowy forest) | (b); accumulation (a) inside the snow block |
| PT-05 | **Petals** (cherry blossom, rose) drifting | stiff cards | T3 | L/M/L/M/M | eng | (b) |
| PT-06 | **Confetti / streamers** (celebration, launch) | confetti falls like stones; no flutter | T3 | L/M/-/M/M | eng | (b) |
| PT-07 | **Glitter / sparkle** (twinkling reflective flecks, cosmetics, jewellery) | constant-brightness dots | T3 | -/H/-/M/H | eng (beauty/jewellery ad staple) | (b) |
| PT-08 | **Sparks** (grinder, welding, impact, metal scrape) streaking with motion blur, bouncing, cooling orange→red | round dots without streaks; no bounce | T4 | M/L/-/L/M | Blender Guru sparks (METHODS) | (b) |
| PT-09 | **Embers / fireflies / floating bokeh** | uniform glowing dots | T3 | L/M/L/M/M | eng | (b) |
| PT-10 | **Bubbles** (carbonation in drink; underwater bubble streams, 8–33 cm/s rise; soap bubbles with iridescence) | bubbles rise at constant speed in a line; no wobble | T4 | -/H/-/L/M | BUB; BBM (beverage) | (b) |
| PT-11 | **Blowing sand / dust drift / sandstorm** | desert with no airborne sand | T3 | M/L/-/L/L | eng | (b) |
| PT-12 | **Powder burst** (holi colour, protein powder, makeup powder, flour) | powder as spheres, no billow | T4 | L/H/-/M/H | CGF (dust/powder) | (b) |
| PT-13 | **Pollen / seed fluff / dandelion** | (niche) | T3 | L/L/L/L/L | eng | (b) |
| PT-14 | **Secondary life** (butterfly on the badge, birds, insects via boids) | dead world | T3 | M/L/L/L/L | REFS ref05 (butterfly), ref04 (deer, bear) | (b) |
| PT-15 | **Ash / cinders falling** (post-fire mood) | as PT-04 | T3 | L/L/-/L/M | eng | (b) |

## 8. Gases (GS)

| ID | Phenomenon | Wrong looks like | Tier | V/P/F/C/S | Evidence | Class |
|---|---|---|---|---|---|---|
| GS-01 | **Smoke plumes and wisps** moving through the set (buoyant rise, curling, thinning; responds to wind and to the subject moving through it) | static fog card; smoke clips through the subject; no light scattering | T3 | H/M/L/M/H | owner brief; NO; CGF (fog and smoke) | (b) |
| GS-02 | **Steam** (coffee, food, hot bath, hot engine) rising in thin curling wisps that fade in < 20 cm | thick smoke on a coffee cup | T3 | -/H/L/-/L | eng (food/beverage ad staple) | (b); default-on for "hot drink" products is a taste rule |
| GS-03 | **Exhaust** → see VD-09 | | | | | |
| GS-04 | **Ground fog / rolling low fog wisps** | flat slab | T2 | H/L/L/M/M | spec §4.3 `ground_fog`; REFS ref03 (foggy mountain pass) | (b) |
| GS-05 | **Dry-ice fog** (heavy, pours over edges, hugs the floor) — the classic car-reveal and stage look | fog rises instead of sinking | T3 | H/M/-/M/M | eng (car reveal staple) | (b) |
| GS-06 | **Fire / flames** (candle, fireplace, burner, torch) with flicker light on subject | looping sprite with no light change | T4 | L/M/H/L/M | CGF (flame effects); JangaFX fire VDBs (ASSETS) | (b) |
| GS-07 | **Explosion / fireball / shockwave dust** | (VFX showpiece) | T4 | L/L/-/L/M | JangaFX explosion VDBs (ASSETS) | (b); likely brand-risk gated |
| GS-08 | **Perfume / aerosol mist spray** (atomiser cloud with fine droplets) | spray as smoke | T4 | -/H/-/-/M | eng (fragrance ad staple) | (b) |
| GS-09 | **Coloured smoke bomb** (fashion, car reveal) | as GS-01 | T3 | M/M/-/M/M | eng | (b) |
| GS-10 | **Volumetric clouds** (sky, fly-through, product among clouds) | painted backdrop | T3 | M/M/-/L/H | REFS ref05 (volumetric cloud sky) | (b) (world) |
| GS-11 | **Breath / cold-air vapour** | characters in snow without breath | T4 | -/-/-/M/- | eng | (a) for characters in cold worlds, later |

## 9. Fluids (FL)

| ID | Phenomenon | Wrong looks like | Tier | V/P/F/C/S | Evidence | Class |
|---|---|---|---|---|---|---|
| FL-01 | **Rain falling** (streaks sized by shutter: v × shutter time; 2–9 m/s by drop size; visible mainly when backlit) | uniform white lines everywhere; frozen dots; front-lit rain invisible or too bright | T2 | H/M/L/M/L | GK; REFS ref10 (rain streak particles), ref06 (rain macro); the GT3 RS rain film (spec §2a T2 reference); NO | (b) |
| FL-02 | **Rain impacts**: splashes and ring ripples on ground and puddles; crown splashes on the subject's horizontal surfaces | rain falls but nothing hits anything | T3 | H/M/-/L/- | REFS ref06 | (a) inside any rain block |
| FL-03 | **Droplets beading** on the subject (static; contact angle high on waxed paint/glass) | a "rainy" car with a dry body | T3 | H/H/L/L/L | REFS ref06 (water beading on paint), ref10 | (a) inside rain/wet blocks; (b) as "dew" / "fresh" |
| FL-04 | **Run-down drips / rivulets** following gravity along surface normals, merging, leaving a wet trail (the "liquid running down a can" ask) | drops slide straight down ignoring curvature; no trail; drops on underside surfaces | T4 | M/H/L/L/L | owner ask; FSH; REFS ref06 ("running drops unproven") | (c): a few runners always inside rain/condensation blocks (a); hero rivulet (b) |
| FL-05 | **Condensation / frost** on cold products (only below the fill line; fog film + droplets; frost crust) | condensation on the dry shoulder or cap; uniform dots | T4 | L/H/-/-/L | FSH, BBM, products.md P-M03; REFS ref08 "frost crust" | (b) (default-on for "cold drink" is a taste rule) |
| FL-06 | **Wet-surface state**: darkened albedo, lower roughness, sharper reflections on ground and subject; puddles in dips | "rain" over a dry, matte ground | T2 | H/M/L/M/L | vehicles.md V-L (wet ground 0.6–1.0) [R]; REFS ref06 (beading), ref04 (wet grimy paint); GT3 RS rain film | (a) coupled to rain/after-rain worlds |
| FL-07 | **Puddles with ripples and reflections** | flat mirror with no ripples in rain | T3 | H/L/-/L/- | GT3 RS rain film (spec §2a); vehicles.md wet ground [R] | (a) in wet worlds |
| FL-08 | **Pour** (into glass, onto product; rope → splash → fill; bubbles; meniscus) | clean tube with no break-up; volume not conserved | T4 | -/H/-/-/H | ART, BBM, REFS ref01 (caramel), ref12 | (b) |
| FL-09 | **Splash / product dropped into liquid** (cavity, crown, Worthington jet, droplets) | splash without a cavity; droplets float | T4 | -/H/-/-/H | WJ, BBM | (b) |
| FL-10 | **Milk crown / coronet** (drop onto thin film) | (showpiece) | T4 | -/M/-/-/H | WJ | (b) |
| FL-11 | **Liquid ribbon / swirl / wave** wrapping the product (cosmetics creams, juice waves, "liquid sculpture") | blobby, noisy mesh; no surface tension detail | T4 | -/H/-/-/H | CGF, GF, PIX | (b) |
| FL-12 | **Underwater look**: caustics on surfaces, suspended particulates, bubbles, light shafts, colour absorption with depth | clean air with a blue tint | T3 | L/M/-/L/M | phase-3 vocabulary `world.water`; REFS ref08 (water surface overhead) | (b) (world) |
| FL-13 | **Ink / paint cloud in water** (billowing, curling) | fast smoke look | T4 | -/M/-/-/H | BlenderNation ink tutorial (METHODS) | (b) |
| FL-14 | **Viscous flow** (honey, caramel, chocolate, paint pouring over objects, coiling and folding) | water-like splash for honey | T4 | -/H/-/-/H | REFS ref01 (caramel pour), ref12 (paint over cylinders, grey clay fluid sim reads real) | (b) |
| FL-15 | **Open water surface** (lake, ocean waves, wake) | flat plane | T3 | M/L/-/L/M | phase-3 vocabulary `world.water` | (b) (world) |
| FL-16 | **Spray / mist** (hose, sprinkler, car-wash, sprayer) hitting the subject and running off | spray passes through the body | T4 | M/M/-/-/L | eng | (b) |
| FL-17 | **Fizz / carbonation** (with PT-10) | still soda | T4 | -/H/-/-/L | BBM | (b) |
| FL-18 | **Ice cubes in a drink** (bob, clink, bubbles) | ice intersects glass | T4 | -/M/-/-/L | eng | (b) |
| FL-19 | **Melting** (ice cream drip, candle wax, ice block) | (showpiece) | T4 | -/M/L/-/M | eng | (b) |
| FL-20 | **Drips from the subject after rain** (drops falling off bumpers, eaves, lamp) | wet car with no drips | T4 | M/L/L/-/- | eng | (a) inside rain/after-rain, low count |

## 10. Wind as one global field (WD)

| ID | Phenomenon | Wrong looks like | Tier | V/P/F/C/S | Evidence | Class |
|---|---|---|---|---|---|---|
| WD-01 | **One wind field per shot/world**: direction, mean speed (Beaufort-anchored), gust period, turbulence. Drives rain slant, snow drift, leaves, tumbleweeds, smoke, steam, fog, flags, curtains, grass, trees, hair, fur, cables | leaves blow left while smoke drifts right; flag flaps in dead-still grass; rain perfectly vertical in a storm | T3 | H/M/M/M/M | BF (visible effects per wind speed), TW | (a): the field always exists (calm by default); every wind-driven block reads it |

Beaufort anchors for the field (BF): F0–1 calm (< 1.5 m/s: smoke rises vertically / drifts);
F2 1.6–3.3 m/s (leaves rustle); F3 3.4–5.5 m/s (leaves and twigs in constant motion, flags extend);
F4 5.5–7.9 m/s (dust and loose paper raised, small branches move); F5–6 8–13.8 m/s (small trees
sway, large branches move). Ads mostly sit at F1–F4; F5+ is a "storm" mood.

## 11. Light–matter phenomena that read as physics (LM)

| ID | Phenomenon | Wrong looks like | Tier | V/P/F/C/S | Evidence | Class |
|---|---|---|---|---|---|---|
| LM-01 | **Caustics** (light focused through glass/liquid onto the floor; pool caustics) | glass bottle casts a flat grey shadow | T3 | L/H/L/-/H | REFS ref12 (refraction/caustics through glass) | (c): shadow caustics on for glass/liquid subjects (a); animated water caustics (b) |
| LM-02 | **Heat haze / refraction shimmer** (exhaust, hot road, fire, desert) | (subtle) | T4 | M/L/-/-/L | heat-haze tutorials (METHODS) | (b) |
| LM-03 | **Volumetric shafts through particles/haze** (only when a light is behind the medium toward camera) | shafts with front light; flat haze | T2 | H/M/H/M/H | NO; vehicles.md V-W02 [R] | (a) as a rule inside haze/fog blocks (place a backlight when shafts are wanted) |
| LM-04 | **Specular glints on droplets, glitter, sparks** | droplets matte | T3 | H/H/-/L/M | REFS ref06, ref10 | (a) inside droplet blocks (material rule) |
| LM-05 | **Rain visible by backlight only** (rain streak brightness from rim/practicals) | rain washes the frame white or disappears | T2 | H/M/-/M/- | NO (backlit shafts), REFS ref10 (rain streaks) | (a) inside rain block |
| LM-06 | **Lens contamination**: raindrops on lens, lens splash, condensation on lens | (taste; FPV realism) | T4 | M/L/-/L/L | eng (FPV/action-cam realism; REFS ref04 action-cam distortion) | (b) |
| LM-07 | **Backlit liquid glow** (beverage translucency) | dark, dead liquid | T3 | -/H/-/-/M | products.md glass_field P-L08/P-L09 [R] | (a) for liquid-filled glass (lighting rule) |
| LM-08 | **Fire flicker light on subject** (light from GS-06 moves) | fire with steady light | T4 | L/M/H/L/M | eng | (a) inside fire blocks |
| LM-09 | **Thin-film iridescence** (soap bubbles, oil on puddles) | grey bubbles | T4 | L/L/-/-/M | eng | (b) |
| LM-10 | **Motion blur of fast physics** (spinning wheels, sparks, rain streaks, splashes) | strobing, stepped particles | T3 | H/H/L/M/H | TIERS T2-05 (shutter 0.5); WW | (a): every sim/particle block emits velocity for blur |

## 12. Secondary / follow-through motion (SF)

| ID | Phenomenon | Wrong looks like | Tier | V/P/F/C/S | Evidence | Class |
|---|---|---|---|---|---|---|
| SF-01 | **Antenna / whip / thin-part wobble** after a stop | rigid | T4 | L/L/-/L/- | eng | (a) when a thin cantilever part is detected, later |
| SF-02 | **Straps, laces, tags, zipper pulls** swinging on bags and shoes | frozen laces during a drop | T4 | -/H/-/M/- | eng (apparel ad staple) | (c) |
| SF-03 | **Pendants, earrings, watch straps, keychains, charms** | rigid dangle | T4 | L/M/-/H/- | characters.md C-M01 [R] | (c) |
| SF-04 | **Hanging lamps / chandeliers** swinging slightly | (subtle) | T3 | -/L/M/-/- | eng | (b) |
| SF-05 | **Overshoot and settle** on any subject that moves then stops (landing shake, hero settle) | dead stop | T3 | H/H/M/M/H | products.md P-M01 "2 f damped landing shake"; P-C11 [R] | (a) |
| SF-06 | **Continuous mechanisms** (watch seconds hand sweep/tick, fan blades, propeller, turbine, clockwork gears) | frozen watch hands in a "live" shot; wrong tick rate | T3 | L/M/L/L/M | REFS ref10 (Rolex macro) | (c): mechanisms detected as parts run at a plausible rate (a), later |
| SF-07 | **Liquid slosh inside a moving container** | liquid stays level-locked during a tilt | T4 | -/M/-/-/L | eng | (b) |

## 13. Other phenomena found (OT)

| ID | Phenomenon | Wrong looks like | Tier | V/P/F/C/S | Evidence | Class |
|---|---|---|---|---|---|---|
| OT-01 | **Frost / ice growth** creeping over a surface (time-lapse) | static texture swap | T4 | L/M/-/-/M | REFS ref08 (frost crust) | (b) |
| OT-02 | **Dirt / mud splatter accumulation** on bodywork (rally) | clean car after off-road | T4 | M/-/-/-/- | REFS ref04 (wet grimy paint) | (b), (a) after VD-11 driving later |
| OT-03 | **Traffic / other moving vehicles** | empty road in a "city" | T3 | M/-/-/-/- | REFS ref09 (traffic as the whole environment) | (b) (world) |
| OT-04 | **Moving sun / time-lapse shadows** | (niche) | T3 | L/L/M/-/L | furniture craft (daylight interiors) | (b) |
| OT-05 | **Magnetic / stylised physics** (parts snap together, anti-gravity assembly, liquid defying gravity) | (showpiece) | T3 | L/H/L/L/H | products.md P-M01 [R] | (b) |
| OT-06 | **Growth** (vines, flowers blooming around a product) | (showpiece) | T4 | -/M/L/-/H | eng | (b) |
| OT-07 | **Speed ramp / slow motion of sims** (sim time scale 0.1–0.2 = ~300 fps look) | real-time splash reads as tiny ("miniature") | T4 | M/H/-/M/H | BBM, products.md P-M02 [R] | (a) as a rule: every sim has a time scale set by subject size and shot intent |
| OT-08 | **True-scale gravity & inertia**: a 10 cm product falls a body length in ~0.14 s; a car in ~0.6 s; at real time small things look fast and toy-like | small product "drops like a pebble"; big car falls like a feather | T3 | H/H/H/H/H | spec §4.1 true size; eng (t = √(2h/g)) | (a): simulate in true metres, then pick time scale deliberately |

---

## 14. Counts and the always-on list

**Phenomena catalogued: 130 distinct** (131 ID rows; GS-03 is only a pointer to VD-09). Per family:
CD 10, VD 16, RB 12, DS 4, SC 10, HF 7, PT 15, GS 10 (+1 pointer), FL 20, WD 1, LM 10, SF 7, OT 8.
Every ID is unique (checked with a grep count on 2026-09-24). Some rows are deliberately linked
(CD-07 ↔ HF-06, RB-11 ↔ SF-04); they are distinct phenomena that share a method.

**Always-on realism defaults (class a, or the (a) half of c)** — the compiler applies these with no
prompt, whenever the scene qualifies:

| Default | Applies when | IDs |
|---|---|---|
| Contact shadow + occlusion at the ground seam | subject placement = ground | CD-01 |
| Tyre contact patch + sidewall bulge | SubjectProfile has `wheels` | CD-02 |
| Suspension static sag + settle bounce after any stop / drop-in | `wheels` | VD-01 |
| Wheel ω = v/r, steering into curves, strobe guard | `wheels` and subject moves | VD-02, VD-03 |
| Body roll / pitch from the motion path | vehicle drives a curve / changes speed | VD-04, VD-05 |
| Road micro-vibration at speed | vehicle drives | VD-06 |
| Spray behind tyres on wet worlds; faint dust on dry dirt | vehicle drives on such a world | VD-12, VD-11 (subtle) |
| Resting-object sink into soft parts; heavy feet into rug pile | soft part or soft floor detected | CD-03, CD-10 |
| Soft-goods squash on landing | subject classed soft (fabric-like) and lands | CD-04 |
| Ground-cover conformity (tyres/feet sink into grass, blades flattened) | world has scatter | CD-07, HF-06 |
| Tracks/prints behind moving things on soft ground | moving subject on snow/sand/mud | CD-05 |
| Physical drop-in settle; every sim collides with the subject | any drop-in / any sim | RB-01, RB-12 |
| Overshoot-and-settle on every stop | subject motion ends | SF-05 |
| Hanging parts hang under gravity (straps, cables, pendants) | such parts detected with high confidence | SC-08, SF-02, SF-03 |
| Grass, flowers and trees sway | outdoor world with foliage | HF-01..HF-03 |
| Curtain billow | interior world with an open window | SC-09 |
| One shared wind field (calm by default) | always | WD-01 |
| Rain couples to: impacts + ripples, droplets on subject, wet state, puddles, a few runners, drips, backlit streaks | a rain block is present | FL-02, FL-03, FL-04 (few), FL-06, FL-07, FL-20, LM-05 |
| Snow accumulates on horizontal surfaces | a snow block is present | PT-04 |
| Faint dust motes in visible shafts; shafts only when backlit | haze/fog present | PT-01, LM-03 |
| Shadow caustics on glass/liquid subjects; backlit liquid glow | glass/transmissive material class | LM-01, LM-07 |
| Motion blur from velocity on every sim/particle | any sim/particle | LM-10 |
| True-scale physics + deliberate time scale | any sim | OT-07, OT-08 |
| Garment/hair follow-through | rigged character moves and has separable cloth/hair | SC-04, HF-04 |

## 15. What the §9a corpus should add

Add a `physics` object to `valora.ref/1` with one entry per observed phenomenon ID from this file
(plus `touchesSubject: bool`, `timeScale: realtime|slowmo|timelapse`, `evidence` frame ids), so the
H/M/L estimates above become counts, and the value side of PHASING's value × cost ranking is
measured instead of estimated. PILOT-NOTES §1 already found that "sim state needs frames every
0.5 s"; sample physics at 0.5 s.
