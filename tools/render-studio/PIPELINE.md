# Render Studio pipeline

How a ModVision build becomes an MP4, and every knob along the way. Written for
an engineer who has to author a **new scene** and does not yet know the code.

Scope: everything under `tools/render-studio/` plus the site-side exporter in
`js/render-studio/`. Every claim below cites a file and line. Where the README
and the code disagree, the disagreement is stated.

---

## 1. Job lifecycle

### 1.1 Site GLB export (browser)

`createBuildSnapshot(car)` (`js/render-studio/snapshot.js:6`) walks the live car
with `traverseVisible`, clones each geometry, and rebuilds its material as a
`MeshPhysicalMaterial`/`MeshStandardMaterial` copy (`:16-20`). Anything that is
not one of those three classes is dropped and recorded in `warnings` ("Effect
omitted", `:29`) — the code behind README:35's "Custom browser shaders and
effects are approximated by GLB materials". Skinned/morphed meshes are baked
into their current pose (`:33-42`); instanced meshes expand to one mesh per
instance with a `-<i>` suffix (`:52-57`). Nothing live is mutated or disposed.

`exportBuildSnapshot` (`:71`) runs `GLTFExporter.parseAsync` with
`{ binary: true, onlyVisible: true, maxTextureSize: 2048 }` (`:75`), rejects
anything over **90 MB** of GLB (`:76`), and base64-encodes it.

`createBuildSnapshot(car, { slotFor })` also stamps each mesh's ModVision slot
id into `userData.mvSlot` (`slotForMeshName` from `click-to-select6.js`), which
`GLTFExporter` writes as a glTF extra and Blender's importer surfaces as a
custom property — the only car-independent way the pipeline has to know what a
mesh is.

`buildToRenderJob` (`config.js:22`) builds the spec. It refuses while the car is
loading or exploded view is open (`:23-24`) and derives
`resolution`/`total_frames` from the client-side `PRESETS` (`:2-10`) so the
numbers match what Python recomputes. `provider.js:7` posts to
`http://127.0.0.1:8765`; progress arrives over `EventSource` on
`/api/jobs/<id>/events` (`provider.js:41`).

The dialog (`js/render-studio/ui.js`) keeps three hidden native selects
(scene / preset / aspect) as the single source of truth for `options()`; the
Scene, Format and Quality cards write to them and dispatch `change`. Quality
cards cover only three tiers (Preview = `film_preview`, Standard =
`film_final`, Ultra = `4k`); the other presets live in the Fine tune › Quality
presets select. Look cards come from `looks.js` (`LOOKS`, `applyLook`,
`matchLook`, `lookLabel`): a Look is a set of spec values clamped to the current
manifest, so the spec the server receives is the only contract and Python has
no notion of a Look. Submit reassembles a scattered car through
`window.scatterEngine.reassemble()` before `buildToRenderJob`, so its
exploded-view refusal is a guard, not a user-facing path.

The Render button exists only on the dev server: the repo-root
`server.py:360-361` injects `bootstrap.js` into `index.html` when
`MV_RENDER_STUDIO` is `local`. `scripts/build-public.mjs:45-46` prunes
`js/render-studio` and `css/render-studio.css` and lists `tools` as FORBIDDEN.

### 1.2 `server.py` — the loopback API

One `ThreadingHTTPServer` bound to `127.0.0.1` (`server.py:29`). On Windows it
sets `SO_EXCLUSIVEADDRUSE` and disables `allow_reuse_address` so a second
process cannot hijack a live worker's port (`server.py:24,32-34`).

Every request passes `_guard()` (`server.py:46`):

- exactly one `Host` header, and it must be `localhost:<port>`,
  `127.0.0.1:<port>` or `[::1]:<port>` — else 403 (`server.py:51-52`).
- at most one `Origin`, matching `^http://(localhost|127.0.0.1|[::1]):port$`
  (`server.py:16,53-60`).
- mutations must be `Content-Type: application/json` (`server.py:61-62`).

Routes:

| Method | Path | Handler |
|---|---|---|
| GET | `/api/health` | `server.py:154` — dependency probe + `queueLength`; `ready` is blender AND ffmpeg |
| GET | `/api/scenes` | `server.py:161` — returns `jobs.SCENES` with each scene manifest embedded (`manifest`) |
| GET | `/api/estimate?preset&scene&aspect` | `server.py:163-165` — defaults `draft` / `turntable` / `16:9` |
| GET | `/api/jobs` | `server.py:166` |
| GET | `/api/jobs/<32 hex>` | `server.py:170` |
| GET | `/api/jobs/<32 hex>/events` | `server.py:168` → `_events`, SSE |
| GET | `/files/<jobId>/<name>` | `server.py:172` → `_file` |
| POST | `/api/jobs` | `server.py:186` — 503 if blender/ffmpeg missing, then `validate_job` |
| POST | `/api/jobs/<id>/cancel` | `server.py:192` — body must be `{}` |
| POST | `/api/jobs/<id>/retry` | `server.py:196` — body must be `{}` |
| DELETE | `/api/jobs/<id>` | `server.py:210` |
| OPTIONS | any | `server.py:132` — only GET/POST/DELETE, only `content-type`/`range` headers |

`_file` (`server.py:250`) serves **only** the three names in `FILE_TYPES`
(`server.py:17`): `video.mp4`, `poster.jpg`, `latest.jpg`. Everything else 404s.
`latest.jpg` is readable mid-render; the other two require `status == "done"`
(`server.py:256-257`). `Range` is honoured only for `video.mp4`
(`server.py:270,293`), with a 416 + `Content-Range: bytes */size` on a bad range
(`server.py:287-289`).

`_events` (`server.py:226`) is a revision-polled SSE loop with a 15 s heartbeat
that returns as soon as the job reaches a terminal state.

`main()` (`server.py:310`) binds the port **before** constructing the `JobStore`
(`server.py:319-324`) — the comment at `server.py:317` explains why: a second
launch must never mutate the live worker's on-disk state.

### 1.3 `jobs.py` — validation, presets, queue

**`PRESETS`** (`jobs.py:24-32`) — seven entries, each `engine`, `resolution`,
`duration_s`, `fps`, `samples`, `previewPrice`:

| id | engine | resolution | dur | fps | samples | price |
|---|---|---|---|---|---|---|
| `smoke` | EEVEE | 320×180 | 1 | 12 | 8 | 0 |
| `draft` | EEVEE | 1280×720 | 6 | 30 | 32 | 0 |
| `film_preview` | CYCLES | 1280×720 | 10 | 24 | 96 | 0 |
| `film_final` | CYCLES | 1920×1080 | 10 | 24 | 192 | 0 |
| `standard` | CYCLES | 1920×1080 | 10 | 30 | 256 | 5 |
| `cinematic` | CYCLES | 1920×1080 | 15 | 30 | 512 | 8 |
| `4k` | CYCLES | 3840×2160 | 10 | 30 | 256 | 15 |

This table is duplicated in `js/render-studio/config.js:2-10`. **They must be
kept in sync by hand** — nothing generates one from the other. (They currently
agree.)

**`SCENES`** (`jobs.py:33-37`) — three dicts (`id`, `name`, `description`,
`aspects`). `SCENE_IDS` (`jobs.py:38`) is derived from it. Also duplicated in
`config.js:12-16`.

**`SPEC_FIELDS`** (`jobs.py:39`) is an allow-list of 21 job keys (`spec` joined
2026-09-17). `validate_job` rejects any key outside it. This is the mechanism
that keeps `look`, `grain`, `proof_offsets` and `save_blend` out of API jobs — see §7.

**spec → look (`spec.py`)**: between field validation and the queue, `validate_job`
gates `job.car` through `render_cars.is_allowed` (shipping fleet minus
`render-denied-cars.json`; a refusal is a 403) and, when the job carries `spec`,
runs `spec.validate_spec` against the scene manifest (`scenes/<id>.json`), checks
`spec.scene == job.scene`, and writes the server-owned `look` (`spec_to_look`) and
`grain` (`spec.look.grain`) into the canonical job. A spec-less job gets neither
key, so it renders exactly as before. `retry` re-runs the car gate. Inside
Blender, `render_snapshot.py` derives the four scene seeds from
`LOOK['scene_seed']` (`spec.derive_seeds`); the default seed 20260915 keeps the
2026-09-17 film's literal seeds. Routes: `GET /api/scenes` embeds each manifest,
`GET /api/spec/random?scene=&seed=` returns a deterministic random spec.

**`canonical_settings(preset, scene, aspect)`** (`jobs.py:52`) is the single
source of derived numbers: it deep-copies the preset, drops `previewPrice`,
reverses `resolution` for `9:16` (`jobs.py:61-62`), and computes
`frame_start=1`, `frame_end=frames`, `total_frames=duration_s*fps`
(`jobs.py:63-64`).

`validate_job` (`jobs.py:67`) then requires `schema == 1` as a real `int`
(`:71`); checks `car`/`buildId` against `ID_PATTERN` so they cannot be paths
(`:22,75-80`); caps `parts` at 256 (`:82`); validates `paint.hex` as `#rrggbb`
and `paint.finish` against a nine-value allow-list (`:85-88`); bounds `tint` to
[0,1] and `ride_height` to [-1,1] (`:89-92`); and — importantly — **re-derives**
the settings and rejects the job if any client-supplied
`resolution`/`fps`/`samples`/… disagrees, type included (`:95-98`). A client
cannot ask for 1000 samples at a draft price.

`validate_snapshot` (`:112`) parses the GLB header itself — magic, version 2,
declared length == actual, JSON chunk type, 4-byte alignment (`:113-117`) — then
walks every binary chunk (`:134-141`) and rejects any `buffers`/`images` entry
whose `uri` is not a `data:` URI (`:124-133`).

**Limits**: `MAX_BODY_BYTES = 128 MiB` (`:19`), `MAX_PENDING_JOBS = 8` (`:20`).

**`JobStore`** (`:144`) is a durable single-worker queue behind one `RLock` +
`Condition`. `_restore` (`:171`) rehydrates `out/` on boot: `queued` jobs with a
snapshot re-enter the queue, anything else non-terminal is marked `failed`.
`_persist` writes `job.json` through `.tmp` + `replace` (`:189-193`).
`directory()` (`:163`) re-validates the id and refuses any path escaping `out/`.
`submit` (`:212`) 429s at 8 non-terminal jobs; `delete` (`:255`) 409s unless
terminal and inactive; `retry` (`:266`) re-validates the saved snapshot first.

**`estimate`** (`jobs.py:278`) averages `stats.secondsPerFrame` over completed
jobs *of the same preset*; with no history it falls back to the hardcoded table
at `jobs.py:283` — smoke 0.5, draft 0.8, film_preview 7, film_final 18, standard
20, cinematic 30, 4k 50 s/frame — plus a flat 120 s scene-build allowance
(`jobs.py:284`). `measured: false` in the response means the fallback was used.

`_work` (`jobs.py:287`) is the worker thread: pop, mark `preparing`, call the
pipeline with a `progress` callback that filters to a fixed field set and clamps
progress to 0.99 (`jobs.py:306-312`), then require `video.mp4` to exist before
declaring `done` (`jobs.py:319-320`).

### 1.4 `pipeline.py` — Blender invocation and encode

`discover_dependencies()` (`pipeline.py:38`) searches `BLENDER_PATH`/`BLENDER`,
PATH, then a glob list of standard install locations (`pipeline.py:46-58`),
falls back to the `imageio_ffmpeg` bundled binary (`pipeline.py:59-66`), and
probes `nvidia-smi` for a GPU name. Results are cached for 30 s
(`pipeline.py:42`).

`run_pipeline(job, job_dir, on_progress, cancelled)` (`pipeline.py:164`):

1. Requires `job_dir/snapshot.glb` (`pipeline.py:171-173`).
2. Writes the spec to `pipeline-job.json` (`pipeline.py:181-182`). The comment
   at `pipeline.py:167` is the ownership rule: **the queue owns `job.json`; the
   pipeline owns `pipeline-job.json` and the outputs.**
3. Runs Blender: `--background --factory-startup --disable-autoexec
   --python-exit-code 1 --python render_snapshot.py -- <spec>`
   (`pipeline.py:194-197`).
4. Progress crosses the process boundary as stdout lines: `render_snapshot.py`
   prints `PROGRESS <json>` (`render_snapshot.py:27-28`), `blender_line`
   (`pipeline.py:185-192`) parses them. Everything else goes to `log.txt`.
5. Reads `render-stats.json` and verifies **every** requested frame PNG exists
   (`pipeline.py:198-204`).
6. Encodes (below), then a `poster.jpg` from the first frame
   (`pipeline.py:218-222`) and copies it to `latest.jpg` if the renderer never
   wrote one (`pipeline.py:226-227`).
7. Writes `stats.json` and returns it (`pipeline.py:228-241`).

**Cancellation** is cooperative and prompt. `_run_process` (`pipeline.py:99`)
drains the child's stdout on a *separate reader thread* and polls `cancelled`
every 100 ms, so a cancel never waits for the next output line
(`pipeline.py:100,123-127`). `_stop_process` (`pipeline.py:88`) terminates, then
kills after 1.5 s. `RenderCancelled` (`pipeline.py:20`) is the signal.

**`encoding_settings(job, resolution)`** (`pipeline.py:150`) is the delivery
policy, keyed on pixel count:

- ≥ 3840×2160 → 60 Mbps target; ≥ 1920×1080 → 20 Mbps; otherwise CRF 18
  (`pipeline.py:153`).
- With a bitrate: `-preset slow`, `-maxrate` = 1.25×, `-bufsize` = 2×
  (`pipeline.py:154-155`), and **two-pass** encoding (`pipeline.py:213-216`).
- Without: `-preset fast -crf 18`, single pass.
- **Scene-conditional filter**: if `job['scene'] == 'rainy_courtyard'`
  (`pipeline.py:159`) it appends a vignette + shadow-weighted grain
  `-vf` chain (`pipeline.py:160`). This is a hardcoded scene-id string in the
  encoder — see §5.
- Always `yuv420p` + `-movflags +faststart` (`pipeline.py:211,217`).

### 1.5 `render_snapshot.py main()` — inside Blender

Entry: `blender ... --python render_snapshot.py -- <pipeline-job.json>`
(`render_snapshot.py:3`). `main()` is at `render_snapshot.py:93`. Step by step:

1. **Import.** `read_factory_settings(use_empty=True)` then
   `import_scene.gltf(snapshot.glb)` (`:104-105`). Collect visible meshes
   (`:107`) — empty is a hard error.
2. **Bounds.** World-space bbox of every mesh corner → `low`, `high`, `center`,
   `extent`, `span` (`:110-117`). Non-finite or absurd bounds abort (`:112,118`).
   **`scale = span / 4.8`** (`:120`) — the single normalisation constant. Every
   light energy, light size, fog density, bead radius and camera clip below is
   expressed as a multiple of it, so the scene adapts to a car of any size.
3. **Scene flags.** `rainy = job['scene'] == 'rainy_courtyard'` (`:121`);
   `night = job['scene'] == 'night_garage'` (`:126`). *These two booleans are the
   entire scene dispatch.*
4. **Look config.** `rain_look.configure(job.get('look'))` (`:122`) — CLI only.
5. **Material calibration**, always, for every scene:
   `component_materials.prepare` (`:123`), `render_materials.calibrate_materials`
   (`:124`), `surface_detail.tire_sidewalls` (`:125`). All three take `wet=rainy`.
6. **Base studio**, built unconditionally then torn down for rain: a world
   background (`:128-132`), a giant floor plane (`:134-137`), and four area
   lights — Key softbox, Fill softbox, Roof strip, Rear rim (`:140-143`).
   `night` only changes their colours/energies and the world/floor values.
7. **Rain branch** (`:146-160`): delete every light and the floor, then
   `rain_scene.build` → `car_apron` → `weathered_rotors` →
   `rain_look.environment` → `car_materials` → `road_weathering.apply` →
   `add_water_beads` → `link_reflections` → `wheel_reflector` → `cabin_fill` →
   `rain_look.lamps`.
8. **Output format** (`:164-180`): resolution (swapped for `9:16`),
   PNG/RGB/8-bit, AgX; the *look* is `LOOK['view_look']` when rainy, else
   "AgX - Medium High Contrast". **Frame range** at `:181-186`.
9. **Rain animation** (`:187-221`): ripple clock + `rain_atmosphere.build` when
   `LOOK['falling_rain']`, otherwise ripple strength is zeroed (`:209-216`);
   then `rain_atmosphere.drips` and `wind.apply`.
10. **Engine.** `pick_engine` (`:55`) sets EEVEE (with a Blender 4/5 name
    fallback, `:58-60`) or Cycles, and probes OPTIX → CUDA → HIP → METAL,
    falling back to CPU (`:74-90`). Rain additionally pins bounce limits,
    `sample_clamp_indirect = 5`, seed and denoiser (`:223-237`). Then exposure
    and compositor (`:238-240`).
11. **Camera** (`:241-288`). A 48 mm / 36 mm-sensor camera is created for all
    scenes; orbit distance is solved from the tighter of hfov/vfov (`:248-251`).
    If rainy, `film_camera.animate` replaces it entirely (`:256`), and the CLI
    probe modes may then overwrite that (`:257-284`).
12. **Proof mode** (`:289-294`). `offsets = job.get('proof_offsets',
    range(total))` — a CLI spec can render five representative frames instead of
    a film. `save_blend` writes `scene.blend` at the first offset.
13. **Render loop** (`:298-323`). For non-rain scenes the camera is placed per
    frame on a circular orbit (`:303-306`) — `radians(38) + tau*offset/total`,
    elevation 13° (night) or 17° (`:254`). PNGs are named by *output index*, not
    source offset (`:307`), so a proof run is contiguous. Every 10th frame (plus
    first and last) is also written as `latest.jpg` through a `.tmp` + `replace`
    so a polling browser never sees a half-written file (`:312-320`).
14. **Stats** (`:324-329`): `render-stats.json` plus a `RENDER_DONE <json>` line.

### 1.5b Preview watermark (`watermark.py`)

A preset with `"watermark": True` (smoke, draft, film_preview) never leaves a
clean pixel reachable: `run_pipeline` builds `watermark.png` at the job's
resolution with Pillow's bundled scalable font (diagonal MODVISION PREVIEW
tile at alpha 64 + a solid corner badge), `finish_filter` composites it as
ffmpeg input 1 AFTER the grain stage and maps `[wm]`, the poster gets the same
overlay, and Blender writes its progress still to `latest-raw.jpg` which the
parent stamps into `latest.jpg` on every PROGRESS line (the raw file is
deleted on completion). Missing Pillow fails the job rather than shipping an
unmarked preview. `canonical_settings` overwrites the client's value, so the
flag cannot be cleared from the browser.

### 1.6 Outputs

Per job, in `tools/render-studio/out/<jobId>/` (README:69):
`snapshot.glb`, `job.json` (queue-owned), `pipeline-job.json` (pipeline-owned),
`log.txt`, `frames/frame_%06d.png`, `render-stats.json`, `video.mp4`,
`poster.jpg`, `latest.jpg`, `stats.json`, and `scene.blend` for CLI proof jobs.
Only the three files in `FILE_TYPES` are reachable over HTTP.

---

## 2. Module map

| Module | One line |
|---|---|
| Module | One line | Watch out |
|---|---|---|
| `spec.py` | RenderSpec: `load_manifest`, `validate_spec`, `default_spec`, `sample_spec` (crc32-seeded `random.Random`, sampler `v0`), `spec_to_look`, `derive_seeds`. Pure, no bpy. | Manifests must carry `schema` and an `id` equal to their filename; `scene_id.isidentifier()` is the path guard. Editing a manifest's ranges changes what `/api/spec/random` can return and what the browser form shows. |
| `scenes/*.json` | Per-scene manifests: enums, ranges, booleans, default spec, sampling windows/weights. | A range `[x, x]` or single-option enum is hidden by the site form. Orbit scenes collapse saturation/fog/bloom/halation/veil because their consumers are courtyard-only. |
| `render_cars.py` | `allowed_cars()` = pickers from `scripts/print-shipping-cars.mjs` (cache `data/aftermarket/_shipping-cars.json`, warns on fallback) minus `render-denied-cars.json`; `MV_RENDER_CAR_IDS` overrides for tests. | Never parse `LICENSED_CAR_IDS` here. The cache is only as fresh as the last printer run. |
| `render_materials.py` | Offline equivalents for known browser materials; `calibrate_materials(meshes, wet, scale)` (`:22`), `add_water_beads(meshes, scale, seed=20260915)` (`:97`, cap `BEAD_LIMIT = 60000` at `:94`). | Routing is entirely material-name prefixes: `mv-carbon-weave` (`:33`), `mv-unified-paint` (`:55`), `mv-window-tint` (`:71`), `mv-smoke-lens` (`:78`), bare `rubber` (`:84`). A differently-named export gets **no** treatment and therefore **no** wet flags and **no** beads. Assumes Z-up and a level car (`:121`, `:149`). |
| `component_materials.py` | Per-component corrections **scoped to one car**: `MANTHEY_992` (`:11`); `prepare()` (`:145`) and `weathered_rotors()` (`:14`) return `[]` for any other id (`:16`, `:146`). | The most asset-locked file here. Mesh regexes `rotor-[fr][lr]`, `headlight-[lr]-lens-(\d+)`, `caliper-(front\|rear)-[lr]`; and `int(match[1]) in (2, 9)` (`:165`) decides cover-vs-internal optic from *this one GLB's* lens numbering. |
| `surface_detail.py` | Reusable shader-node builders — `noise`/`variation`/`bump` (`:7-25`), `lacquer` (`:38`), `metallic_flake` (`:52`), `rubber` (`:86`), `thin_lens` (`:98`) — plus `tire_sidewalls` (`:338`). | Material name must be exactly `rubber` (`:361`); mesh prefixes `tire-`/`tyre-` (`:347`). Generated-coordinate radius bands `.76`–`.94` (`:386`) assume the wheel fills its own bbox. Generated material names are per-object, so a second scene in one session collides. |
| `wet_detail.py` | Puddle impact rings: `puddle_normal(...)` (`:5`), `configure_ripple_animation(scene, first, total)` (`:64`). | The node **name** `'Rain impact time seconds'` is the cross-module contract (written `:27`, read `:72`, and `render_snapshot.py:199` reaches in by name). Discovery is the custom prop `mv_animated_puddles`. Blender 4.4+ layered-action API only, no legacy fallback (`:79-94`). |
| `road_weathering.py` | Car-agnostic world-position layers — `road_film` (`:150`) and `brake_dust` (`:178`), entry `apply(meshes, low, high, scale, look)` (`:215`). | **Hardcoded orientation: the nose must point along −Y** (docstring `:57`, tail lobe `high.y` `:78`). The only module reading LOOK through injection: `look['road_film']` (`:216`), `look['brake_dust']` (`:217`). |
| `rain_scene.py` | The courtyard itself: `hdri_path()` (`:14`), `wet_asphalt(scale)` (`:72`), `car_apron(...)` (`:235`), `environment` (`:249`), `park_ground` (`:292`), `leaf_mesh` (`:340`), `build(scene, center, low, scale)` (`:384`). | **This file *is* the scene.** `PUDDLE_LEVEL = 0.69` (`:69`) is calibrated against the exact sum of three height terms — change any noise scale and it is invalid. HDRI rotation `radians(110)` is written three times (`:257`, `:283`, `:306`) and must stay in sync. Furniture is at literal court metres (curbs `x = ±4.8` `:429`, beds `y ∈ (-7,-1,6,12)` `:432`). Litter keep-outs assume a ~2.5 × 5.6 m car (`:468`, `:480`). |
| `rain_atmosphere.py` — `build` | `build(scene, meshes, center, low, scale, first, total, seed=20260916, size, reach, backlight, glow)` (`:10`): the falling-drop field with continuous subframe motion and car interception. | Fall speed `6.5` m/s appears three times (`:19`, `:43`, `:119`). Spawn box is a literal `±7 × ±8 m` (`:24`) — this is the box `rain_reach` scales. Backlight is at a fixed offset authored for this courtyard (`:116-117`). |
| `rain_atmosphere.py` — `drips` | `drips(scene, meshes, center, extent, low, scale, first, seed=20260920, count=70, size=1.0, glow=0.0)` (`:122`): rays cast up from the road find underside emitters; each bead swells, releases, falls, and throws two low rings. Only a *falling* drip glows. | Outward direction is **radial from the car centre** (`:151`) — right for a car, wrong for a long or asymmetric subject. Gives up after 40,000 tries (`:143`). |
| `rain_look.py` | All art direction. `LOOK` (`:18`), `configure` (`:136`), `car_materials` (`:172`), `environment` (`:255`), `link_reflections` (`:320`), `compositor` (`:330`), `distance_fog` (`:386`), `lamps` (`:441`), `animate_lamps` (`:462`), `wheel_reflector` (`:494`), `cabin_fill` (`:520`), `animate_exposure` (`:541`), `animate_reflections` (`:564`). | `LOOK` is a module-level singleton mutated in place. See §3. |
| `scene_plants.py` | CC0 foliage instancing: `prototypes` (`:11`), `shape_variants(count=4, seed=20260919)` (`:42`), `plant_tree` (`:112`), `plant_grass` (`:120`), `plant_depth_layers` (`:131`), `plant_foreground_grass` (`:164`). | Object **names** are `wind.py`'s only discovery mechanism (`:117`, `:127`, `:154`, `:182` ⇄ `wind.py:154-155`). The verge has three literal keep-out rectangles coupled to both `rain_scene.py`'s beds and `film_camera.py`'s shot-0 walk-in route (`:175-180`). `plant_tree.planted` is state on the function object (`:115`) — not reset between scenes in one process. Needs numpy (`:53`). |
| `wind.py` | One gust field everything answers differently: `gust` (`:20`), `_rock` (`:43`), `_flutter` (`:75`), `_leaves` (`:116`), entry `apply(scene, first, total, scale, strength=1.0, canopy=True, seed=20260917)` (`:147`). | `DIRECTION = (.55, .835)` and `FRONT_SPEED = 7.0` are module-level (`:16-17`). The name dictionary at `:154-155` is the whole discovery mechanism — a rename in `scene_plants.py` yields a silent zero-count report, not an error. Near-tuft cull box is court-sized (`:164`). |
| `film_camera.py` | The simulated operator — see the shot table below. | Nose at −Y, camera side at +X (docstring `:67`). Anchor prefixes `wheel-fl`/`tire-fl`/`headlight-l-lens` (`:30`), with graceful bounds fallbacks (`:25-26`). `_TAKES` is a module-global cache (`:132`). The `points` argument to `pose()` and `animate()` is accepted and **never used** — dead parameter. |
| `prepare_assets.py` | One-shot checksum-verified fetch: `request` (`:12`), `fetch` (`:16`), `main()` (`:32`). | A deliberate supply-chain fence: `fetch` refuses any path outside `assets/` and any host other than `dl.polyhaven.org` (`:18`). The asset list is a literal (`:42-53`); if `manifest.json` exists it is authoritative and the API is never queried (`:36-40`). |

### `film_camera.py` — the five shots

`_shots(center, extent, low, targets, scale, portrait)` (`:64`), in `SHOT_NAMES`
(`:8`) / `SHOT_BOUNDARIES` (`:9`) order:

| # | Name | Lens (landscape / portrait) | f/ | Anchored to |
|---|---|---|---|---|
| 0 | Low front three-quarter (walk-in) | 40 / 30 | 2.8 | **absolute court metres** `center + (7.65, −8.0)·scale`, chest 1.34 m → 4.4 m out at 1.12 m (`:92-94`) |
| 1 | Rear three-quarter | 28 / 24 | 2.0 | `tail = center.y + extent.y/2`, chest 1.18 → hip .86 m (`:100-107`) |
| 2 | Wheel and contact (crouched) | 70 / 70 | 2.2 | offsets from `targets['wheel']` (`:110-114`) |
| 3 | Headlight optics (lean-in) | 85 / 85 | 3.2 | offsets from `targets['lamp']` (`:117-121`) |
| 4 | Wet hood and carbon | 24 / 20 | 2.8 | `nose = center.y − extent.y/2` (`:123-128`) |

`portrait = height > width` (`:299`) and only swaps the wide lenses (`:85`,
`:99`); the two close-ups keep their focal length. The sensor is always 36 mm
`HORIZONTAL` (`:295-296`), so a portrait frame crops the horizontal field and
the tighter portrait lenses compensate. README:47 notes "Portrait uses 22/20 mm
for the walking shots" — **the code now reads 30/20 and 24** (`:85`, `:99`); the
README figure is stale (the change is recorded in work_state.md:28, "walk-in
lens 28 to 40 mm (portrait 22 to 30)").

`_operate(index, shot, frames, fps, scale)` (`:135`) integrates at 8 substeps
per frame (`:146`), seeded `random.Random(9176 + index)` (`:145`). Layers: pace
envelope with wander (`:153-156`), per-step randomised footfalls (`:181-185`), a
loose arm spring ~9 rad/s ζ .42 (`:216-220`), reframes every .5–1.4 s glided by
a 60/9.5 spring (`:162-165`, `:230-232`), footfall ring-down jolts (`:233-235`),
a damped aim spring ω 5.0 ζ .58 (`:171-172`), tracking that holds a *direction*
with slip tolerance, catch-up and attention lapses (`:247-264`), and 0–3
hesitations (`:175-179`). Each take is simulated once and cached in `_TAKES`
(`:132`), so `pose()` is deterministic.

`shot_at` (`:12-20`) resolves normalised boundaries to integer frames with
`math.ceil`, and `pose()` repeats the arithmetic (`:301-302`), so a short smoke
render never lands inside a zero-length shot and no sample interpolates across a
cut.

### `assets/`

`assets/manifest.json` pins 22 files with `source`, `url`, `license: "CC0"` and
an md5 each. On disk today (`ls -l`):

| File | Size |
|---|---|
| `cloudy_vondelpark_hdri_8k.hdr` | 109,009,782 B |
| `cloudy_vondelpark_hdri_4k.hdr` | 28,288,134 B |
| `asphalt_02_nor_gl_2k.jpg` | 4,943,950 B |
| `asphalt_02_Diffuse_2k.jpg` | 3,075,676 B |
| `asphalt_02_Rough_2k.jpg` | 2,230,457 B |
| `asphalt_02_Displacement_2k.exr` | 2,008,682 B |
| `tree_small_02/tree_small_02.bin` | 95,102,324 B |
| `tree_small_02/` gltf + 9 textures | 9,075 B + ~5.6 MB |
| `grass_medium_01/grass_medium_01.bin` | 1,006,632 B |
| `grass_medium_01/` gltf + 3 textures | 27,110 B + ~2.0 MB |
| `rain-scene-preview.png` | 2,260,580 B — **not in the manifest**; it is a render output used as the UI thumbnail |

All 21 manifest records are present on disk. Sources: Cloudy Vondelpark,
Asphalt 02, Tree Small 02, Grass Medium 01 — all Poly Haven CC0. Note both
`.bin` URLs point at Poly Haven's **8k** model directory even though the `.gltf`
is the 1k variant; that is their layout, mirrored by `prepare_assets.py:57`, not
a bug.

**README/disk mismatch:** README:57 says the setup "downloads roughly 140 MB".
The on-disk total is ~148 MB, dominated by the 8k HDRI (109 MB) and the tree
`.bin` (95 MB) — note those two alone exceed 140 MB, so the README figure
predates the 8k HDRI. Treat it as approximate, not a budget.

### `checks/claude-pass/` helper scripts

| Script | What it is for |
|---|---|
| `render_film_chunks.py` | Resumable full-film render. `py -u checks/claude-pass/render_film_chunks.py <16x9\|4k\|9x16> [chunk=12]` (`:82`; `TOTAL = 240` at `:25`). Scans `film-<tag>/frames` for frames PIL can **fully decode** (`:28-34`), renders only the missing ones a chunk at a time via a fresh Blender per chunk, aborts if a chunk yields 0 frames (`:68`), then two-pass encodes through `pipeline.encoding_settings` (`:69-77`). Hardlinks `checks/black-rain-v3/snapshot.glb` and hardcodes the Manthey car + `rainy_courtyard` (`:23,:43-44`). The one to use when memory is tight. |
| `render_film.py` | The same film through `pipeline.run_pipeline` in one process, without the API (README:65). |
| `seed_probe.py` | `py -u seed_probe.py <variant> [...]` (`:68`; 12 named variants at `:26-39` — `base`, `t010`, `s384`, `raw`, `optix`, `res4k`, `preview`, `final2`, …). Renders offsets **60 (wide)** and **190 (headlight)** under seeds 20260915 and 777 (`:23-25`), resumable, then diffs luma on the 1920×1080 delivery grid. Writes `n-<variant>.json` (mean/p95/p99/over2/over5) and ×24 heat maps (`:78-83`). **Hardcodes an absolute Blender path** `C:\Program Files\Blender Foundation\Blender 5.0\blender.exe` (`:22`) — it does not use `pipeline.discover_dependencies`. |
| `temporal_stability.py` | `py temporal_stability.py <job dir> [label]` (`:18-19`). Requires the run to have used `look.freeze_camera`. Stacks `frames/frame_*.png` as luma and computes a robust per-pixel temporal sigma `1.4826 * MAD` (`:23-24`). Writes `stability.json` (`sigmaMean/P95/P99`, `pixelsOver2`, `brightnessStepMax`) and `stability-heat.png` (`:34-35`). No car/scene hardcoding. |
| `mkjob3.py` | `mkjob3.py <dir> <look-json> <offsets> [w h spp]` (`:3-5`; offsets accept `0-95` or `40,60`; defaults 1920 1080 192). Writes `<dir>/proof.json` with `total_frames 240`, fps 24, CYCLES and the supplied `look` dict (`:6-8`). **This is the only supported way to hand `render_snapshot.py` a `look` override.** Hardcodes the Manthey car + `rainy_courtyard`. |
| `encode_clip.py` | `py encode_clip.py <proof dir> [fps=24]` (`:5`). Writes `clean.mp4` (crf 12, no grain, `:7`) and `graded.mp4` (the same vignette/noise/lutyuv chain and 20 Mbps target as `pipeline.encoding_settings`, `:8-10`). Needs `ffmpeg` on PATH — unlike the others it does not use `discover_dependencies`. |
| `alias_probe.py`, `flicker_metric.py`, `motion_ab.py`, `crop.py`, `stack.py` | Ad-hoc measurement/figure helpers from past passes. `flicker_metric.py` is explicitly retired for handheld shots: "does not work under the handheld camera… Kept only for locked or rail shots" (work_state.md:79). |
| `film_camera_v6_backup.py` | Dead code — the pre-v7 operator, kept for reference (work_state.md:51). Nothing imports it. |

---

## 3. `rain_look.LOOK` — every key

Defined at `rain_look.py:18-133`. `configure()` (`:136`) raises on an unknown
key, so a typo in a CLI `look` object fails loudly. **API jobs cannot set any of
these** (`look` is not in `SPEC_FIELDS`).

"Safe to randomise" below means: varying it within the range changes the picture
without breaking a contract test or a physical relationship. "Fixed" means a
contract asserts it, or changing it invalidates the measured look.

| Key | Default | Drives | Randomise? |
|---|---|---|---|
| `exposure` | `-0.30` | `render_snapshot.main` `:238` → `scene.view_settings.exposure` | Safe, ±0.3 stop. Sets the mood; the sky stays at captured brightness. |
| `view_look` | `'AgX - High Contrast'` | `render_snapshot.main` `:178` | **Fixed.** The comment (`:20-24`) records the measurement: Medium High Contrast + positive veil read black paint as charcoal against the owner's reference frames. |
| `world_saturation` | `.85` | `rain_look.environment` `:262` | Safe, .75–.95. |
| `plate_saturation` | `.80` | `rain_look.environment` `:267` (backdrop + projected ground) | Safe, .7–.9. |
| `plate_value` | `1.0` | `rain_look.environment` `:267` | Safe, .85–1.05. |
| `foliage_saturation` | `.80` | `rain_look.environment` `:275` | Safe, .7–.95. |
| `foliage_value` | `.85` | `rain_look.environment` `:275` | Safe, .75–1.0. |
| `haze_density` | `.0014` | `rain_look.environment` `:314` (÷ `scale`) | Safe, .0008–.0025. Thin scatter around the car. |
| `fog_density` | `.0040` | `rain_look.distance_fog` `:393,433`; `<= 0` removes the layer | Safe, .002–.006. Was .0048 before the depth belts (work_state.md:53). |
| `fog_clearance` | `1.5` | `rain_look.distance_fog` `:409` — metres added to the farthest camera keyframe to size the clear pocket | Keep ≥ 1.0; below that the fog can reach the car. |
| `falling_rain` | `False` | `render_snapshot.main` `:190` — gates `rain_atmosphere.build` and the ripple clock | Boolean art decision, not a randomisable knob. Off = "after the rain". |
| `rain_size` | `2.3` | `rain_atmosphere.build(size=…)` `:193` | Safe 1.5–3.0 **when `falling_rain`**. A physical 1 mm drop is a third of a pixel at 1080p (`:44-47`). |
| `rain_reach` | `1.7` | `rain_atmosphere.build(reach=…)` `:193` | Safe 1.3–2.0. Below ~1.5 the operator walks outside the field (11 m out). Drop count scales with reach². |
| `rain_backlight` | `2.5` | `rain_atmosphere.build(backlight=…)` `:194` | **Fixed** — `check_surface_materials`/contracts assert the rain-only lamp exists, and work_state.md:4 measured ×400 changing nothing because `sample_clamp_indirect = 5` caps it. Changing it does not change visibility. |
| `rain_glow` | `1.1` | `rain_atmosphere.build(glow=…)` `:194`, and `drips(glow=LOOK['rain_glow']*.4)` `:220` | Safe 0.8–1.5. Above ~3.0 streaks become hard white lines (work_state.md:4). This, not the backlight, is what makes rain visible. |
| `ripple_depth` | `5.0` | `render_snapshot.main` `:199` — multiplies the ripple bump `Distance` | Safe 3–8 when rain is on. |
| `ripple_scale` | `1.0` | `render_snapshot.main` `:199,203-208` — scales ring reach up, envelope sharpness and wave number down | Safe 1–2.5. Needed for low cameras: at 27 mm wavelets the bump node's pixel derivatives average the rings away. |
| `drips` | `70` | `render_snapshot.main` `:217-219` → `rain_atmosphere.drips(count=…)` | Safe 0–200. `0` removes the system. |
| `drip_size` | `1.0` | `rain_atmosphere.drips(size=…)` `:219` | Safe 0.8–1.8 (multiplies a 1.7–2.6 mm bead radius). |
| `wind` | `1.0` | `wind.apply(strength=…)` `:221` | Safe 0–1.5. `0` is still air. |
| `wind_canopy` | `False` | `wind.apply(canopy=…)` `:221` | **Leave False by default.** Measured: 27 GB vs 6.8 GB Blender memory and ~+10 s/frame, because each displaced court tree becomes a unique 900k-vertex mesh with its own BVH (work_state.md:26, 42). |
| `strip_energy` | `0.0` | `rain_look.environment` `:285,296` — gates the three studio strips | **Fixed at 0.** `check_surface_materials.py:173` asserts `== 0`. The owner saw the A/B and preferred the unlit look (work_state.md:28). |
| `drl_emission` | `240.0` | `rain_look.lamps` `:457`, `animate_lamps` `:473` | Safe 150–350. Below ~100 the DRL reads as a painted line under an overcast sky (`:68-72`). |
| `drl_color` | `(.80,.89,1.0)` | `rain_look.lamps` `:456` | Safe within a 5500–6500 K white. |
| `tail_emission` | `95.0` | `rain_look.lamps` `:457` | Safe 60–140. |
| `tail_color` | `(1.0,.030,.012)` | `rain_look.lamps` `:456` | **Near-fixed.** Deliberately not pure red so it brightens toward orange-pink instead of clipping (`:70-72`). |
| `lamp_per_shot` | `(1.0,1.0,1.0,.16,.55)` | `animate_lamps` `:473`, indexed by `film_camera.shot_at` | **Fixed length = 5.** A different shot count breaks this tuple. The .16 keeps headlight-macro optics readable. |
| `key_diffuse` | `.12` | `rain_look.environment` `:290` | Inert while `strip_energy == 0`. |
| `key_per_shot` | `(1.0,.38,.65,.045,.30)` | `animate_reflections` `:577`; read by `check_film_cuts.py:29` | **Fixed length = 5**, and the contract reads it. |
| `car_apron` | `.12` | `render_snapshot.main` `:151` → `rain_scene.car_apron(depth=…)` | Safe .08–.25. `.40` was rendered and not adopted (work_state.md:8). |
| `veil` | `-.0015` | `rain_look.compositor` `:348` — scene-linear lift | **Fixed.** Set against the owner's reference frames; positive is veiling glare, negative sets the black point. |
| `bloom` | `.09` | `rain_look.compositor` `:357` (Fog Glow strength) | Safe .05–.15. |
| `halation` | `.05` | `rain_look.compositor` `:368-374`; `0` removes the node entirely | Safe 0–.12. |
| `filter_width` | `1.95` | `rain_look.compositor` `:380` → `scene.cycles.filter_width` | Safe 1.5–2.2. 1.5 is the CG default; ~2 also calms shimmer on grilles and spokes. |
| `distortion` | `.006` | `rain_look.compositor` `:362` | Safe 0–.012. |
| `adaptive_threshold` | `.025` | `render_snapshot.main` `:227` | **Inert at current settings** — measured identical at .01 and .005 because pixels already run to the sample cap (work_state.md:68). |
| `seed` | `20260915` | `render_snapshot.main` `:229` | **Fixed for a film**; vary only for the two-seed probe. |
| `animated_seed` | `False` | `render_snapshot.main` `:237` | Open owner decision (work_state.md:82). False glues the noise to the screen; True redraws it per frame for the grain to absorb. |
| `denoise` | `None` | `render_snapshot.main` `:230-231`; `None` leaves Blender's value alone | Probe only. Measured: no denoiser = 4.91 mean luma diff vs 1.10 (work_state.md:71). |
| `denoiser` | `None` | `render_snapshot.main` `:232-233` | Probe only. OptiX measured *worse* than OpenImageDenoise (work_state.md:70). |
| `denoise_prefilter` | `None` | `render_snapshot.main` `:234-235` | Probe only. |
| `freeze_camera` | `None` | `render_snapshot.main` `:257-261` — holds the camera at this film offset | **CLI probe only** (see comment `:116-117`). |
| `probe_camera` | `None` | `render_snapshot.main` `:262-284` | **CLI probe only.** Dict of `{from, to, aim, aim_to, lens, fstop}` in metres from the car centre on the road (`:119-122`). |
| `shot_exposure` | `(-0.10,0.25,0.55,0.30,0.05)` | `animate_exposure` `:551`; read by `check_surface_materials.py:193` | **Fixed length = 5**, contract-read. Per-setup metering; the wheel sits in the arch's shade. |
| `wheel_reflector` | `38.0` | `rain_look.wheel_reflector` `:500,506`; `<= 0` removes the board | Safe 20–60. Contract-read (`check_surface_materials.py:193`). Exists only during shot index 2 (`animate_exposure` `:557`). |
| `road_film` | `1.0` | `road_weathering.apply` via `LOOK` `:155` | Safe 0–1.5. `0` removes the layer. |
| `brake_dust` | `.9` | `road_weathering.apply` via `LOOK` `:155` | Safe 0–1.2. |
| `cabin_fill` | `7.0` | `rain_look.cabin_fill` `:521,526`; `<= 0` removes the practical | Safe 3–12. Invisible to camera, glossy and transmission rays (`:531-533`). |

**Stale comment:** `rain_look.py:106` points at
`checks/claude-pass/seed_diff.py`. That file does not exist; the script is
`checks/claude-pass/seed_probe.py` (as README:65 says).

**Tuple-length coupling:** `lamp_per_shot`, `key_per_shot` and `shot_exposure`
are each indexed by `film_camera.shot_at()`. They are hard-coupled to
`len(film_camera.SHOT_NAMES) == 5`.

---

## 4. Contracts

All `check_*.py` run **inside Blender**, CPU-only, and never load or save a
production scene except where noted. The command line (README:80-82):

```powershell
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python tools/render-studio/<check>.py
```

`check_rain_motion.py` and `check_film_cuts.py` additionally accept an optional
JSON report path after `--`.

| Check | Invariant | Scope / output |
|---|---|---|
| `check_surface_materials.py` (60 asserts) | Calibration mutates **no** Base Color (`:39`); gloss paint gains linked Coat Normal + Coat Roughness, matte does not (`:40-42`); an unknown authored material gains **zero** nodes (`:43`); `mv-window-tint` keeps Alpha 1 / Transmission 0 (`:44`). `thin_lens` refuses partial alpha and refuses an authored Volume output (`:50,:55`). `rotor_face_normals` repairs exactly **2** flat disc faces, moves no vertices, leaves wall normals within `1e-4` (`:99-107`). `rain_look.car_materials` yields exactly `['lightly-tinted-window','muted-yellow-lacquer']` and is **idempotent** (`:137,:147`); blue/flat/metallic/texture-mapped paints untouched (`:140-142`). `LOOK['strip_energy'] == 0` (`:173`); with no strips there are **no LIGHT objects at all** (`:181-182`). Per-shot exposure keys match `LOOK['shot_exposure']` within `1e-6` at all 144 frames; the wheel board is energised on **shot 2 only** within `1e-4`; changes land at subframes `-.75`/`-.25` and every key is `CONSTANT` (`:188-210`). | Synthetic objects + the real `MANTHEY_992` path (`:69,:82,:136`). No argv, writes nothing. Hard-bound to the rainy look — it calls `rain_scene.environment`/`rain_look.environment` directly. |
| `check_wet_surfaces.py` (47 asserts) | Dry pass selects exactly **4** tyres, adds no detail objects, and SHA256 vertex/loop fingerprints are unchanged (`:47-52`). Wet pass molds `'PERFORMANCE / ROAD TIRE'` on 4 objects, every vertex inside the tyre bbox ±`.002*scale`, geometry still unchanged (`:61-73`). Beads: **20000 < count < BEAD_LIMIT** (38,037 measured on this GLB, `:87`), mist share in (.31,.37), merged+runoff in (.025,.045) (`:94-96`); water IOR `1.333±1e-5`, transmission 1 (`:121-122`); vertical-panel runoff aligns with gravity `dot > .999` (`:145`). Road graph: Coat Weight spans exactly **.62 → .88** dry and 1 pooled, pooled roughness ≤ .005, `film < stone < 1` (`:230-241`); ripple time linear in subframes within `1e-5` (`:243-250`). | Imports `checks/black-final/snapshot.glb` read-only (`:35`); hardcodes the `4.8` scale divisor (`:39`). No argv, writes nothing. |
| `check_puddle_fields.py` (21 asserts) | Bakes real `wet_asphalt()` sockets through a 1-sample CPU Cycles emission render (orthographic, 32-bit EXR). **Harness self-check first**: baked world X/Y must match pixel centres within 0.01 px (`:136`) — only then is any measurement trusted. Mask is bit-identical at t=0 and t=.6, so ripples never move pools (`:141`). Coverage: court flooded share in (.20,.45), damp > .50 (`:147-149`); largest pool > 3 m², at most 12 pools ≥ .5 m² (`:154`). Shorelines: real crossings must exceed **3×** plain-noise crossings overall and 1.5× in every window with the scanned relief flattened (`:199-200`). Ripples confined: height > .05 in water, stray < `1e-6` outside standing water (`:229`). Pool optics flat: Coat Weight > 1−1e-6, roughness ≤ .005 (`:243-246`). | Car-free — builds a plane with `wet_asphalt(1)`. Windows/court metres (`:30-31`) are sized to this courtyard. Renders into a `TemporaryDirectory` (`:254`); no persistent output. |
| `check_road_weathering.py` (41 asserts) | Strength 0 removes both layers and leaves node counts unchanged (`:105-107`). Exactly 1 shared mask group (`:119`); the film applies iff the material name starts `mv-unified-paint`/`mv-carbon-weave` without `interior`, or is a `mv_rain_look` trim (`:125-127`); glass, lenses, rubber, rims and tyres are excluded (`:142`). **Spray envelope, evaluated by re-implementing the node math**: zero at roof height and at 1.0 m on the flank, > .6 at .12 m sill height, > 2× behind a wheel vs ahead, > 3× tail vs nose, all in [0,1] (`:162-169`). Flake gate: platelets exist only for metallic ≥ .6 with coat 1, feed `Normal` not `Coat Normal`, size .0002–.0005 m (`:223-232`). Second apply is a no-op; geometry fingerprints intact (`:148-150`). | `CAR = MANTHEY_992` (`:26`), same baseline GLB (`:40`). No argv, writes nothing. |
| `check_rain_motion.py` (10 asserts) | `interceptedColumns > 0`, `temporalWrap is False` (`:49-50`); the rain backlight's receiver collection is **exactly** the droplets (`:54`); water IOR `1.333±1e-5`, transmission 1 (`:56-57`); instance identity/topology unchanged across frames .75, 1, 1.25, 60.125, 144, 144.25 (`:63-65`); every drop's displacement matches **−6.5 m/s** with error `< 2e-5 * scale` (`:68-70`); no visible drop inside the collider or below ground (`:78-79`). | Purely synthetic cube collider — no car, no GLB, no scene file. **Takes an optional JSON path after `--`** (`:33-36`); otherwise writes `checks/black-rain-final/rain-motion-contract.json` with a sha256 of `rain_atmosphere.py`, and prints `REPORT <path>`. |
| `check_film_cuts.py` (8 asserts) | Motion blur on, `CENTER`, shutter `.5`, `rolling_shutter_type NONE` (`:66-69`); animated integer-frame poses match `film_camera.pose()` within `1e-5` (`:76`); across shutter fractions ±.25/±.125/0 at every cut the camera never interpolates toward another shot (`< 1e-5`) and light energy stays at `base * LOOK['key_per_shot'][shot]` (`< 1e-4`) (`:102-103`); the switch lands in the closed-shutter gap — energies at `.49/.50/.51` past the outgoing frame equal the correct side within `1e-4` (`:110`). Runs three cases including a 12-frame 180×320 smoke case (`:130`). | Synthetic bounds and lights. **Optional JSON path after `--`** (`:125-128`); default report `checks/black-rain-final/film-cut-contract.json` with sha256 of `film_camera.py`, `rain_look.py`, `render_snapshot.py` (`:136-137`). |

**Retargeting cost:** four of the six are hard-bound to `MANTHEY_992` and/or
`checks/black-final/snapshot.glb`. Only `check_rain_motion.py` and
`check_film_cuts.py` are car-free and scene-file-free, and even those assume the
rain look's object names. **None of the six accepts a car or scene argument** —
covering a new scene means writing a new check, not parameterising an old one.

The `test_*.py` files are plain unittest and run outside Blender (README:76):

```powershell
python -m unittest discover -s tools/render-studio -p 'test_*.py' -v
node --test "js/render-studio/*.test.js"
```

- `test_server.py` (331 lines) — local-origin and Host restrictions, request
  size, canonical presets for every preset × scene × aspect combination
  (`:216-217`), embedded-GLB validation, byte ranges, queue persistence,
  retries, and cancellation races against a fake pipeline.
- `test_pipeline.py` (67 lines) — dependency discovery, cancellation without a
  real render, and `encoding_settings` per resolution and scene (`:19-26`).
- `test_dev_injection.py` (40 lines) — that the dev server injects
  `bootstrap.js` and the public build does not.

work_state.md reports "pytest 26 passed" as the current count (2026-09-17,
lines 46 and 84).

---

## 5. The three scenes, and how to add a fourth

### How they differ

There is no scene registry. The dispatch is two booleans in
`render_snapshot.main()`:

```
rainy = job.get('scene') == 'rainy_courtyard'   # :121
night = job.get("scene", "turntable") == "night_garage"   # :126
```

- **`turntable`** is the *default path*: the four-softbox studio rig
  (`:140-143`), a large grey floor plane (`:134-137`), a flat world colour
  (`:130-131`), and the per-frame circular orbit at 17° elevation
  (`:254,303-306`). No compositor, no fog, `exposure = 0` (`:238`).
- **`night_garage`** is *the same code path with four numbers changed*: darker
  world colour and strength (`:130-131`), darker/rougher floor (`:137`), a
  cooler and weaker fill plus a warm rear rim (`:141,143`), and 13° elevation
  instead of 17° (`:254`). Nothing else differs. Its `SCENES` description ("a
  slow orbit with dramatic garage lighting", `jobs.py:36`) oversells it — the
  orbit speed is identical.
- **`rainy_courtyard`** tears the studio down (`:147-149`) and builds an
  entirely different world: `rain_scene`, `rain_look`, `road_weathering`,
  `rain_atmosphere`, `wind`, `scene_plants`, the `film_camera` operator instead
  of an orbit, the compositor, distance fog, per-shot metering, and a
  scene-specific ffmpeg filter chain in `pipeline.encoding_settings:159`.

### What a fourth scene must provide

A scene is currently *not* a module — it is a branch. To add
`sunset_canyon` (say):

1. **Register it.** Add a dict to `jobs.SCENES` (`jobs.py:33`) **and** to
   `SCENES` in `js/render-studio/config.js:12`. Both lists are hand-maintained
   copies; miss one and the UI and the API disagree.
2. **Branch in `render_snapshot.main()`.** Add a flag next to `rainy`/`night`
   (`render_snapshot.py:121-126`) and guard your scene build the way the rain
   branch does at `:146-160`. Note the ordering constraint: your build must run
   *after* `component_materials.prepare` / `calibrate_materials` /
   `tire_sidewalls` (`:123-125`), because those set up the materials your scene
   then decorates, and *before* `pick_engine` (`:222`) if you need engine
   settings.
3. **Tear down what you do not want.** The studio floor and four lights are
   created unconditionally at `:134-143`. Rain deletes them at `:147-149`. Any
   new scene must do the same or inherit them.
4. **Lighting** — a world, or an HDRI. `rain_scene.hdri_path()` (`:14`) is the
   pattern: pin the file in `assets/manifest.json`, add it to
   `prepare_assets.py`, and load it through `bpy.data.images.load(...,
   check_existing=True)` (`rain_scene.py:308`).
5. **Camera programme** — either reuse the orbit (do nothing; `:303-306` runs
   for every non-rainy scene) or write your own `animate()` and call it at
   `:255`. If you write your own multi-shot programme you need your own
   `SHOT_NAMES`/`SHOT_BOUNDARIES`; `film_camera`'s are a module-level constant
   (`film_camera.py:8-9`), not a parameter.
6. **Ground** — the studio plane (`:134`) or your own mesh.
7. **Materials** — `calibrate_materials(wet=…)` already takes a wetness flag;
   anything more specific needs its own module, following
   `road_weathering.py`'s example of being car-agnostic rather than
   `component_materials.py`'s of being car-scoped.
8. **Contracts** — add a `check_<scene>.py` that runs CPU-only in Blender and
   asserts geometry is unchanged, scope is respected, and nothing lands inside
   an exposed subframe. Add its command to README:80-82.
9. **Delivery** — if your scene needs its own grain/vignette, extend
   `encoding_settings` (`pipeline.py:159`) rather than hardcoding a second
   equality test.

### What will bite you (hardcoded values)

- `rain_look.LOOK` is a **module-level singleton**, mutated in place by
  `configure()` (`rain_look.py:140`). A second scene with its own look dict
  cannot coexist with it in one process without either a namespacing scheme or
  a per-scene dict.
- `render_snapshot.py` reads `rain_look.LOOK['view_look']` and
  `LOOK['exposure']` for the rainy branch only (`:178,238`); a new scene gets
  the hardcoded `"AgX - Medium High Contrast"` and exposure 0 unless you add a
  branch.
- `pipeline.encoding_settings` tests the literal string `'rainy_courtyard'`
  (`:159`). Every future scene that wants grain adds another `or`.
- `component_materials.MANTHEY_992` (`:11`) gates all component work to one car
  id; `rain_look.car_materials` does the same (`:174`). A new scene inherits
  those gates, which means a non-Porsche car gets no component treatment in any
  scene. The generic baseline every car DOES get (2026-09-18): paint / carbon /
  privacy-glass / lamp-lens / rubber calibration decided by
  `material_classes.classify` from the material name AND the `mvSlot` tag the
  site writes on every exported mesh (three naming families ship: runtime
  `mv-*`, authored `MV_*`, raw artist names — only the slot tag reaches the
  third), an alpha-blended lens converted to transmissive glass before
  `thin_lens`, and camera anchors (`film_camera.anchors`) that find the
  camera-side wheel and headlight by slot tag, ranked by how far outboard and
  forward the part sits (a fender-wide alias no longer wins by size). Every
  render logs an `ANCHORS {...}` line naming the chosen parts.
- `film_camera.SHOT_BOUNDARIES` (`:9`) and the three 5-tuples in `LOOK` are
  coupled by length, and `check_film_cuts.py:29` reads one of them.
- **Car orientation is assumed, not measured.** `road_weathering.py` (docstring
  `:57`) and `film_camera.py` (docstring `:67`) both require the nose at −Y and
  the camera side at +X. `rain_atmosphere.drips` assumes the outward direction
  is radial from the car centre (`:151`). Nothing validates this.
- **Cross-module contracts are name strings, and they fail silently.**
  `wind.py:154-155` finds everything it animates by object-name prefix;
  `wet_detail.py`'s `'Rain impact time seconds'` node is reached by name from
  `render_snapshot.py:199-208`; `rain_scene.py`'s `'Car apron depth'` nodes are
  read back by `car_apron()`. A rename gives you a zero-count report, not an
  error.
- **Module-global state survives between scenes in one process:**
  `rain_look.LOOK`, `film_camera._TAKES` (`:132`) and
  `scene_plants.plant_tree.planted` (`:115`). A process that builds two scenes
  will leak.
- `rain_scene.PUDDLE_LEVEL = 0.69` (`:69`) is calibrated against the exact sum
  of its three height terms, and the HDRI rotation `radians(110)` is written out
  three separate times (`:257`, `:283`, `:306`).
- `main()` in `render_snapshot.py` is a single ~240-line function. Scene four
  will make it worse; consider extracting a `scenes/` package with a
  `build(scene, ctx)` protocol before adding one.

---

## 6. Measured costs

Every figure below is quoted from `work_state.md` or `README.md` with its stated
population and date. Nothing here was re-measured.

**Stability study — 2026-09-17, all 1080p, Manthey 992 snapshot, film offsets 60
(wide) and 190 (headlight), display levels 0–255** (work_state.md:64-77):

| Configuration | Two-seed luma diff mean / p99 / % pixels > 5 levels (wide, then headlight) |
|---|---|
| base 192 spp | 1.10 / 7.0 / 2.15 and 1.19 / 7.4 / 3.10 |
| adaptive threshold .01 and .005 | 1.01 / 6.9 / 2.02 and 1.10 / 7.3 / 3.00 (identical — threshold inert) |
| 384 spp | 1.01 / 5.9 / 1.46 and 1.05 / 6.1 / 1.84 |
| 768 spp | 0.99 / 5.3 / 1.21 and 0.97 / 5.1 / 1.23 |
| OptiX denoiser | 1.41 / 9.0 / 3.45 and 1.67 / 11.8 / 7.09 (worse) |
| no denoiser | 4.91 / 19.1 / 38.5 and 4.98 / 23.3 / 36.2 |
| 3840×2160 @ 192 spp, box-downsampled | 0.79 / 4.7 / 0.75 and 0.79 / 4.9 / 0.81 (best) |
| 2880×1620 @ 192 spp, box-downsampled | 0.90 / 5.5 / 1.21 and 0.94 / 5.9 / 1.51 |

Locked camera, 8 consecutive frames, 192 spp (`temporal_stability.py`): wide
sigma mean .023 / p99 .53; headlight .003 / .054 — "a still camera is already
stable" (work_state.md:65).

**Wall time**, two-frame job including scene build (work_state.md:75):
1080p **49 s**, 1620p **103 s**, 4K **175 s**. Film estimates for 240 frames:
**1.5 h / ~3.2 h / ~5.8 h**.

**Per-frame, measured on real runs:**

- 3840×2160, 192 spp: **87 s/frame**, Blender **16 GB**, about **6.3 h**
  (2026-09-17 evening, work_state.md:31).
- 1920×1080, 192 spp, `falling_rain` true, wind on, canopy flutter off:
  **29 s/frame**; 36,550 drops, 94 belt trees, 87 loose leaves — run `a1`,
  96 frames (2026-09-17 night, work_state.md:17).
- 1920×1080, 192 spp, close probe clip `r5`, offsets 0–95: **about 40 s/frame**
  (2026-09-17 night, work_state.md:8).
- 640×360, 20 spp motion test: **~2 s/frame** before wind, **~11.5 s/frame**
  after; expected 1080p cost of wind is "roughly 10 s per frame"
  (2026-09-17 late afternoon, work_state.md:42).

**Memory** (2026-09-17 evening, bisected at one frame, 4K, work_state.md:26):
no wind **7.0 GB**; wind without canopy flutter **6.8 GB**; **with flutter
27 GB** — which killed a 4K attempt that reached **37 GB on a 31 GB box**. Each
displaced court tree becomes a unique 900k-vertex mesh with its own BVH. This is
why `LOOK['wind_canopy']` defaults False.

**Completed API jobs** (older, 1280×720 / Cycles 96 / 144 frames / 6 s):
508.8 s (work_state.md:130), 755.86 s (`:109`), 903.4 s (`:118`). At 1080×1920
Cycles 192: 18.6 Mbps, 13,952,727 bytes (`:90`).

**Preview-quality warning** (work_state.md:25): "the 640x360 / 20-sample motion
tests leave 3.6 levels mean uncertainty, 21 % of pixels over 5 levels; final
settings (1080p / 192) leave 1.0 to 1.4 mean, 1.4 to 3 % over 5. … Do not send
20-sample previews for judging anything but camera path again."

**`jobs.estimate` fallbacks** (`jobs.py:283`) are *not* measurements — they seed
the estimate until a job of that preset completes: smoke 0.5, draft 0.8,
film_preview 7, film_final 18, standard 20, cinematic 30, 4k 50 s/frame. The
film_final figure of 18 s/frame is well below the 29–40 s/frame actually
measured for rainy 1080p runs above, and the 4k figure of 50 is well below the
measured 87.

---

## 7. Security posture

As written in the README and enforced in code:

- **Loopback only.** The socket binds `127.0.0.1` (`server.py:29`). README:3:
  "The service binds to `127.0.0.1` and only permits HTTP pages on localhost,
  127.0.0.1, or ::1."
- **Host header pinning.** Exactly one `Host`, matching the bound port
  (`server.py:51-52`) — a DNS-rebinding defence.
- **Origin allow-list.** `ORIGIN_PATTERN` (`server.py:16`) admits only `http://`
  loopback origins with a valid port; multiple `Origin` headers are refused
  (`:53-59`); CORS is echoed only for an origin that passed (`:69-71`).
  Preflight allows only GET/POST/DELETE and only `content-type`/`range`
  (`:136-140`).
- **Request size.** 128 MiB body cap (`jobs.py:19`, `server.py:121-122`),
  ~96 MiB of model data after base64 (README:35); the browser refuses at 90 MB
  of GLB first (`snapshot.js:76`). No chunked bodies (`server.py:115-116`);
  exactly one numeric `Content-Length` or 411 (`:117-119`).
- **Embedded resources only.** A snapshot referencing an external file or URL is
  rejected (`jobs.py:131-133`). README:35: "Very large or externally referenced
  models are rejected with an explanation."
- **What API jobs cannot set.** `SPEC_FIELDS` (`jobs.py:39`) is an allow-list,
  so the internal CLI-only fields are unreachable over HTTP:
  - `look` — the whole `rain_look.LOOK` override object. README:43: "a CLI proof
    job may override keys through a `look` object, and API jobs cannot."
  - `proof_offsets` — render only selected frames (`render_snapshot.py:291`).
  - `save_blend` — write `scene.blend` (`render_snapshot.py:292`).
  README:59: "Internal proof fields are intentionally rejected by the HTTP API."
  Additionally, any client-supplied `resolution`, `fps`, `samples`, `engine`,
  `duration_s`, `frame_start`, `frame_end` or `total_frames` that disagrees with
  the preset is rejected rather than honoured (`jobs.py:95-98`).
- **Path containment.** Job ids must be 32 lowercase hex (`jobs.py:23`); every
  directory is re-resolved and checked to be a direct child of `out/`
  (`jobs.py:163-169`). `_file` serves only three fixed filenames
  (`server.py:17,252`).
- **Blender runs sandboxed-ish**: `--factory-startup --disable-autoexec`
  (`pipeline.py:195`) — no user config, no auto-run scripts from the .blend.
- **Windows port hijack defence**: `allow_reuse_address = False` +
  `SO_EXCLUSIVEADDRUSE` (`server.py:22-24,32-34`).
- **Never shipped.** The feature is injected only by the dev server
  (`server.py:360-361`, repo root) and `MV_RENDER_STUDIO=off` hides it.
  `scripts/build-public.mjs:45-46` prunes `js/render-studio` and
  `css/render-studio.css` and treats `tools` as FORBIDDEN. README:29 and the
  project rule that `server.py` never faces the internet both apply.
- **No cloud, accounts or payments.** README:3. The `previewPrice` values in
  `PRESETS` (`jobs.py:25-31`) are display-only — nothing charges
  (README:33: "Price figures are previews; no charge is made").
