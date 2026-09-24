# Director Layer Phase 2 — Compiler, First T3 Blocks, Preview Tier, Eval Harness v0

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a checked `valora.scene/1` script into a real Blender/Cycles render. Add the first
blocks that can reach T3 (a professional ad), a fast preview tier, and an eval harness that scores
key frames against `research/craft/TIERS.md`. The harness only reports: no score blocks a render yet.

**Architecture:**

- `engine/` stays stdlib-only and importable inside Blender's bundled Python.
- **Pure maths lives in `engine/`**: the reflection solver, the camera timeline, easing, the edit
  rules and grade plans. The checker (host) and the compiler (Blender) call the same functions, so
  what is checked is what renders.
- **Blender-only code lives in two places:** `engine/blender/` (shared helpers) and each block's
  `build.py`. A `build.py` imports `bpy` *inside* `build()`, so the catalog can load it outside
  Blender.
- The compiler is a host runner (`engine/compiler/run.py`). It checks the script, then launches
  headless Blender on `engine/compiler/blender_main.py` with a job JSON.
- The eval harness is a separate top-level package `harness/`. It may use numpy, Pillow and
  scikit-image; it is never imported inside Blender.

**Tech Stack:** Python 3.12 (dev) / Blender 5.0 bundled Python 3.11. `engine/` is stdlib only.
`harness/` uses numpy 2.x, Pillow, scikit-image (all installed in the dev `py`; listed in
`harness/requirements.txt`). pytest 8, ffmpeg 8 (for cut detection and preview encodes). Blender
5.0 at `C:\Program Files\Blender Foundation\Blender 5.0\blender.exe` (override with `BLENDER_EXE`).

**Spec:** `docs/superpowers/specs/2026-09-24-director-layer-design.md` §2a, §4.3, §4.5, §4.7, §4.8,
§9, §10 step 2. Research inputs: `research/craft/TIERS.md`, `research/craft/CATALOG-GAPS.md`,
`research/craft/vehicles.md`, `research/craft/products.md`, `research/prior-art/PRIOR-ART.md`.
Phase 1 plan (the style this follows): `docs/superpowers/plans/2026-09-24-director-phase1-foundations.md`.

**Conventions (same as phase 1):**

- Run every command from the repo root `C:\Users\deand\Projects\rendering`, on branch
  `renderer/director`.
- Use `py`, never bare `python`; bare `python` hits a Windows Store stub.
- Fast loop: `py -m pytest engine/tests harness/tests -q -m "not blender"`.
  Full: `py -m pytest engine/tests harness/tests -q`. Baseline before this plan: **146 passed**
  with Blender installed (143 passed + 3 skipped without it).
- Each commit message ends with the two attribution lines given in the session. Run
  `git diff --cached --name-only` before every commit and stage only this plan's files. Other
  terminals share the index.
- **Render tests use a few key frames only** (at most 3 per test, tiny resolution, 4 samples).
  Never render a full sequence in a test. Full-sequence renders are manual, via the CLI.
- **The owner games on this machine.** Anything heavier than a key-frame test (full preview clips,
  the whole suite) runs only after asking the owner.
- **Blender 5.0 API names that the plan cannot verify offline** (compositor node sockets, File
  Output node, AgX look names) get a **probe step** before the code step. Use
  `mcp__blender__bpy_api_lookup` or a `--python-expr` probe. The test is the arbiter, not this
  plan's guess.

**Carry-forwards from the phase-1 final review (all folded in below):**

| Carry-forward | Where |
|---|---|
| Compiler puts the repo root on `sys.path` | Task 19 (`blender_main.py` first lines), Task 6 (extractor) |
| Place the subject from `sourceCenter` / `sourceMinZ` / `scaleFactor` | Task 19 (`place_subject` + bounds guard test) |
| Camera rotation from `geometry._basis`, never `TRACK_TO` | Task 16 (`camera_matrix`), Task 20 (projection-agreement test) |
| Posed bounds for rigged subjects | Task 6 (union over animation frames + rigged fixture test) |
| Farm containers: memory limit, no network | Task 17 (`container_argv` + `--offline-mode` on every Blender launch) |
| Render tests: a few key frames only | Conventions above; Tasks 20, 22–24, 28 |
| Director schema reserves owner "markers" | Task 3 (schema + checker), Task 12 (a detail shot can target a marker) |

---

## File map

| File | Responsibility | Task |
|---|---|---|
| `engine/catalog.py` | + `edit` kind, required `tierMax`, `load_builder()` | 1, 18 |
| `engine/easing.py` | Easing curves and end-of-move settle, shared by paths and checks | 2 |
| `engine/markers.py` | Marker shape validation, glTF→placed conversion, on-subject check | 3 |
| `engine/script.py` | + shot `purpose` / `transitionIn` / `target`, top-level `edit`, `markers` | 4 |
| `engine/profile.py` | + gloss share, reflection targets, shoulder line, detail points, wheels, parts, posed flag | 5 |
| `engine/blender/scene_io.py` | One GLB import used by ingest AND compiler (so bounds agree) | 6 |
| `engine/ingest/blender_extract.py` | + surface samples, per-object parts, posed bounds | 6 |
| `engine/ingest/measure.py` | + pure detectors: gloss, reflection targets, shoulder line, details, wheels, parts | 7–9 |
| `engine/reflect.py` | Reflection solver + `reflection_rig` layout (pure) | 11 |
| `engine/color.py` | Kelvin → RGB (pure) | 11 |
| `engine/targets.py` | Resolve a shot's detail target (marker / detail point / centre) | 12 |
| `engine/craft_rules.py` | TIERS [S] items as pure functions (checker + harness share them) | 13 |
| `engine/sequence.py` | `sequence` edit-block enforcement + repairs in the checker | 13 |
| `engine/grade_plan.py` | Pure grade plans for `neutral_film` / `mood_grade` | 14 |
| `engine/softbox.py` | Pure `softbox_three_point` layout (same LightSpec realiser) | 21 |
| `engine/checker.py` | + markers, targets, detail framing, sequence stage | 3, 12, 13 |
| `engine/geometry.py` | + `camera_matrix`, `focus_depth` | 16 |
| `engine/compiler/timeline.py` | Frame keys, cuts in the closed-shutter gap, key frames (pure) | 16 |
| `engine/compiler/tiers.py` | Render tiers `keyframes` / `preview` / `final` (pure data) | 17 |
| `engine/blender_cli.py` | Blender path + safe launch flags (`--offline-mode` etc.) | 17 |
| `engine/compiler/sandbox.py` | Farm container argv: no network, memory cap (pure) | 17 |
| `engine/compiler/context.py` | `BuildContext`, per-block seeds, hero pose | 18 |
| `engine/compiler/blender_main.py` | Runs in Blender: place, build blocks, camera, passes, render | 19–24 |
| `engine/compiler/run.py` | Host: check → job JSON → Blender → results | 19 |
| `engine/blender/lights.py`, `engine/blender/grade.py`, `engine/blender/render.py` | Blender realisers shared by blocks | 21–24 |
| `engine/blocks/**` | New: `lighting/reflection_rig`, `camera/macro_detail`, `edit/sequence`, `grade/mood_grade`, `effect/haze_volume`; `build.py` for every non-camera block | 1–2, 11–15, 21–23 |
| `engine/__main__.py` | + `py -m engine render …` | 24 |
| `engine/tests/conftest.py` | `blender` marker, `requires_blender` | 6 |
| `engine/tests/blender_fixtures.py` | Scripts that generate tiny test GLBs inside Blender | 6 |
| `harness/` | Eval harness v0: item registry, thresholds, metrics, scoring, suite runner, calibration | 25–29 |

---

## Chunk 1: Manifest and schema foundations (pure, no Blender)

### Task 1: `tierMax` and the `edit` kind in the block manifest

Spec §2a: every block records the highest tier it supports. CATALOG-GAPS §2 adds an `edit` kind
for sequence templates and transitions.

**Files:**
- Modify: `engine/catalog.py` (constants at top, `_REQUIRED`, `_check_types`)
- Modify: all six `engine/blocks/*/*/block.json` (add `tierMax`)
- Test: `engine/tests/test_catalog.py`

- [ ] **Step 1: Write the failing tests** — in `engine/tests/test_catalog.py`, change the first
  test's kinds assertion and `_base`, then add two tests:

```python
def test_loads_starter_blocks():
    cat = Catalog.load()
    assert set(KINDS) == {"world", "lighting", "camera", "motion", "effect", "grade", "edit"}
    assert cat.get("world", "studio_cyc")["hasGround"] is True
    assert cat.get("camera", "arc_orbit")["framing"] == "full"
    assert cat.get("world", "moon") is None
    assert {"arc_orbit", "low_hero_push"} <= set(cat.ids("camera"))


def _base(bid, kind="world", **extra):
    m = {"id": bid, "kind": kind, "description": "x", "params": {},
         "subjectSizeM": [0.1, 1.0], "aspects": ["9:16"], "costWeight": 1.0,
         "tags": {"mood": [], "energy": [], "palette": []}, "tierMax": "T2"}
    m.update(extra)
    return m


@pytest.mark.parametrize("bad", ["T5", "t3", 3, None])
def test_rejects_bad_tier_max(tmp_path, bad):
    _write(tmp_path, "world", "a", _base("a", tierMax=bad))
    with pytest.raises(CatalogError, match="tierMax"):
        Catalog.load(tmp_path)


def test_starter_tier_max_matches_catalog_gaps():
    # CATALOG-GAPS §3 "Suggested tierMax once fixed".
    cat = Catalog.load()
    want = {("world", "studio_cyc"): "T3", ("lighting", "softbox_three_point"): "T2",
            ("camera", "low_hero_push"): "T3", ("camera", "arc_orbit"): "T3",
            ("motion", "static"): "T3", ("grade", "neutral_film"): "T2"}
    for (kind, bid), tier in want.items():
        assert cat.get(kind, bid)["tierMax"] == tier, bid
```

(The `ids("camera")` assertion becomes a subset check because Task 12 adds `macro_detail`.)

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_catalog.py -q` →
  `KINDS` assertion fails, and every starter manifest fails with `missing keys ['tierMax']` once
  the next step lands (not yet).

- [ ] **Step 3: Implement** — in `engine/catalog.py`:

```python
KINDS = ("world", "lighting", "camera", "motion", "effect", "grade", "edit")
TIERS = ("T1", "T2", "T3", "T4")
_REQUIRED = ("id", "kind", "description", "params", "subjectSizeM", "aspects", "costWeight", "tags",
             "tierMax")
```

At the end of `_check_types`:

```python
    if m["tierMax"] not in TIERS:
        raise CatalogError(f"{where}: tierMax must be one of {list(TIERS)}")
```

Add `"tierMax": "<tier>"` to each starter manifest, with the values from the test above. Change
the `softbox_three_point` description to say it is T2 on glossy subjects:

```json
"description": "Classic key, fill and rim softboxes sized to the subject. Even, flattering, commercial. Azimuths are relative to the hero camera. Good on matte subjects; on glossy subjects prefer reflection_rig (this rig makes blob highlights, T2).",
```

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests -q -m "not blender"` → all pass.

- [ ] **Step 5: Commit**
```bash
git add engine/catalog.py engine/blocks engine/tests/test_catalog.py
git commit -m "feat(engine): tierMax on every block and the edit block kind"
```

### Task 2: Easing, end-of-move settle, starter param fixes

TIERS T2-03 (eased moves) and T3-13 (true stillness at the end) are script-level. Both need the
path functions to ease and to hold. The checker samples the same functions, so they stay in
agreement with the render. Also apply the CATALOG-GAPS §3 parameter fixes.

**Files:**
- Create: `engine/easing.py`, `engine/tests/test_easing.py`
- Modify: `engine/blocks/camera/low_hero_push/{block.json,path.py}`,
  `engine/blocks/camera/arc_orbit/{block.json,path.py}`,
  `engine/blocks/world/studio_cyc/block.json`, `engine/blocks/grade/neutral_film/block.json`
- Test: `engine/tests/test_camera_paths.py`

- [ ] **Step 1: Write the failing tests** — `engine/tests/test_easing.py`

```python
import pytest
from engine.easing import EASINGS, ease, settle


@pytest.mark.parametrize("name", EASINGS)
def test_easings_hit_endpoints_and_are_monotone(name):
    assert ease(name, 0.0) == 0.0 and abs(ease(name, 1.0) - 1.0) < 1e-12
    vals = [ease(name, i / 100) for i in range(101)]
    assert all(b >= a - 1e-12 for a, b in zip(vals, vals[1:]))


def test_ease_clamps_and_rejects_unknown():
    assert ease("in_out_cubic", -1) == 0.0 and ease("in_out_cubic", 2) == 1.0
    with pytest.raises(ValueError):
        ease("bounce", 0.5)


def test_settle_finishes_early_and_holds():
    assert settle(0.8, 0.2) == 1.0 and settle(1.0, 0.2) == 1.0
    assert abs(settle(0.4, 0.2) - 0.5) < 1e-12
    assert settle(0.3, 0.0) == 0.3
```

Append to `engine/tests/test_camera_paths.py`:

```python
def test_settle_frac_holds_the_camera_still_at_the_end():
    cat = Catalog.load()
    for bid in ("low_hero_push", "arc_orbit"):
        sample = cat.load_camera_path(bid)
        p = {**_defaults(cat, bid), "settleFrac": 0.25}
        assert sample(p, CAR, 0.8).position == sample(p, CAR, 1.0).position, bid


def test_paths_accept_an_ignored_target_argument():
    cat = Catalog.load()
    for bid in ("low_hero_push", "arc_orbit"):
        sample = cat.load_camera_path(bid)
        p = _defaults(cat, bid)
        assert sample(p, CAR, 0.5, None) == sample(p, CAR, 0.5)
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_easing.py engine/tests/test_camera_paths.py -q`
  → `ModuleNotFoundError: No module named 'engine.easing'`.

- [ ] **Step 3: Implement** — `engine/easing.py`:

```python
"""Easing curves shared by camera paths (checker) and the compiler. One definition, no drift.

TIERS T2-03: camera moves are eased; `linear` exists only for blocks that declare
`linearByDesign`. products.md P-C03 uses in_quad for a tension push."""

EASINGS = ("in_out_cubic", "smoothstep", "in_quad", "out_cubic", "linear")


def _clamp01(u):
    return 0.0 if u < 0 else 1.0 if u > 1 else float(u)


def ease(name, u):
    u = _clamp01(u)
    if name == "linear":
        return u
    if name == "in_quad":
        return u * u
    if name == "out_cubic":
        return 1.0 - (1.0 - u) ** 3
    if name == "smoothstep":
        return u * u * (3.0 - 2.0 * u)
    if name == "in_out_cubic":
        return 4.0 * u ** 3 if u < 0.5 else 1.0 - (-2.0 * u + 2.0) ** 3 / 2.0
    raise ValueError(f"unknown easing {name!r}")


def settle(u, settle_frac):
    """Map shot progress u to move progress so the move completes at 1 - settle_frac and then
    holds still (products.md P-E07: every move ends in true stillness). settle_frac is at most 0.5."""
    if settle_frac <= 0:
        return _clamp01(u)
    return _clamp01(u / (1.0 - settle_frac))
```

In both camera manifests add:

```json
"easing": {"type": "enum", "values": ["in_out_cubic", "smoothstep", "in_quad"], "default": "in_out_cubic"},
"settleFrac": {"type": "number", "min": 0.0, "max": 0.5, "default": 0.0},
```

Also add `"move": "dolly"` to `low_hero_push/block.json` and `"move": "arc"` to
`arc_orbit/block.json`, top level. These are CameraBench primitive names (PRIOR-ART #7); T3-11
needs them. In `arc_orbit` set the `settleFrac` default to `0.15` (CATALOG-GAPS §3
`apexHoldS`, expressed as a fraction because `sample()` never sees the shot length).

`low_hero_push/path.py`:

```python
import math
from engine.easing import ease, settle
from engine.geometry import Pose

# Floor clearance so a "ground" camera never sits inside the floor plane.
MIN_HEIGHT_M = 0.03


def sample(params, profile, u, target=None):
    cx, cy, cz = profile.center
    k = ease(params["easing"], settle(u, params["settleFrac"]))
    d = profile.radius * params["distance"] * (1.0 - params["pushFrac"] * k)
    az = math.radians(params["azimuthDeg"])
    z = max(MIN_HEIGHT_M, params["heightFrac"] * profile.sizeM[2])
    pos = (cx + d * math.cos(az), cy + d * math.sin(az), z)
    return Pose(position=pos, target=(cx, cy, cz), lens_mm=params["lensMm"])
```

`arc_orbit/path.py`: same imports; inside `sample(params, profile, u, target=None)` replace
`params["sweepDeg"] * u` with `params["sweepDeg"] * ease(params["easing"], settle(u, params["settleFrac"]))`.

Starter fixes (CATALOG-GAPS §3):
- `studio_cyc/block.json` params: add
  `"lowerHemisphereGain": {"type": "number", "min": 0.05, "max": 0.2, "default": 0.1}` (V-L06).
- `neutral_film/block.json` params: add
  `"agxLook": {"type": "enum", "values": ["none", "base", "medium_high", "high"], "default": "base"}`
  and `"separation": {"type": "number", "min": 1.0, "max": 1.2, "default": 1.0}` (V-G01, V-G04).

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests -q -m "not blender"` → all pass.
  Also, `test_valid_script_passes_for_car_and_watch_without_camera_repair` must still pass: easing
  changes intermediate samples, not the u=0 and u=1 extremes.

- [ ] **Step 5: Commit**
```bash
git add engine/easing.py engine/tests/test_easing.py engine/tests/test_camera_paths.py engine/blocks
git commit -m "feat(engine): eased camera paths with end-of-move settle; starter block param fixes"
```

### Task 3: Markers — schema, validation, glTF→placed conversion

Owner request (spec §2b): the user places markers on the model, each with its own instruction,
like Higgsfield's image-to-video keyframes. The director reads them as structured hints in phase
3. Phase 2 reserves and validates the schema now, and lets a detail shot target a marker (Task 12).
The viewer UI for placing markers is a later site phase.

Marker shape inside the script:

```jsonc
"markers": [
  { "id": "badge",
    "anchor": { "space": "gltf", "point": [0.41, 0.62, 1.93], "normal": [0, 0, 1] },
    "text": "slow macro on the badge, make it glint",
    "timeS": 3.0 }            // optional: when in the clip this should happen
]
```

- `space: "gltf"` is what the three.js viewer will send (glTF world space, Y-up, source units).
  The checker converts it to `"placed"` (metres, Z-up, subject on z = 0) and logs a repair.
- `text` is **untrusted user input**. It is bounded (≤ 280 printable characters) and is only ever
  data for the director, never code or a file path.

**Files:**
- Create: `engine/markers.py`, `engine/tests/test_markers.py`
- Modify: `engine/script.py`, `engine/checker.py`

- [ ] **Step 1: Write the failing tests** — `engine/tests/test_markers.py`

```python
import copy
import json
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.markers import gltf_to_placed
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()
CAR = SubjectProfile.from_dict(json.loads((FIX / "profile_car.json").read_text()))
BASE = json.loads((FIX / "script_valid.json").read_text())


def _script(markers):
    s = copy.deepcopy(BASE)
    s["markers"] = markers
    return s


def _m(**kw):
    m = {"id": "m1", "anchor": {"space": "placed", "point": list(CAR.center)}, "text": "glint here"}
    m.update(kw)
    return m


def _codes(r, sev="error"):
    return {i.code for i in r.issues if i.severity == sev}


def test_valid_marker_passes():
    r = check(_script([_m(timeS=3.0)]), CAR, CAT)
    assert r.ok, [i.to_dict() for i in r.issues]


@pytest.mark.parametrize("marker,code", [
    ("not-a-dict", "bad_marker"),
    (_m(id="Bad Id"), "bad_marker_id"),
    (_m(text=""), "bad_marker_text"),
    (_m(text="x" * 281), "bad_marker_text"),
    (_m(text="bell\x07"), "bad_marker_text"),
    (_m(anchor={"space": "placed", "point": [0, 0]}), "bad_marker_anchor"),
    (_m(anchor={"space": "placed", "point": [0, float("nan"), 0]}), "bad_marker_anchor"),
    (_m(anchor={"space": "screen", "point": [0, 0, 0]}), "bad_marker_anchor"),
    (_m(anchor={"space": "placed", "point": [0, 0, 0.5], "normal": [0, 0, 0]}), "bad_marker_anchor"),
    (_m(timeS=99), "bad_marker_time"),
    (_m(extra=1), "bad_marker"),
])
def test_malformed_markers_are_errors_not_crashes(marker, code):
    r = check(_script([marker]), CAR, CAT)
    assert not r.ok and code in _codes(r)


def test_duplicate_ids_and_too_many():
    assert "duplicate_marker_id" in _codes(check(_script([_m(), _m()]), CAR, CAT))
    many = [_m(id=f"m{i}") for i in range(9)]
    assert "too_many_markers" in _codes(check(_script(many), CAR, CAT))


def test_marker_off_the_subject_is_an_error():
    far = _m(anchor={"space": "placed", "point": [50.0, 0.0, 0.5]})
    assert "marker_off_subject" in _codes(check(_script([far]), CAR, CAT))


def test_gltf_point_is_converted_to_placed():
    # glTF (x, y, z) -> Blender (x, -z, y), then (v - (cx, cy, minZ)) * f.
    prof = SubjectProfile.from_dict({**CAR.to_dict(), "sourceCenter": [1.0, 2.0, 0.0],
                                     "sourceMinZ": -0.5, "scaleFactor": 0.01})
    assert gltf_to_placed([10.0, 20.0, -30.0], prof) == pytest.approx([0.09, 0.28, 0.205])
    placed = list(CAR.center)
    gltf = [placed[0], placed[2], -placed[1]]  # inverse of the importer axis swap (identity placement)
    r = check(_script([_m(anchor={"space": "gltf", "point": gltf})]), CAR, CAT)
    assert r.ok and "marker_converted" in _codes(r, "repaired")
    assert r.script["markers"][0]["anchor"] == {"space": "placed", "point": pytest.approx(placed)}
```

(`profile_car.json` uses the identity placement: `sourceCenter` 0, `sourceMinZ` 0, factor 1.)

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_markers.py -q` →
  `ModuleNotFoundError: No module named 'engine.markers'`.

- [ ] **Step 3: Implement** — `engine/markers.py`:

```python
"""Point-and-describe markers (spec §2b): user-placed anchors on the model, each with its own
instruction, fed to the director as structured hints (phase 3). Phase 2 validates them and lets
a detail shot target one. Marker text is untrusted user input: it is bounded here and is only
ever data for the director, never code."""
import math
import re

from engine.geometry import point_in_box
from engine.issues import Issue

MAX_MARKERS = 8
MAX_TEXT = 280
ANCHOR_MARGIN = 0.10
SPACES = ("placed", "gltf")
_KEYS = {"id", "anchor", "text", "timeS"}
_ID = re.compile(r"^[a-z0-9_-]{1,32}$")
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _vec3(v):
    return isinstance(v, list) and len(v) == 3 and all(_finite(x) for x in v)


def gltf_to_placed(p, profile):
    """glTF world point (Y-up, source units) -> placed metres. Blender's glTF importer maps
    (x, y, z) -> (x, -z, y); then the SubjectProfile placement formula applies."""
    bx, by, bz = p[0], -p[2], p[1]
    c, f = profile.sourceCenter, profile.scaleFactor
    return [(bx - c[0]) * f, (by - c[1]) * f, (bz - profile.sourceMinZ) * f]


def gltf_dir_to_placed(n):
    return [n[0], -n[2], n[1]]


def _marker_errors(m, seen, duration):
    if not isinstance(m, dict) or set(m) - _KEYS:
        return [("bad_marker", f"marker must be an object with keys {sorted(_KEYS)}")]
    out = []
    mid = m.get("id")
    if not isinstance(mid, str) or not _ID.match(mid):
        out.append(("bad_marker_id", "id must match [a-z0-9_-]{1,32}"))
    elif mid in seen:
        out.append(("duplicate_marker_id", f"duplicate id {mid!r}"))
    else:
        seen.add(mid)
    text = m.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT or _CTRL.search(text):
        out.append(("bad_marker_text", f"text must be 1-{MAX_TEXT} printable characters"))
    a = m.get("anchor")
    if not isinstance(a, dict) or a.get("space", "placed") not in SPACES or not _vec3(a.get("point")):
        out.append(("bad_marker_anchor", "anchor needs space placed|gltf and point [x, y, z]"))
    elif "normal" in a and (not _vec3(a["normal"]) or not any(a["normal"])):
        out.append(("bad_marker_anchor", "anchor normal must be a non-zero [x, y, z]"))
    if "timeS" in m and not (_finite(m["timeS"]) and _finite(duration) and 0 <= m["timeS"] <= duration):
        out.append(("bad_marker_time", "timeS must be inside the clip"))
    return out


def validate_shapes(markers, duration, issues):
    """Profile-free checks (script.py). Appends errors; never raises."""
    if not isinstance(markers, list):
        issues.append(Issue("bad_markers", "markers", "'markers' must be a list", "error"))
        return
    if len(markers) > MAX_MARKERS:
        issues.append(Issue("too_many_markers", "markers", f"at most {MAX_MARKERS} markers", "error"))
    seen = set()
    for i, m in enumerate(markers):
        for code, msg in _marker_errors(m, seen, duration):
            issues.append(Issue(code, f"markers[{i}]", msg, "error"))


def check_anchors(markers, profile, issues):
    """Convert glTF anchors to placed (repair) and require every anchor to sit on the subject."""
    for i, m in enumerate(markers):
        a = m["anchor"]
        if a.get("space", "placed") == "gltf":
            a["point"] = gltf_to_placed(a["point"], profile)
            if "normal" in a:
                a["normal"] = gltf_dir_to_placed(a["normal"])
            issues.append(Issue("marker_converted", f"markers[{i}].anchor", "glTF -> placed metres", "repaired"))
        a["space"] = "placed"
        if not point_in_box(a["point"], profile.boundsMin, profile.boundsMax, ANCHOR_MARGIN):
            issues.append(Issue("marker_off_subject", f"markers[{i}].anchor.point",
                                "anchor is not on the subject", "error"))
```

In `engine/script.py` (import `from engine.markers import validate_shapes as _marker_shapes`),
right after the `bad_fps` check in `validate_and_repair` add:

```python
    if "markers" in s:
        _marker_shapes(s["markers"], fmt.get("durationS"), issues)
```

In `engine/checker.py` `check()`, after the first `errors(issues)` early return:

```python
    if s.get("markers"):
        check_anchors(s["markers"], profile, issues)
```

(import `from engine.markers import check_anchors`). The test expects `anchor` to equal
`{"space": "placed", "point": …}` exactly, so `normal` stays absent when it was absent.

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests -q -m "not blender"`.

- [ ] **Step 5: Commit**
```bash
git add engine/markers.py engine/script.py engine/checker.py engine/tests/test_markers.py
git commit -m "feat(engine): point-and-describe markers in the scene schema, validated by the checker"
```

### Task 4: Shot `purpose`, `transitionIn`, `target`, and the top-level `edit` block

CATALOG-GAPS §2: per-shot `purpose` (`hook | establish | detail | motion | hero | packshot`) and
`transitionIn` let the checker enforce T3-15/T3-16. Phase 2 builds only the hard cut. Every other
transition name is **reserved**: the checker rejects it with a clear code until its block exists
(deferred, rank 8).

**Files:**
- Modify: `engine/script.py`
- Test: `engine/tests/test_script.py`

- [ ] **Step 1: Write the failing tests** — append to `engine/tests/test_script.py` (it already
  has `_script()` and `CAT`; add `import pytest` at the top if missing):

```python
@pytest.mark.parametrize("field,value,code", [
    ("purpose", "vibes", "bad_purpose"),
    ("transitionIn", "whip", "transition_not_available"),
    ("transitionIn", "teleport", "bad_transition"),
    ("target", {"marker": "a", "detail": 0}, "bad_target"),
    ("target", {"detail": -1}, "bad_target"),
    ("target", {"detail": True}, "bad_target"),
    ("target", "badge", "bad_target"),
])
def test_bad_shot_fields_are_errors(field, value, code):
    s = _script()
    s["shots"][1][field] = value
    _, issues = validate_and_repair(s, CAT)
    assert code in {i.code for i in issues if i.severity == "error"}


def test_good_shot_fields_pass():
    s = _script()
    s["shots"][0].update({"purpose": "hook", "transitionIn": "cut"})
    s["shots"][1].update({"purpose": "hero", "target": {"detail": 0}})
    _, issues = validate_and_repair(s, CAT)
    assert not [i for i in issues if i.severity == "error"]


def test_unknown_edit_block_is_an_error():
    s = _script()
    s["edit"] = {"id": "montage", "params": {}}
    _, issues = validate_and_repair(s, CAT)
    assert "unknown_block" in {i.code for i in issues}
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_script.py -q`.

- [ ] **Step 3: Implement** — in `engine/script.py`:

```python
PURPOSES = ("hook", "establish", "detail", "motion", "hero", "packshot")
TRANSITIONS = ("cut",)
# Reserved: named in the craft research, rejected until their edit blocks exist (CATALOG-GAPS rank 8).
TRANSITIONS_RESERVED = ("flash", "dark_tunnel", "focus_handoff", "black_card", "whip", "hidden_cut",
                        "mask_wipe")


def _valid_target(t):
    if not isinstance(t, dict) or len(t) != 1:
        return False
    if "marker" in t:
        return isinstance(t["marker"], str)
    d = t.get("detail")
    return isinstance(d, int) and not isinstance(d, bool) and d >= 0


def _shot_fields(i, sh, issues):
    p = f"shots[{i}]"
    if "purpose" in sh and sh["purpose"] not in PURPOSES:
        issues.append(Issue("bad_purpose", f"{p}.purpose", f"must be one of {PURPOSES}", "error"))
    tr = sh.get("transitionIn", "cut")
    if tr in TRANSITIONS_RESERVED:
        issues.append(Issue("transition_not_available", f"{p}.transitionIn",
                            f"'{tr}' is reserved; only {TRANSITIONS} exist in this version", "error"))
    elif tr not in TRANSITIONS:
        issues.append(Issue("bad_transition", f"{p}.transitionIn", f"must be one of {TRANSITIONS}", "error"))
    if "target" in sh and not _valid_target(sh["target"]):
        issues.append(Issue("bad_target", f"{p}.target", "expected {marker: id} or {detail: index >= 0}", "error"))
```

In the per-shot loop of `validate_and_repair` (the one that calls `_block(sh.get("camera"), …)`),
call `_shot_fields(i, sh, issues)`. After the grade `_block` call add:

```python
    if "edit" in s:
        _block(s.get("edit"), "edit", "edit", catalog, issues)
```

Target *references* (does the marker exist, is the detail index in range) need the profile. They
are checked in Task 12.

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests -q -m "not blender"`.

- [ ] **Step 5: Commit**
```bash
git add engine/script.py engine/tests/test_script.py
git commit -m "feat(engine): shot purpose, transitionIn (cut only, rest reserved), target; edit block ref"
```

---

## Chunk 2: Ingest extensions

CATALOG-GAPS §2: without these SubjectProfile fields, `reflection_rig`, `macro_detail` and the
future `rolling_track` cannot place anything. **Everything is geometric and trusts no names**
(spec §4.1). The Blender half dumps raw facts (an area-weighted sample of surface points). The
pure half (`measure.py`, stdlib only) turns them into targets, so every detector is unit-tested on
synthetic points with no Blender.

**Raw sample row** (written by the extractor, source coordinates after import, before placement):
`[x, y, z, nx, ny, nz, w, matIndex, curv]`. `w` is the surface area the row stands for (m² after
placement scaling). `matIndex` indexes `raw["materials"]`. `curv` is a curvature proxy in
`[0, 2]`: 1 − mean(face normal · vertex normals). It is high on small sharp features such as
badges, bolts and panel edges.

**Deferred from CATALOG-GAPS §2, no consumer yet:** character eyes (C-C02), brushed-metal
anisotropy direction (P-L10), wheel spoke count (V-M01's strobe guard). Each lands with the first
block that uses it.

### Task 5: New `SubjectProfile` fields

**Files:**
- Modify: `engine/profile.py`
- Test: `engine/tests/test_profile.py`

- [ ] **Step 1: Write the failing test** — append to `engine/tests/test_profile.py`:

```python
def test_new_ingest_fields_default_and_round_trip():
    old = json.loads((FIX / "profile_car.json").read_text())
    p = SubjectProfile.from_dict(old)  # a phase-1 document still loads
    assert (p.glossShare, p.reflectionTargets, p.shoulderLine, p.detailPoints, p.wheels, p.parts,
            p.boundsPosed) == (0.0, [], [], [], [], [], False)
    rich = {**old, "glossShare": 0.4, "boundsPosed": True,
            "reflectionTargets": [{"kind": "top", "point": [0, 0, 1.3], "normal": [0, 0, 1], "area": 3.0}],
            "detailPoints": [{"kind": "emissive", "point": [2.2, 0.6, 0.7], "normal": [1, 0, 0], "score": 3.2}],
            "wheels": [{"center": [1.4, 0.8, 0.33], "radius": 0.33, "axis": [0, 1, 0], "confidence": "high"}],
            "shoulderLine": [{"side": "+y", "points": [[0, 0.95, 0.8]]}],
            "parts": [{"index": 0, "boundsMin": [-1, -1, 0], "boundsMax": [1, 1, 1], "polyShare": 1.0}]}
    d = SubjectProfile.from_dict(rich).to_dict()
    assert {k: d[k] for k in rich} == rich
```

(Use the file's existing `FIX`/`json` imports; add them if missing.)

Also fix the phase-1 test `test_placement_round_trips` in the same file. It asserts
`from_dict(raw).to_dict() == raw`, which breaks once `to_dict()` carries the new defaulted
fields. Compare on raw's keys instead:

```python
    d = SubjectProfile.from_dict(raw).to_dict()
    assert {k: d[k] for k in raw} == raw
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_profile.py -q` → unknown key(s).

- [ ] **Step 3: Implement** — add these fields to `SubjectProfile` after `scaleFactor` and before
  `schema`, each with a default, so `valora.profile/1` documents from phase 1 still load:

```python
    glossShare: float = 0.0     # area share of gloss materials (metallic >= 0.5 or roughness <= 0.3; TIERS mask)
    reflectionTargets: list = field(default_factory=list)  # [{kind, point, normal, area}] glossy patches by facing
    shoulderLine: list = field(default_factory=list)       # [{side, points}] widest-point polyline per flank
    detailPoints: list = field(default_factory=list)       # [{kind, point, normal, score}] ranked, spread out
    wheels: list = field(default_factory=list)             # [{center, radius, axis, confidence}] best effort
    parts: list = field(default_factory=list)              # [{index, boundsMin, boundsMax, polyShare}]
    boundsPosed: bool = False   # bounds are a union over the subject's animation frames
```

All points are placed coordinates. Update the class docstring with one line per field.

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests -q -m "not blender"`.

- [ ] **Step 5: Commit**
```bash
git add engine/profile.py engine/tests/test_profile.py
git commit -m "feat(engine): SubjectProfile fields for reflection targets, details, wheels, parts, posed bounds"
```

### Task 6: Extractor — shared import, surface samples, parts, posed bounds

**Files:**
- Create: `engine/blender/__init__.py` (empty), `engine/blender/scene_io.py`,
  `engine/tests/conftest.py`, `engine/tests/blender_fixtures.py`
- Modify: `engine/ingest/blender_extract.py`
- Test: `engine/tests/test_ingest_blender.py`

`scene_io.import_subject` is the ONE GLB import. Ingest and the compiler (Task 19) both call it
with identical importer settings, so the compiler's placed bounds can equal the profile's.

- [ ] **Step 1: Test infrastructure** — `engine/tests/conftest.py`:

```python
import os

import pytest

from engine.ingest.run import BLENDER


def pytest_configure(config):
    config.addinivalue_line("markers", "blender: needs a local Blender install (slow)")


requires_blender = pytest.mark.skipif(not os.path.exists(BLENDER), reason="Blender not installed")
```

Mark the existing `engine/tests/test_ingest_blender.py` module with
`pytestmark = [pytest.mark.blender, pytest.mark.skipif(not os.path.exists(BLENDER), reason="Blender not installed")]`.

`engine/tests/blender_fixtures.py` generates tiny GLBs inside Blender for tests:

```python
"""Generate small test GLBs inside headless Blender. Test-only; never shipped."""
import subprocess
from pathlib import Path

from engine.ingest.run import BLENDER

_RIGGED = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=0.2, location=(0, 0, 0.8))
cube = bpy.context.object
arm_data = bpy.data.armatures.new("Rig")
arm = bpy.data.objects.new("Rig", arm_data)
bpy.context.scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
b = arm_data.edit_bones.new("Bone"); b.head = (0, 0, 0); b.tail = (0, 0, 1)
bpy.ops.object.mode_set(mode="OBJECT")
vg = cube.vertex_groups.new(name="Bone"); vg.add(list(range(len(cube.data.vertices))), 1.0, "REPLACE")
mod = cube.modifiers.new("Armature", "ARMATURE"); mod.object = arm
pb = arm.pose.bones["Bone"]; pb.rotation_mode = "XYZ"
pb.rotation_euler = (0, 0, 0); pb.keyframe_insert("rotation_euler", frame=1)
pb.rotation_euler = (1.5708, 0, 0); pb.keyframe_insert("rotation_euler", frame=24)
bpy.context.scene.frame_set(1)
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_animations=True)
'''

_DETAILS = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
def mat(name, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True
    n = next(x for x in m.node_tree.nodes if x.type == "BSDF_PRINCIPLED")
    for k, v in kw.items(): n.inputs[k].default_value = v
    return m
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.5))
body = bpy.context.object; body.data.materials.append(mat("gloss", Metallic=1.0, Roughness=0.1))
# A 6x6 grid, not a single quad: a detail cluster needs >= 3 samples.
bpy.ops.mesh.primitive_grid_add(x_subdivisions=6, y_subdivisions=6, size=0.1, location=(0.3, -0.501, 0.8), rotation=(1.5708, 0, 0))
lamp = bpy.context.object
lamp.data.materials.append(mat("lamp", **{"Emission Color": (1, 1, 1, 1), "Emission Strength": 5.0}))
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
'''


# A 200-unit cube authored off-centre. measure.infer_units tries mm before cm, so ingest
# reads it as millimetres (scaleFactor 0.001, a 0.2 m subject).
# Task 19 uses it to prove placement handles a non-unit scale and a non-zero source centre.
_SCALED = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=200, location=(30, -40, 100))
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
'''


def make_glb(kind, out):
    """kind: 'rigged' (bone swings a cube 90 deg over frames 1-24), 'details' (glossy cube +
    small lamp) or 'scaled' (200-unit off-centre cube)."""
    code = {"rigged": _RIGGED, "details": _DETAILS, "scaled": _SCALED}[kind]
    script = Path(out).with_suffix(".py")
    script.write_text(code, encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                           "--python", str(script), "--", str(out)],
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0 and Path(out).exists(), proc.stderr[-2000:]
    return Path(out)
```

- [ ] **Step 2: Write the failing tests** — append to `engine/tests/test_ingest_blender.py`:

```python
from engine.tests.blender_fixtures import make_glb


def test_rigged_subject_uses_posed_bounds(tmp_path):
    # At rest the 0.2 m cube sits on the bone at z 0.7-0.9. By frame 24 the bone has swung
    # 90 degrees and carried the cube out to |y| ~ 0.8. Rest-only bounds would frame a
    # 0.2 m-wide subject and the render would cut the swing off (phase-1 final review).
    p = ingest(make_glb("rigged", tmp_path / "rigged.glb"), workdir=tmp_path / "w")
    assert p.boundsPosed is True
    assert p.sizeM[1] > 0.6, p.sizeM


def test_details_glb_yields_samples_targets_and_an_emissive_detail(tmp_path):
    p = ingest(make_glb("details", tmp_path / "d.glb"), workdir=tmp_path / "w")
    assert p.glossShare > 0.9
    assert any(t["kind"] == "top" for t in p.reflectionTargets)
    em = [d for d in p.detailPoints if d["kind"] == "emissive"]
    assert em, p.detailPoints
    # The lamp was modelled at Blender (0.3, -0.501, 0.8); placement centres XY, so check
    # the side (-y face) and the height rather than exact x.
    assert em[0]["point"][1] < -0.4 and abs(em[0]["point"][2] - 0.8) < 0.08
    assert len(p.parts) == 2
```

- [ ] **Step 3: Run, expect FAIL** — `py -m pytest engine/tests/test_ingest_blender.py -q` →
  `boundsPosed` is False and `sizeM[1]` ≈ 0.2; the details test fails on `glossShare`.

- [ ] **Step 4: Implement** — `engine/blender/scene_io.py` (Blender-only module):

```python
"""The ONE GLB import (runs inside Blender). Ingest and the compiler both use it, with the same
importer settings, so the compiler's placed bounds can equal the SubjectProfile's."""
import bpy


def import_subject(glb):
    """Factory-reset the file, import the GLB, drop any cameras/lights it carried.
    Returns (new_objects, mesh_objects)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    new = [o for o in bpy.data.objects if o not in before]
    for o in [o for o in new if o.type in ("CAMERA", "LIGHT")]:
        new.remove(o)
        bpy.data.objects.remove(o, do_unlink=True)
    return new, [o for o in new if o.type == "MESH"]


def world_bounds(meshes, depsgraph):
    """Per-axis (min, max) numpy arrays over evaluated world-space vertices. Ingest and the
    compiler's placement guard (Task 19) share it, so they measure the same thing."""
    import numpy as np
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for obj in meshes:
        ev = obj.evaluated_get(depsgraph)
        mesh = ev.to_mesh()
        n = len(mesh.vertices)
        if n:
            co = np.empty(n * 3, dtype=np.float64)
            mesh.vertices.foreach_get("co", co)
            m = np.array(ev.matrix_world, dtype=np.float64)
            w = co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
            lo, hi = np.minimum(lo, w.min(axis=0)), np.maximum(hi, w.max(axis=0))
        ev.to_mesh_clear()
    return lo, hi


def animation_frames(scene, max_n=16):
    """Up to max_n frames spanning every action in the scene, or None if nothing is animated."""
    ranges = [o.animation_data.action.frame_range for o in scene.objects
              if o.animation_data and o.animation_data.action]
    if not ranges:
        return None
    a = int(min(r[0] for r in ranges))
    b = int(max(r[1] for r in ranges) + 0.999)
    n = max(2, min(max_n, b - a + 1))
    return sorted({round(a + (b - a) * k / (n - 1)) for k in range(n)})
```

`engine/ingest/blender_extract.py` changes:

1. First lines (repo root on `sys.path`, the phase-1 carry-forward):
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
```
then `from engine.blender.scene_io import animation_frames, import_subject, world_bounds`.

2. Replace `read_factory_settings` + `import_scene.gltf` in `main()` with
   `objs, meshes = import_subject(glb)`.

3. **Posed bounds.** Replace the extractor's own bounds loop with `scene_io.world_bounds`
   (import it with the other `scene_io` names). Then:
```python
    scene = bpy.context.scene
    frames = animation_frames(scene)
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for f in (frames or [scene.frame_current]):
        scene.frame_set(f)
        flo, fhi = world_bounds(meshes, bpy.context.evaluated_depsgraph_get())
        lo, hi = np.minimum(lo, flo), np.maximum(hi, fhi)
    scene.frame_set(frames[0] if frames else scene.frame_current)
```
   Write `"boundsPosed": frames is not None` into `raw`. Samples, materials and parts are taken at
   the first frame.

4. **Materials get a stable global index**: `mat_index = {}` (material name → index) assigned on
   first sight; `raw["materials"]` is built in that order. Add `"textured"` to `_props` (true when
   the Principled BSDF `Normal` input is linked, i.e. there is a normal/bump map).

5. **Surface samples** with streaming weighted reservoir sampling (Efraimidis–Spirakis:
   key = log(u)/area, keep the MAX_SAMPLES largest keys). This is exact area-weighted sampling
   without replacement in bounded memory, whatever the poly count:
```python
MAX_SAMPLES = 20000


def _poly_rows(mesh, slot_to_global):
    """Rows [x,y,z,nx,ny,nz,area,mat,curv] for every polygon of a world-space mesh copy."""
    n = len(mesh.polygons)
    f64 = lambda k, size: np.empty(size, dtype=np.float64)
    cen, nor, area = f64("c", n * 3), f64("n", n * 3), f64("a", n)
    mesh.polygons.foreach_get("center", cen)
    mesh.polygons.foreach_get("normal", nor)
    mesh.polygons.foreach_get("area", area)
    mi = np.empty(n, dtype=np.int32); mesh.polygons.foreach_get("material_index", mi)
    ltot = np.empty(n, dtype=np.int32); mesh.polygons.foreach_get("loop_total", ltot)
    lv = np.empty(len(mesh.loops), dtype=np.int32); mesh.loops.foreach_get("vertex_index", lv)
    vn = np.empty(len(mesh.vertices) * 3); mesh.vertex_normals.foreach_get("vector", vn)
    nor3, vn3 = nor.reshape(-1, 3), vn.reshape(-1, 3)
    poly_of_loop = np.repeat(np.arange(n), ltot)
    dots = (vn3[lv] * nor3[poly_of_loop]).sum(axis=1)
    curv = 1.0 - np.bincount(poly_of_loop, weights=dots, minlength=n) / np.maximum(ltot, 1)
    gmat = np.array([slot_to_global.get(int(i), -1) for i in range(max(int(mi.max(initial=0)) + 1, 1))])[mi]
    return np.column_stack([cen.reshape(-1, 3), nor3, area, gmat, curv])


class _Reservoir:
    def __init__(self, k, seed=0):
        self.k, self.rng = k, np.random.default_rng(seed)
        self.rows, self.keys, self.total_area, self.count = np.empty((0, 9)), np.empty(0), 0.0, 0

    def add(self, rows):
        a = np.maximum(rows[:, 6], 1e-30)
        self.total_area += float(a.sum()); self.count += len(rows)
        keys = np.log(self.rng.random(len(rows))) / a
        rows, keys = np.vstack([self.rows, rows]), np.concatenate([self.keys, keys])
        if len(keys) > self.k:
            keep = np.argpartition(keys, -self.k)[-self.k:]
            rows, keys = rows[keep], keys[keep]
        self.rows, self.keys = rows, keys

    def result(self):
        out = self.rows.copy()
        if self.count > self.k:  # sampled by area: every row now stands for an equal share
            out[:, 6] = self.total_area / len(out)
        return out
```
   In the per-object loop (world-space `mesh` after `mesh.transform(obj.matrix_world)`), build
   `slot_to_global` from `obj.material_slots` via `mat_index`, then `res.add(_poly_rows(mesh, slot_to_global))`.
   Write `raw["samples"] = [[round(float(v), 6) for v in r] for r in res.result()]`.

6. **Parts**: per mesh object, `{"boundsMin", "boundsMax", "polys"}` in source coordinates, into
   `raw["parts"]`. Object names are not recorded (trust no names).

`measure.build_profile` ignores the new raw keys until Tasks 7–9, except `boundsPosed` and parts.
Add those now:

```python
        boundsPosed=bool(raw.get("boundsPosed", False)),
        parts=_parts(raw.get("parts", []), place),
```

```python
def _parts(parts, place, max_n=64):
    total = sum(p.get("polys", 0) for p in parts) or 1
    rows = sorted(parts, key=lambda p: -p.get("polys", 0))[:max_n]
    return [{"index": i, "boundsMin": [round(v, 6) for v in place(p["boundsMin"])],
             "boundsMax": [round(v, 6) for v in place(p["boundsMax"])],
             "polyShare": round(p.get("polys", 0) / total, 4)} for i, p in enumerate(rows)]
```

- [ ] **Step 5: Run** — `py -m pytest engine/tests/test_ingest_blender.py -q`. The rigged test
  must PASS now. The details test still fails (glossShare/targets/details come in Tasks 7–8):
  mark it `@pytest.mark.xfail(strict=True, reason="detectors land in Tasks 7-8")` and remove the
  mark in Task 8. Run `py -m pytest engine/tests -q` → all others pass.

- [ ] **Step 6: Commit**
```bash
git add engine/blender engine/ingest engine/tests/conftest.py engine/tests/blender_fixtures.py engine/tests/test_ingest_blender.py
git commit -m "feat(ingest): shared GLB import, area-weighted surface samples, parts, posed bounds for rigs"
```

### Task 7: Pure detectors — gloss share and reflection targets

**Files:**
- Modify: `engine/ingest/measure.py`
- Test: `engine/tests/test_measure_targets.py` (new)

The synthetic "car" used by Tasks 7–9 is a test helper. Put it at the top of the new test file:

```python
import math
import pytest
from engine.ingest.measure import (Sample, build_profile, detail_points, gloss_share,
                                   reflection_targets, shoulder_line, wheels)

GLOSS = {"metallic": 1.0, "roughness": 0.1, "area": 1.0}
MATTE = {"metallic": 0.0, "roughness": 0.8, "area": 1.0}
LAMP = {"emission": 5.0, "area": 1.0}


def S(p, n, w=0.01, cls="glossy", gloss=True, textured=False, curv=0.0):
    return Sample(tuple(p), tuple(n), w, cls, gloss, textured, curv)


def box_car(L=4.5, W=1.9, H=1.3, step=0.1):
    """Glossy box body from z=0.35H to H, with 4 matte cylinder wheels r=0.33 touching z=0."""
    out = []
    xs = [(-L / 2) + step * (i + 0.5) for i in range(int(L / step))]
    ys = [(-W / 2) + step * (i + 0.5) for i in range(int(W / step))]
    zs = [0.35 * H + step * (i + 0.5) for i in range(int(0.65 * H / step))]
    out += [S((x, y, H), (0, 0, 1)) for x in xs for y in ys]                       # roof
    out += [S((x, sgn * W / 2, z), (0, sgn, 0)) for x in xs for z in zs for sgn in (1, -1)]  # flanks
    out += [S((sgn * L / 2, y, z), (sgn, 0, 0)) for y in ys for z in zs for sgn in (1, -1)]  # ends
    r = 0.33
    for wx in (-1.4, 1.4):
        for wy in (-0.8, 0.8):
            for k in range(72):
                a = 2 * math.pi * k / 72
                p = (wx + r * math.sin(a), wy, r - r * math.cos(a))
                out.append(S(p, (math.sin(a), 0, -math.cos(a)), cls="matte", gloss=False))
    return out
```

- [ ] **Step 1: Write the failing tests**

```python
def test_gloss_share_uses_the_tiers_gloss_definition():
    assert gloss_share([GLOSS, MATTE]) == pytest.approx(0.5)
    assert gloss_share([{"metallic": 0.0, "roughness": 0.3, "area": 1.0}]) == 1.0  # roughness <= 0.3
    assert gloss_share([]) == 0.0


def test_reflection_targets_find_roof_and_flanks():
    t = {x["kind"]: x for x in reflection_targets(box_car())}
    assert {"top", "+y", "-y"} <= set(t)
    assert t["top"]["normal"] == pytest.approx([0, 0, 1], abs=1e-6)
    assert t["top"]["point"][2] == pytest.approx(1.3)
    assert t["+y"]["point"][1] == pytest.approx(0.95)
    # Every target point is a real surface sample, not an averaged point in mid-air.
    pts = {tuple(round(v, 5) for v in s.p) for s in box_car()}
    assert all(tuple(x["point"]) in pts for x in t.values())


def test_reflection_targets_ignore_matte_and_down_facing():
    samples = [S((0, 0, 0), (0, 0, -1))] * 50 + [S((0, 0, 1), (0, 0, 1), cls="matte", gloss=False)] * 50
    assert reflection_targets(samples) == []
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_measure_targets.py -q` → ImportError.

- [ ] **Step 3: Implement** — in `engine/ingest/measure.py`:

```python
import math
from collections import namedtuple

Sample = namedtuple("Sample", "p n w cls gloss textured curv")  # placed coords, unit normal, area m^2

GLOSS_METALLIC, GLOSS_ROUGHNESS = 0.5, 0.3  # TIERS §2 "gloss" mask definition
_DIRS = {"top": (0, 0, 1), "+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0),
         "top+x": (0.7071, 0, 0.7071), "top-x": (-0.7071, 0, 0.7071),
         "top+y": (0, 0.7071, 0.7071), "top-y": (0, -0.7071, 0.7071)}


def is_gloss(m):
    return m.get("metallic", 0.0) >= GLOSS_METALLIC or m.get("roughness", 0.5) <= GLOSS_ROUGHNESS


def gloss_share(mats):
    total = sum(m.get("area", 0.0) for m in mats)
    if total <= 0:
        return 0.0
    return round(sum(m.get("area", 0.0) for m in mats if is_gloss(m)) / total, 4)


def _r(v, nd=5):
    return [round(float(x), nd) for x in v]


def _unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n > 0 else [0.0, 0.0, 1.0]


def _representative(ss):
    """(area, surface point nearest the area-weighted centroid, mean unit normal)."""
    a = sum(s.w for s in ss)
    c = [sum(s.p[i] * s.w for s in ss) / a for i in range(3)]
    rep = min(ss, key=lambda s: sum((s.p[i] - c[i]) ** 2 for i in range(3)))
    n = _unit([sum(s.n[i] * s.w for s in ss) for i in range(3)])
    return a, rep.p, n


def reflection_targets(samples, max_n=6, min_share=0.05):
    """Largest glossy patches grouped by facing: where the reflection solver aims the key planes
    (vehicles.md V-L02/L03, products.md P-L01). Down-facing surfaces are never lit this way."""
    gl = [s for s in samples if s.gloss and s.n[2] > -0.5]
    total = sum(s.w for s in gl)
    if total <= 0:
        return []
    bins = {}
    for s in gl:
        k = max(_DIRS, key=lambda d: sum(a * b for a, b in zip(_DIRS[d], s.n)))
        bins.setdefault(k, []).append(s)
    out = []
    for k, ss in bins.items():
        a, p, n = _representative(ss)
        if a >= min_share * total:
            out.append({"kind": k, "point": _r(p), "normal": _r(n), "area": round(a, 6)})
    return sorted(out, key=lambda t: -t["area"])[:max_n]
```

In `build_profile`, turn raw sample rows into placed `Sample`s and fill the new fields:

```python
def _samples(raw, place, f):
    mats = raw.get("materials", [])
    out = []
    for x, y, z, nx, ny, nz, w, mi, curv in raw.get("samples", []):
        m = mats[int(mi)] if 0 <= int(mi) < len(mats) else {}
        out.append(Sample(tuple(place([x, y, z])), tuple(_unit([nx, ny, nz])), w * f * f,
                          material_class(m), is_gloss(m), bool(m.get("textured")), curv))
    return out
```

and pass `glossShare=gloss_share(raw.get("materials", []))`,
`reflectionTargets=reflection_targets(samples)` to the constructor (`samples = _samples(raw, place, f)`).
Add `detail_points`, `shoulder_line`, `wheels` as stubs returning `[]` so the import in the test
file works. Tasks 8–9 replace them.

- [ ] **Step 4: Run, expect PASS** — the three tests above pass; `py -m pytest engine/tests -q -m "not blender"` green.

- [ ] **Step 5: Commit**
```bash
git add engine/ingest/measure.py engine/tests/test_measure_targets.py
git commit -m "feat(ingest): gloss share and reflection targets from surface samples"
```

### Task 8: Pure detectors — shoulder line and detail points

**Files:** Modify `engine/ingest/measure.py`; Test `engine/tests/test_measure_targets.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_shoulder_line_follows_the_widest_point_per_flank():
    car = box_car()
    # Flare the flanks at z ~ 0.8 m: that row becomes the widest point, i.e. the shoulder.
    car = [s._replace(p=(s.p[0], s.p[1] * 1.03, s.p[2])) if abs(abs(s.p[1]) - 0.95) < 1e-9
           and abs(s.p[2] - 0.805) < 0.03 else s for s in car]
    lines = {l["side"]: l["points"] for l in shoulder_line(car, [-2.25, -0.98, 0], [2.25, 0.98, 1.3])}
    assert set(lines) == {"+y", "-y"}
    assert all(abs(p[2] - 0.805) < 0.03 for p in lines["+y"])


def test_detail_points_rank_emissive_first_and_stay_apart():
    car = box_car()
    lamp = [S((2.25, 0.6 + 0.01 * i, 0.7), (1, 0, 0), cls="emissive", gloss=False) for i in range(10)]
    badge = [S((2.25, -0.3 + 0.005 * i, 0.9), (1, 0, 0), curv=0.4) for i in range(10)]
    d = detail_points(car + lamp + badge, longest=4.5)
    assert d[0]["kind"] == "emissive" and d[0]["point"][1] == pytest.approx(0.645, abs=0.05)
    assert any(x["kind"] == "glossy_peak" for x in d)
    assert len(d) <= 8
    for i, a in enumerate(d):
        for b in d[i + 1:]:
            assert math.dist(a["point"], b["point"]) >= 0.15 * 4.5 - 1e-9


def test_detail_points_empty_for_featureless_subject():
    flat = [S((x * 0.1, 0, 0), (0, 0, 1), cls="matte", gloss=False) for x in range(50)]
    assert detail_points(flat, longest=5.0) == []
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement**

```python
_LONG_AXIS = lambda bmin, bmax: (0, 1) if bmax[0] - bmin[0] >= bmax[1] - bmin[1] else (1, 0)


def shoulder_line(samples, bmin, bmax, bins=12):
    """Per flank, the widest point in each slice along the long axis, between 0.3H and 0.9H.
    That is the shoulder line the side strips should run along (vehicles.md V-L03)."""
    la, wa = _LONG_AXIS(bmin, bmax)
    H, lo_l, span = bmax[2] - bmin[2], bmin[la], bmax[la] - bmin[la]
    body = [s for s in samples if 0.3 * H <= s.p[2] <= 0.9 * H]
    out = []
    for sign, name in ((1, "+"), (-1, "-")):
        pts = []
        for b in range(bins):
            a = lo_l + span * (0.05 + 0.9 * b / bins)
            e = lo_l + span * (0.05 + 0.9 * (b + 1) / bins)
            band = [s for s in body if a <= s.p[la] < e and s.p[wa] * sign > 0]
            if band:
                pts.append(_r(max(band, key=lambda s: s.p[wa] * sign).p))
        if len(pts) >= bins // 2:
            out.append({"side": f"{name}{'xy'[wa]}", "points": pts})
    return out


def _cells(samples, cell):
    g = {}
    for s in samples:
        g.setdefault(tuple(math.floor(v / cell) for v in s.p), []).append(s)
    return [ss for ss in g.values() if len(ss) >= 3]


def _pct(vals, q):
    v = sorted(vals)
    return v[min(len(v) - 1, int(q * len(v)))]


# Base score per kind: lamps first (V-C12 detail inventory), then glossy glints, sharp small
# features, textures. (eng) ordering; the director may override with an explicit target.
_KIND_BASE = {"emissive": 3.0, "glossy_peak": 2.0, "high_curvature": 1.0, "textured": 0.5}


def detail_points(samples, longest, max_n=8, sep_frac=0.15):
    cell = 0.08 * longest
    groups = {
        "emissive": [s for s in samples if s.cls == "emissive"],
        "textured": [s for s in samples if s.textured],
    }
    gl = [s for s in samples if s.gloss and s.curv > 1e-4]
    if gl:
        cut = _pct([s.curv for s in gl], 0.90)
        groups["glossy_peak"] = [s for s in gl if s.curv >= cut]
    other = [s for s in samples if not s.gloss and s.cls != "emissive" and s.curv > 1e-4]
    if other:
        cut = _pct([s.curv for s in other], 0.95)
        groups["high_curvature"] = [s for s in other if s.curv >= cut]
    cands = []
    for kind, ss in groups.items():
        total = sum(s.w for s in ss) or 1.0
        for cl in _cells(ss, cell):
            a, p, n = _representative(cl)
            cands.append({"kind": kind, "point": _r(p), "normal": _r(n),
                          "score": round(_KIND_BASE[kind] + a / total, 4)})
    kept = []
    for c in sorted(cands, key=lambda c: -c["score"]):
        if all(math.dist(c["point"], k["point"]) >= sep_frac * longest for k in kept):
            kept.append(c)
        if len(kept) == max_n:
            break
    return kept
```

Wire into `build_profile`: `shoulderLine=shoulder_line(samples, bmin, bmax)`,
`detailPoints=detail_points(samples, max(size))`. Remove the `xfail` mark from Task 6's
`test_details_glb_yields_samples_targets_and_an_emissive_detail`.

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests -q` (includes the Blender details test).

- [ ] **Step 5: Commit**
```bash
git add engine/ingest/measure.py engine/tests/test_measure_targets.py engine/tests/test_ingest_blender.py
git commit -m "feat(ingest): shoulder line and ranked, spread-out detail points"
```

### Task 9: Pure detector — wheels (best effort, with confidence)

No block consumes wheels in phase 2: `rolling_track` + `drive` is deferred. The detector exists
so the first vehicle block has data, and it reports `confidence` so that block can refuse
`low`. Method: ground-contact patches give each wheel's (l, w) centre. Each surface sample near
a patch votes a radius `r = z / (1 + n_z)`: the centre of the circle through that point along its
normal must sit at height r. A vote only counts if the circle's centre lands on the patch. The
median of the votes is the radius.

**Files:** Modify `engine/ingest/measure.py`; Test `engine/tests/test_measure_targets.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_wheels_found_on_synthetic_car():
    w = wheels(box_car(), [-2.25, -0.98, 0], [2.25, 0.98, 1.3])
    assert len(w) == 4
    for x in w:
        assert x["radius"] == pytest.approx(0.33, abs=0.02)
        assert x["center"][2] == pytest.approx(0.33, abs=0.02)
        assert x["axis"] == [0.0, 1.0, 0.0] and x["confidence"] == "high"


def test_no_wheels_on_a_bottle():
    bottle = [S((0.03 * math.cos(a / 10), 0.03 * math.sin(a / 10), z * 0.01), (math.cos(a / 10), math.sin(a / 10), 0))
              for a in range(63) for z in range(30)]
    assert wheels(bottle, [-0.03, -0.03, 0], [0.03, 0.03, 0.3]) == []
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement**

```python
def _components(points, cell):
    """Connected components of 2D points on a grid (8-neighbourhood)."""
    grid = {}
    for p in points:
        grid.setdefault((math.floor(p[0] / cell), math.floor(p[1] / cell)), []).append(p)
    seen, comps = set(), []
    for start in grid:
        if start in seen:
            continue
        stack, comp = [start], []
        seen.add(start)
        while stack:
            c = stack.pop()
            comp += grid[c]
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nb = (c[0] + dx, c[1] + dy)
                    if nb in grid and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        comps.append(comp)
    return comps


def wheels(samples, bmin, bmax):
    la, wa = _LONG_AXIS(bmin, bmax)
    H, Wd = bmax[2] - bmin[2], bmax[wa] - bmin[wa]
    contacts = [(s.p[la], s.p[wa]) for s in samples if s.p[2] <= 0.02 * H]
    patches = [c for c in _components(contacts, 0.1 * Wd) if len(c) >= 3]
    if not 3 <= len(patches) <= 8:
        return []
    out = []
    for comp in patches:
        lc = sum(p[0] for p in comp) / len(comp)
        wc = sum(p[1] for p in comp) / len(comp)
        votes = []
        for s in samples:
            if not (0.02 * H < s.p[2] <= 0.6 * H and abs(s.p[wa] - wc) <= 0.15 * Wd
                    and abs(s.n[wa]) < 0.3 and s.n[2] > -0.95):
                continue
            r = s.p[2] / (1.0 + s.n[2])
            if 0 < r < 0.6 * H and abs(s.p[la] - r * s.n[la] - lc) < 0.1 * r:
                votes.append(r)
        if len(votes) < 5:
            continue
        votes.sort()
        r = votes[len(votes) // 2]
        iqr = votes[3 * len(votes) // 4] - votes[len(votes) // 4]
        center, axis = [0.0, 0.0, r], [0.0, 0.0, 0.0]
        center[la], center[wa], axis[wa] = lc, wc, 1.0
        out.append({"center": _r(center), "radius": round(r, 5), "axis": axis,
                    "confidence": "high" if iqr <= 0.15 * r else "low"})
    return out if len(out) >= 3 else []
```

Wire `wheels=wheels(samples, bmin, bmax)` into `build_profile`.

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests -q -m "not blender"`.

- [ ] **Step 5: Commit**
```bash
git add engine/ingest/measure.py engine/tests/test_measure_targets.py
git commit -m "feat(ingest): best-effort wheel detection from ground contacts, with confidence"
```

### Task 10: Regenerate the six reference profiles and assert the new fields

**Files:**
- Modify: `engine/tests/fixtures/profiles/*.json` (regenerated), `engine/tests/test_real_profiles.py`

- [ ] **Step 1: Regenerate** (Blender, about a minute in total):
```bash
for m in camera_01 flighthelmet mid_century_lounge_chair pocket_watch toycar vintage_microscope; do
  py -m engine ingest assets-in/models/$m/$m.glb --out engine/tests/fixtures/profiles/$m.json > /dev/null
done
```
Check each diff: `sizeM`/`bounds*` must be unchanged (no model here is animated) and the new
fields filled. If bounds moved, stop: the shared importer changed behaviour. Investigate before
continuing.

- [ ] **Step 2: Add assertions** — append to `engine/tests/test_real_profiles.py`:

```python
@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.stem)
def test_reference_profiles_carry_ingest_extensions(path):
    p = SubjectProfile.from_dict(json.loads(path.read_text(encoding="utf-8")))
    assert 0.0 <= p.glossShare <= 1.0
    assert p.parts, "every model has at least one mesh part"
    for d in p.detailPoints:
        assert all(lo - 1e-6 <= v <= hi + 1e-6 for v, lo, hi in zip(d["point"], p.boundsMin, p.boundsMax))
    assert len(p.detailPoints) <= 8
    if p.wheels:  # best effort: if found, they must be plausible
        assert 3 <= len(p.wheels) <= 8
        assert all(w["radius"] < 0.6 * p.sizeM[2] for w in p.wheels)


def test_glossy_reference_models_have_reflection_targets():
    for name in ("pocket_watch", "camera_01"):
        p = SubjectProfile.from_dict(json.loads((FIX / "profiles" / f"{name}.json").read_text(encoding="utf-8")))
        if p.glossShare >= 0.1:
            assert p.reflectionTargets, name
```

- [ ] **Step 3: Run, expect PASS** — `py -m pytest engine/tests -q`. Record in the commit body
  which models got wheels (expect only `toycar`, if any) and each model's detail-point kinds.
  The report needs these later.

- [ ] **Step 4: Commit**
```bash
git add engine/tests/fixtures/profiles engine/tests/test_real_profiles.py
git commit -m "test(ingest): regenerate reference profiles with reflection targets, details, parts"
```

---

## Chunk 3: The first T3-capable blocks (pure halves)

**Which gaps this phase builds** (CATALOG-GAPS §1, ranked by T3 impact):

| Rank | Block | Built here? | Why |
|---|---|---|---|
| 1 | `reflection_rig` (lighting) | **Yes**, Task 11 + 22 | Unblocks T3-06..T3-10: the biggest jump from T2 to T3 |
| 2 | `sequence` (edit) | **Yes**, Task 13 | T3-01..T3-05, T3-13, T3-15, T3-16 are edit rules; without it nothing is multi-set-up |
| 3 | `macro_detail` (camera) | **Yes**, Task 12 | T3-03 needs a detail shot; T3-22 shallow details |
| 4 | `mood_grade` (grade) | **Yes**, Task 14 + 23 | T2-08, T3-19 subject separation, T3-08 highlight guard |
| 6 | `haze_volume` (effect) | **Yes (pulled forward)**, Task 15 + 22 | Tiers are cumulative and T2-07 requires atmosphere: without an atmosphere block **no** phase-2 render can score T2, let alone T3. It is cheap. (`ground_fog` stays deferred.) |
| 5 | `rolling_track` + `drive` | **Deferred** | Needs a road world (only `studio_cyc` exists), wheel rotation driven by validated wheel data (Task 9 is best effort), and a real-scale vehicle eval subject (Task 30 sources one). Build in catalog growth (spec §10 step 5), vehicles first. |
| 7 | Worlds `night_street`, `rain_courtyard`, `exterior_sun`, `interior_daylight` | Deferred | Spec §10 step 5: port the render-studio rain scene and compositor, then new worlds. Each needs an owner-graded golden render. |
| 8 | Transitions | Deferred (**names reserved**, Task 4) | Each needs timeline + compositor work; the hard cut covers T3-17 via cut-on-action once flow metrics exist. |
| 9 | `handheld_operator` | Deferred | Camera Shakify's code is GPL-3 (re-implement the loader), its shake data is CC0. T2-04 is met meanwhile by motivated paths. |
| 10, 14 | `light_sweep`, `edge_reveal` | Deferred | Need animated lighting params in the schema. |
| 11 | `hero_settle` | **Partly**: `settleFrac` on `low_hero_push` / `arc_orbit` (Task 2) delivers T3-13. A dedicated block comes later. |
| 12, 13, 15–20 | crane/drone, profile slide, glass field, crash zoom, portrait rig, interior camera, explode, T4 sims | Deferred | Catalog growth by CATALOG-GAPS order after this phase's goldens are graded. `explode_assembly` has its ingest data (Task 6 parts). |

### Task 11: Reflection solver and the `reflection_rig` manifest

vehicles.md §1 "Reflection solver": for a body point P with normal N seen from camera C,
`d = normalize(P − C)`, `R = d − 2(d·N)N`. A light centred on `P + R·dist`, facing `−R`, puts its
reflection on P. The rig solves once, from the hero camera: the last `hero` shot, else the last
shot, at mid-shot. That keeps key direction continuous across shots (T4-01). Re-solving accents per
shot is later work.

Rig contents: one huge overhead plane (V-L02, P-L01), a side strip per visible flank (V-L03, at
most 2, so there are at most 3 big planes: V-L04), up to N accents on detail points (V-L05), a rim
from behind (V-L11, P-L06), and black negative-fill cards below the strips (V-L10). Every size,
height and ratio default is **(eng)** and is calibrated in Task 29 through T3-06..T3-09.

**Files:**
- Create: `engine/reflect.py`, `engine/color.py`, `engine/blocks/lighting/reflection_rig/block.json`,
  `engine/tests/test_reflect.py`

- [ ] **Step 1: Write the failing tests** — `engine/tests/test_reflect.py`

```python
import json
import math
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.color import kelvin_to_rgb
from engine.geometry import point_in_box
from engine.profile import SubjectProfile
from engine.reflect import mirror_dir, rig_layout

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()
CAR = SubjectProfile.from_dict(json.loads((FIX / "profile_car.json").read_text()))
P = {k: v["default"] for k, v in CAT.get("lighting", "reflection_rig")["params"].items()}


def _angle(a, b):
    na, nb = math.hypot(*a), math.hypot(*b)
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b)) / (na * nb)))))


def test_mirror_dir_obeys_the_law_of_reflection():
    r = mirror_dir((0, 0, 0), (0, 0, 1), (-1, 0, 1))
    assert r == pytest.approx((0.7071068, 0, 0.7071068))


def test_side_on_camera_gets_one_solved_strip_on_the_seen_flank():
    cam = (0.0, -10.0, 0.8)
    rig = rig_layout(CAR, cam, P)
    strips = [l for l in rig.lights if l.role == "strip"]
    assert len(strips) == 1 and strips[0].center[1] < -0.95
    p = (0.0, -0.95, 0.78)  # synthesized -y flank target at 0.6 H
    want = mirror_dir(p, (0, -1, 0), cam)
    got = tuple(c - q for c, q in zip(strips[0].center, p))
    assert _angle(got, want) < 1e-6


def test_three_quarter_camera_gets_two_strips_and_at_most_three_big_planes():
    rig = rig_layout(CAR, (8.0, -8.0, 1.0), P)
    assert len([l for l in rig.lights if l.role == "strip"]) == 2
    assert len([l for l in rig.lights if l.role in ("overhead", "strip")]) <= 3  # V-L04


def test_overhead_is_above_the_roof_and_everything_is_outside_the_subject():
    rig = rig_layout(CAR, (8.0, -8.0, 1.0), P)
    over = [l for l in rig.lights if l.role == "overhead"]
    assert len(over) == 1 and over[0].center[2] > CAR.boundsMax[2]
    for l in rig.lights:
        assert not point_in_box(l.center, CAR.boundsMin, CAR.boundsMax, 0.10), l.name
        assert l.center[2] > 0, l.name
        assert math.isclose(math.hypot(*l.facing), 1.0, rel_tol=1e-9)


def test_negative_fill_is_black_and_below_the_strip():
    rig = rig_layout(CAR, (0.0, -10.0, 0.8), P)
    neg = [l for l in rig.lights if l.role == "negfill"]
    strip = [l for l in rig.lights if l.role == "strip"][0]
    assert neg and all(n.power == 0 and n.center[2] < strip.center[2] for n in neg)


def test_accents_use_detail_points_and_respect_the_count():
    rich = SubjectProfile.from_dict({**CAR.to_dict(), "detailPoints": [
        {"kind": "glossy_peak", "point": [2.25, 0.5, 0.9], "normal": [1, 0, 0], "score": 2.1},
        {"kind": "high_curvature", "point": [-2.25, 0.0, 0.8], "normal": [-1, 0, 0], "score": 1.1}]})
    assert len([l for l in rig_layout(rich, (8, -8, 1), {**P, "accentCount": 4}).lights if l.role == "accent"]) == 2
    assert len([l for l in rig_layout(rich, (8, -8, 1), {**P, "accentCount": 1}).lights if l.role == "accent"]) == 1


def test_ambient_is_one_over_key_fill():
    assert rig_layout(CAR, (8, -8, 1), {**P, "keyFill": 4.0}).ambient == pytest.approx(0.25)


def test_kelvin_to_rgb_is_warm_to_cool():
    w, d, c = kelvin_to_rgb(3000), kelvin_to_rgb(6500), kelvin_to_rgb(9000)
    assert w[0] == 1.0 and w[0] > w[1] > w[2]
    assert all(v > 0.9 for v in d)
    assert c[2] >= c[0]
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_reflect.py -q` → ImportError.

- [ ] **Step 3: Implement** — `engine/color.py`:

```python
"""Colour temperature -> linear-ish RGB for light colours (Tanner Helland fit). Pure. (eng)"""
import math


def kelvin_to_rgb(kelvin):
    t = min(max(float(kelvin), 1000.0), 40000.0) / 100.0
    r = 255.0 if t <= 66 else 329.698727446 * (t - 60) ** -0.1332047592
    g = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * (t - 60) ** -0.0755148492
    b = 255.0 if t >= 66 else 0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307
    c = [min(max(v, 0.0), 255.0) / 255.0 for v in (r, g, b)]
    m = max(c)
    return tuple(v / m for v in c)
```

`engine/reflect.py`:

```python
"""Reflection-shaped lighting (vehicles.md §1 V-L01..L11; products.md P-L01..L07). Pure maths:
the compiler turns LightSpecs into Blender area lights and black cards (Task 22).
Every size/height/ratio default is (eng): calibrate through harness items T3-06..T3-09."""
import math
from dataclasses import dataclass

from engine.geometry import _dot, _norm, _sub, point_in_box

LIGHT_BOX_MARGIN = 0.10   # same margin the checker keeps cameras out of
MIN_Z_FRAC = 0.05         # lights stay above the floor by this fraction of the subject radius
MAX_STRIPS = 2            # V-L04: overhead + 2 strips = at most 3 big planes


@dataclass(frozen=True)
class LightSpec:
    name: str
    role: str       # overhead | strip | accent | rim | negfill
    center: tuple
    facing: tuple   # unit vector the emitting face points along
    sizeX: float
    sizeY: float
    power: float    # relative radiance; build.py multiplies by area and a calibrated constant


@dataclass(frozen=True)
class RigLayout:
    lights: tuple
    ambient: float  # world fill relative to the overhead radiance (= 1 / keyFill, V-L11 / P-L05)


def mirror_dir(point, normal, camera):
    d = _norm(_sub(point, camera))
    n = _norm(normal)
    k = 2.0 * _dot(d, n)
    return _norm((d[0] - k * n[0], d[1] - k * n[1], d[2] - k * n[2]))


def _along(p, v, t):
    return (p[0] + v[0] * t, p[1] + v[1] * t, p[2] + v[2] * t)


def _place(p, direction, dist, profile):
    """Centre at p + direction*dist, lifted above the floor and pushed out of the subject box;
    facing points back at p."""
    c = _along(p, direction, dist)
    zmin = MIN_Z_FRAC * profile.radius
    if c[2] < zmin:
        c = (c[0], c[1], zmin)
    cx, cy, _ = profile.center
    for _ in range(40):
        if not point_in_box(c, profile.boundsMin, profile.boundsMax, LIGHT_BOX_MARGIN):
            break
        h = (c[0] - cx, c[1] - cy, 0.0)
        h = _norm(h) if (h[0] or h[1]) else (1.0, 0.0, 0.0)
        c = (c[0] + h[0] * 0.1 * profile.radius, c[1] + h[1] * 0.1 * profile.radius, c[2])
    return c, _norm(_sub(p, c))


def _targets(profile):
    """Top + flank targets from ingest; synthesized from bounds for profiles without them."""
    lo, hi = profile.boundsMin, profile.boundsMax
    cx, cy, _ = profile.center
    by = {t["kind"]: t for t in profile.reflectionTargets}
    top = by.get("top") or {"kind": "top", "point": [cx, cy, hi[2]], "normal": [0, 0, 1]}
    sides = [t for k, t in by.items() if k in ("+x", "-x", "+y", "-y")]
    if not sides:
        z = lo[2] + 0.6 * (hi[2] - lo[2])
        sides = [{"kind": "+x", "point": [hi[0], cy, z], "normal": [1, 0, 0]},
                 {"kind": "-x", "point": [lo[0], cy, z], "normal": [-1, 0, 0]},
                 {"kind": "+y", "point": [cx, hi[1], z], "normal": [0, 1, 0]},
                 {"kind": "-y", "point": [cx, lo[1], z], "normal": [0, -1, 0]}]
    return top, sides


def rig_layout(profile, camera, params):
    r = profile.radius
    L, W = max(profile.sizeM[:2]), min(profile.sizeM[:2])
    H = profile.sizeM[2]
    top, sides = _targets(profile)
    lights = []

    # Overhead plane (V-L02, P-L01): solved so the roof/top reflects it, else straight above.
    P = tuple(top["point"])
    R = mirror_dir(P, top["normal"], camera)
    height = profile.boundsMax[2] + params["overheadHeightR"] * r
    if R[2] > 0.2:
        c, facing = _place(P, R, (height - P[2]) / R[2], profile)
    else:
        c, facing = (profile.center[0], profile.center[1], height), (0.0, 0.0, -1.0)
    lights.append(LightSpec("valora_overhead", "overhead", c, facing,
                            L * params["overheadScale"], W * params["overheadWidth"], 1.0))

    # Side strips on the flanks the camera sees (V-L03, V-L08), most face-on first.
    seen = []
    for s in sides:
        v = _norm(_sub(camera, s["point"]))
        facing_cam = _dot(_norm(s["normal"]), v)
        if facing_cam > 0.05:
            seen.append((facing_cam, s))
    seen.sort(key=lambda t: -t[0])
    length = L * params["stripLength"]
    width = length / params["stripAspect"]
    for _, s in seen[:MAX_STRIPS]:
        p = tuple(s["point"])
        c, facing = _place(p, mirror_dir(p, s["normal"], camera), params["stripDistR"] * r, profile)
        lights.append(LightSpec(f"valora_strip_{s['kind']}", "strip", c, facing, length, width, 0.8))
        # Negative fill (V-L10): a black card where the lower flank's reflection lands.
        low = (p[0], p[1], profile.boundsMin[2] + 0.3 * H)
        c2, f2 = _place(low, mirror_dir(low, s["normal"], camera), params["stripDistR"] * r, profile)
        lights.append(LightSpec(f"valora_negfill_{s['kind']}", "negfill", c2, f2,
                                length, width * (1.0 + 4.0 * params["darkShare"]), 0.0))

    # Accents on detail glints (V-L05): small, close, placed by reflection.
    pts = [d for d in profile.detailPoints if d["kind"] in ("glossy_peak", "high_curvature")]
    for i, d in enumerate(pts[: int(params["accentCount"])]):
        p = tuple(d["point"])
        c, facing = _place(p, mirror_dir(p, d["normal"], camera), 0.6 * r, profile)
        side = params["accentScale"] * 0.5 * r
        lights.append(LightSpec(f"valora_accent_{i}", "accent", c, facing, side, side, 0.6))

    # Rim from behind and above (V-L11, P-L06).
    cx, cy, cz = profile.center
    az = math.atan2(camera[1] - cy, camera[0] - cx) + math.pi
    el = math.radians(params["rimElevationDeg"])
    c = (cx + 2 * r * math.cos(el) * math.cos(az), cy + 2 * r * math.cos(el) * math.sin(az), cz + 2 * r * math.sin(el))
    lights.append(LightSpec("valora_rim", "rim", c, _norm(_sub(profile.center, c)), 0.6 * r, 0.3 * r,
                            params["rimStrength"]))
    return RigLayout(tuple(lights), 1.0 / params["keyFill"])
```

`engine/blocks/lighting/reflection_rig/block.json`:

```json
{
  "id": "reflection_rig",
  "kind": "lighting",
  "description": "Professional reflection lighting for glossy subjects (cars, watches, electronics, bottles). One huge soft overhead plane, a long strip along each visible flank, small accents on detail glints, a rim from behind, and black cards that keep planned dark areas in the reflections. Each light is placed where the camera sees it reflected, so highlights run as long smooth gradients along the body lines. Use it instead of softbox_three_point whenever the subject is glossy.",
  "params": {
    "overheadScale": {"type": "number", "min": 1.0, "max": 1.6, "default": 1.3},
    "overheadWidth": {"type": "number", "min": 0.8, "max": 1.4, "default": 1.1},
    "overheadHeightR": {"type": "number", "min": 0.3, "max": 1.5, "default": 0.6},
    "stripLength": {"type": "number", "min": 0.8, "max": 1.3, "default": 1.0},
    "stripAspect": {"type": "number", "min": 3.0, "max": 30.0, "default": 8.0},
    "stripDistR": {"type": "number", "min": 0.4, "max": 1.5, "default": 0.8},
    "accentCount": {"type": "number", "min": 0, "max": 10, "default": 4},
    "accentScale": {"type": "number", "min": 0.2, "max": 0.7, "default": 0.4},
    "darkShare": {"type": "number", "min": 0.3, "max": 0.7, "default": 0.45},
    "keyFill": {"type": "number", "min": 2.0, "max": 8.0, "default": 4.0},
    "rimStrength": {"type": "number", "min": 0.0, "max": 3.0, "default": 1.0},
    "rimElevationDeg": {"type": "number", "min": 30.0, "max": 60.0, "default": 45.0},
    "colorTempK": {"type": "number", "min": 3200.0, "max": 9000.0, "default": 6000.0},
    "exposureEv": {"type": "number", "min": -2.0, "max": 2.0, "default": 0.0}
  },
  "subjectSizeM": [0.02, 8.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "costWeight": 1.3,
  "tags": {"mood": ["premium", "clean", "dramatic"], "energy": ["calm", "medium", "hype"], "palette": ["neutral", "cool"]},
  "tierMax": "T3"
}
```

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests -q -m "not blender"`.

- [ ] **Step 5: Commit**
```bash
git add engine/reflect.py engine/color.py engine/blocks/lighting/reflection_rig engine/tests/test_reflect.py
git commit -m "feat(engine): reflection solver and the reflection_rig lighting block (layout)"
```

### Task 12: `macro_detail` camera, detail targets, detail framing in the checker

A long-lens slide or push onto a detail target. The target comes from the shot's `target`: a
user marker, a ranked ingest detail point, or the subject centre as a fallback. `path.sample`
gains an optional `target` argument (Task 2 already accepts it).

Detail framing check: the camera stays outside the subject box + 10% (the same hard rule as
every shot). The target must stay near frame centre (|ndc| ≤ 0.6) at all 12 samples. The shot
must actually be close: if the whole subject fits in frame, coverage must be ≥ 0.6 (T3-03
"detail shot"), otherwise the distance repair pulls in.

**Files:**
- Create: `engine/targets.py`, `engine/blocks/camera/macro_detail/{block.json,path.py}`,
  `engine/tests/test_macro_detail.py`
- Modify: `engine/checker.py`

- [ ] **Step 1: Write the failing tests** — `engine/tests/test_macro_detail.py`

```python
import copy
import json
from pathlib import Path

from engine.catalog import Catalog
from engine.checker import DETAIL_CENTER, SAMPLES_PER_SHOT, check
from engine.geometry import project
from engine.profile import SubjectProfile
from engine.targets import resolve_target

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()
_CAR = json.loads((FIX / "profile_car.json").read_text())
LAMP = {"kind": "emissive", "point": [2.25, 0.6, 0.7], "normal": [1, 0, 0], "score": 3.0}
CAR = SubjectProfile.from_dict({**_CAR, "detailPoints": [LAMP]})
BASE = json.loads((FIX / "script_valid.json").read_text())


def _macro(**shot):
    s = copy.deepcopy(BASE)
    s["shots"][1] = {"startS": 5, "endS": 10, "focus": "subject",
                     "camera": {"id": "macro_detail", "params": {}}, **shot}
    return s


def _codes(r, sev):
    return {i.code for i in r.issues if i.severity == sev}


def test_macro_on_a_detail_point_passes_and_keeps_it_centred():
    r = check(_macro(target={"detail": 0}), CAR, CAT)
    assert r.ok, [i.to_dict() for i in r.issues if i.severity == "error"]
    shot = r.script["shots"][1]
    sample = CAT.load_camera_path("macro_detail")
    tgt = resolve_target(shot, CAR, [])
    for k in range(SAMPLES_PER_SHOT):
        x, y, depth = project(sample(shot["camera"]["params"], CAR, k / (SAMPLES_PER_SHOT - 1), tgt),
                              tgt.point, "9:16")
        assert depth > 0 and max(abs(x), abs(y)) <= DETAIL_CENTER


def test_missing_target_defaults_to_the_best_detail_point():
    r = check(_macro(), CAR, CAT)
    assert r.ok and "detail_target_defaulted" in _codes(r, "repaired")
    assert r.script["shots"][1]["target"] == {"detail": 0}


def test_unknown_targets_are_errors():
    assert "unknown_target" in _codes(check(_macro(target={"detail": 3}), CAR, CAT), "error")
    assert "unknown_target" in _codes(check(_macro(target={"marker": "nope"}), CAR, CAT), "error")


def test_marker_target_works():
    s = _macro(target={"marker": "lamp"})
    s["markers"] = [{"id": "lamp", "anchor": {"space": "placed", "point": LAMP["point"], "normal": [1, 0, 0]},
                     "text": "macro on the headlight"}]
    assert check(s, CAR, CAT).ok


def test_too_close_macro_is_pushed_out_of_the_subject_margin():
    s = _macro(target={"detail": 0})
    s["shots"][1]["camera"]["params"] = {"distance": 0.1}
    r = check(s, CAR, CAT)
    assert r.ok and "camera_distance_adjusted" in _codes(r, "repaired")
```

- [ ] **Step 2: Run, expect FAIL** — ImportError (`engine.targets`, `DETAIL_CENTER`).

- [ ] **Step 3: Implement** — `engine/targets.py`:

```python
"""Resolve a shot's detail target to a point and normal in placed coordinates."""
import math
from dataclasses import dataclass

DEFAULT_NORMAL = (0.0, -0.957826, 0.287348)  # unit (0, -1, 0.3): side-on, slightly above


@dataclass(frozen=True)
class Target:
    point: tuple
    normal: tuple
    source: str  # "marker:<id>" | "detail:<i>" | "centre"


def _unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return tuple(x / n for x in v) if n > 0 else DEFAULT_NORMAL


def resolve_target(shot, profile, markers):
    """Marker, then detail point, then subject centre. None if the reference does not exist."""
    t = shot.get("target")
    if isinstance(t, dict) and "marker" in t:
        m = next((m for m in markers if m.get("id") == t["marker"]), None)
        if m is None:
            return None
        p = tuple(m["anchor"]["point"])
        n = m["anchor"].get("normal") or [a - b for a, b in zip(p, profile.center)]
        return Target(p, _unit(n), f"marker:{t['marker']}")
    if isinstance(t, dict) and "detail" in t:
        i = t["detail"]
        if i >= len(profile.detailPoints):
            return None
        d = profile.detailPoints[i]
        return Target(tuple(d["point"]), _unit(d["normal"]), f"detail:{i}")
    return Target(tuple(profile.center), DEFAULT_NORMAL, "centre")
```

`engine/blocks/camera/macro_detail/path.py`:

```python
import math
from engine.easing import ease, settle
from engine.geometry import Pose
from engine.targets import DEFAULT_NORMAL

MIN_HEIGHT_M = 0.01
LOOK_DRIFT = 0.15  # how much the aim follows a slide; small keeps the target near centre


def sample(params, profile, u, target=None):
    point, normal = (target.point, target.normal) if target else (profile.center, DEFAULT_NORMAL)
    az = math.atan2(normal[1], normal[0]) + math.radians(params["azimuthOffsetDeg"])
    el0 = math.asin(max(-1.0, min(1.0, normal[2])))
    el = max(math.radians(-10.0), min(math.radians(80.0), el0 + math.radians(params["elevationOffsetDeg"])))
    k = ease(params["easing"], settle(u, params["settleFrac"]))
    d0 = profile.radius * params["distance"]
    out = (math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))
    right = (-math.sin(az), math.cos(az), 0.0)
    if params["move"] == "push":
        d, s = d0 * (1.0 - params["pushFrac"] * k), 0.0
    else:
        d, s = d0, (k - 0.5) * params["slideFrac"] * d0
    pos = [point[i] + out[i] * d + right[i] * s for i in range(3)]
    pos[2] = max(pos[2], MIN_HEIGHT_M)
    look = tuple(point[i] + right[i] * s * LOOK_DRIFT for i in range(3))
    return Pose(position=tuple(pos), target=look, lens_mm=params["lensMm"])
```

`engine/blocks/camera/macro_detail/block.json`:

```json
{
  "id": "macro_detail",
  "kind": "camera",
  "description": "Long-lens close-up on one detail (a lamp, badge, glint, texture or a user marker): a slow lateral slide or gentle push with shallow focus. Use for the detail shots of a sequence. Set the shot's target to {marker: id} or {detail: index}; without one it uses the subject's best detail.",
  "framing": "detail",
  "move": {"param": "move", "map": {"slide": "truck", "push": "dolly"}},
  "params": {
    "distance": {"type": "number", "min": 0.1, "max": 2.0, "default": 0.45},
    "move": {"type": "enum", "values": ["slide", "push"], "default": "slide"},
    "slideFrac": {"type": "number", "min": 0.0, "max": 0.6, "default": 0.4},
    "pushFrac": {"type": "number", "min": 0.0, "max": 0.3, "default": 0.12},
    "azimuthOffsetDeg": {"type": "number", "min": -60.0, "max": 60.0, "default": 20.0},
    "elevationOffsetDeg": {"type": "number", "min": -20.0, "max": 40.0, "default": 10.0},
    "lensMm": {"type": "number", "min": 85.0, "max": 150.0, "default": 100.0},
    "fstop": {"type": "number", "min": 1.4, "max": 8.0, "default": 2.8},
    "easing": {"type": "enum", "values": ["in_out_cubic", "smoothstep", "in_quad"], "default": "in_out_cubic"},
    "settleFrac": {"type": "number", "min": 0.0, "max": 0.5, "default": 0.0}
  },
  "subjectSizeM": [0.02, 8.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "costWeight": 1.0,
  "tags": {"mood": ["premium", "clean", "dramatic"], "energy": ["calm", "medium", "hype"], "palette": []},
  "tierMax": "T3"
}
```

(Lens 85–150 mm: V-C01 detail 85–135, P-C01 detail 85–150, src. Distance range and slide
fractions are (eng).)

`engine/checker.py` changes:

```python
from engine.geometry import box_corners, frame_stats, point_in_box, project
from engine.targets import resolve_target

DETAIL_CENTER = 0.6         # target stays within |ndc| <= 0.6 on detail shots (eng)
DETAIL_MIN_COVERAGE = 0.6   # T3-03: a detail shot fills >= 60% or overflows the frame


def _shot_verdict(sample, params, profile, framing, aspect, target=None):
    """Return 'ok', 'out' (move away), 'in' (move closer) or 'off' (target not centred)."""
    corners = box_corners(profile.boundsMin, profile.boundsMax)
    small = False
    for k in range(SAMPLES_PER_SHOT):
        pose = sample(params, profile, k / (SAMPLES_PER_SHOT - 1), target)
        if pose.position[2] < MIN_CAMERA_Z:
            return "out"
        if point_in_box(pose.position, profile.boundsMin, profile.boundsMax, BOX_MARGIN):
            return "out"
        st = frame_stats(pose, corners, aspect)
        if framing == "full":
            if not st["allInFront"] or not st["inFrame"]:
                return "out"
            if st["coverage"] < MIN_COVERAGE:
                small = True
        else:
            x, y, depth = project(pose, target.point if target else profile.center, aspect)
            if depth <= 0 or max(abs(x), abs(y)) > DETAIL_CENTER:
                return "off"
            if st["allInFront"] and st["inFrame"] and st["coverage"] < DETAIL_MIN_COVERAGE:
                small = True
    return "in" if small else "ok"


def _targets(s, catalog, profile, issues):
    markers = s.get("markers", [])
    for i, sh in enumerate(s["shots"]):
        t = sh.get("target")
        if t is not None and resolve_target(sh, profile, markers) is None:
            issues.append(Issue("unknown_target", f"shots[{i}].target", f"{t} does not exist", "error"))
        elif t is None and catalog.get("camera", sh["camera"]["id"])["framing"] == "detail" and profile.detailPoints:
            sh["target"] = {"detail": 0}
            issues.append(Issue("detail_target_defaulted", f"shots[{i}].target", "best detail point", "repaired"))
```

`_fix_shot`'s signature becomes `def _fix_shot(i, shot, catalog, profile, aspect, markers, issues):`
(markers **before** issues; Task 13 calls it in this order). It computes
`target = resolve_target(shot, profile, markers) if m["framing"] == "detail" else None`, and
passes `target` to every `_shot_verdict` call. In `check()`: call `_targets(s, catalog, profile, issues)`
right after `_compat`, keep the early return on errors, and pass `s.get("markers", [])` to
`_fix_shot`.

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests -q -m "not blender"`. The old
  checker tests must pass unchanged.

- [ ] **Step 5: Commit**
```bash
git add engine/targets.py engine/blocks/camera/macro_detail engine/checker.py engine/tests/test_macro_detail.py
git commit -m "feat(engine): macro_detail camera with marker/detail targets and detail framing checks"
```

### Task 13: `sequence` edit block, TIERS [S] rules, checker sequence stage

`engine/craft_rules.py` holds the TIERS [S] items as pure functions. The checker's `sequence`
stage **enforces** some of them (errors, or repairs where the fix is mechanical). The harness
**scores** all of them. They share one implementation.

Sequence rules (TIERS T3-01..T3-04, T3-13, T3-16; vehicles.md V-E01..V-E05; products.md
P-E01/P-E02/P-E07):

| Rule | Source | Checker action |
|---|---|---|
| Shot count per pace, scaled by duration: calm 3–5, medium 4–6, hype 5–7 per 10 s | T3-01, V-E03 (src 3–7) | error `seq_shot_count` |
| Each shot 0.8–3.5 s; median 1.0–3.0 s | T3-02, V-E03 (eng) | error |
| First shot: full framing, `hook`/`establish`, ≤ 2.5 s | P-E02, T3-15 (eng 2.5) | error `seq_bad_hook` |
| ≥ 1 detail-framing shot | T3-03 | error `seq_no_detail` |
| Last shot: full framing, `hero`/`packshot`, ≥ 1.5 s | T3-16 | error `seq_bad_ending` |
| Adjacent cut ≥ 30° azimuth or ≥ 1.5× screen size | T3-04, V-E05 | **repair**: rotate incoming shot +35°, else error `seq_jump_cut` |
| Last shot ends in ≥ 1.0 s true stillness | T3-13, P-E07 | **repair**: raise `settleFrac`, else error |
| Missing `purpose` | CATALOG-GAPS §2 | **repair**: infer (first=hook, detail framing=detail, last=hero, else motion) |

**Files:**
- Create: `engine/craft_rules.py`, `engine/sequence.py`, `engine/blocks/edit/sequence/block.json`,
  `engine/tests/fixtures/script_t3.json`, `engine/tests/test_craft_rules.py`,
  `engine/tests/test_sequence.py`
- Modify: `engine/checker.py`

- [ ] **Step 1: Fixture** — `engine/tests/fixtures/script_t3.json`, the vehicles.md default
  9:16 10 s template (5 shots), built from blocks that exist now (Task 15 swaps in the T3
  lighting/grade/effect):

```json
{
  "schema": "valora.scene/1",
  "seed": 7,
  "direction": {"id": "clean-studio/hero/medium", "source": "dice"},
  "prompt": "",
  "assumptions": ["empty prompt -> dice direction, vehicle template"],
  "format": {"aspect": "9:16", "durationS": 10, "fps": 30},
  "subject": {"placement": "ground", "motion": {"id": "static", "params": {}}, "finishOverrides": []},
  "world": {"id": "studio_cyc", "params": {"tone": "black", "floorGloss": 0.4}},
  "lighting": {"id": "softbox_three_point", "params": {}},
  "edit": {"id": "sequence", "params": {"pace": "medium"}},
  "shots": [
    {"startS": 0, "endS": 2.0, "purpose": "hook", "focus": "subject",
     "camera": {"id": "low_hero_push", "params": {"azimuthDeg": 35, "distance": 4.0, "lensMm": 40}}},
    {"startS": 2.0, "endS": 3.5, "purpose": "detail", "focus": "subject",
     "camera": {"id": "macro_detail", "params": {"lensMm": 100}}},
    {"startS": 3.5, "endS": 5.5, "purpose": "motion", "focus": "subject",
     "camera": {"id": "arc_orbit", "params": {"startAzimuthDeg": -100, "sweepDeg": 40, "lensMm": 70, "elevationDeg": 8}}},
    {"startS": 5.5, "endS": 7.0, "purpose": "detail", "focus": "subject",
     "camera": {"id": "macro_detail", "params": {"move": "push", "azimuthOffsetDeg": -25}}},
    {"startS": 7.0, "endS": 10.0, "purpose": "hero", "focus": "subject",
     "camera": {"id": "arc_orbit", "params": {"startAzimuthDeg": 60, "sweepDeg": -30, "lensMm": 55, "settleFrac": 0.4}}}
  ],
  "effects": [],
  "grade": {"id": "neutral_film", "params": {}}
}
```

- [ ] **Step 2: Write the failing tests** — `engine/tests/test_craft_rules.py`

```python
import json
from pathlib import Path

from engine.catalog import Catalog
from engine import craft_rules as cr
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()
CAR = SubjectProfile.from_dict(json.loads((FIX / "profile_car.json").read_text()))


def _shot(cam, params, start=0.0, end=3.0):
    return {"startS": start, "endS": end, "camera": {"id": cam, "params": {
        **{k: v["default"] for k, v in CAT.get("camera", cam)["params"].items()}, **params}}}


def test_still_tail_measures_the_settle():
    assert cr.still_tail_s(_shot("arc_orbit", {"settleFrac": 0.4}), CAR, CAT) >= 1.0
    assert cr.still_tail_s(_shot("arc_orbit", {"settleFrac": 0.0}), CAR, CAT) < 0.5


def test_thirty_degree_rule():
    a = _shot("arc_orbit", {"startAzimuthDeg": 0, "sweepDeg": 10})
    b = _shot("arc_orbit", {"startAzimuthDeg": 15, "sweepDeg": 10})
    c = _shot("arc_orbit", {"startAzimuthDeg": 60, "sweepDeg": 10})
    assert cr.cut_ok(a, b, CAR, CAT, "9:16")[0] is False
    assert cr.cut_ok(a, c, CAR, CAT, "9:16")[0] is True


def test_anti_miniature_dof_on_vehicles():
    close_wide_open = _shot("low_hero_push", {"distance": 1.5, "lensMm": 50, "fstop": 1.4})
    far_stopped = _shot("low_hero_push", {"distance": 4.0, "lensMm": 50, "fstop": 8.0})
    assert cr.dof_ok(close_wide_open, CAR, CAT, "9:16") is False
    assert cr.dof_ok(far_stopped, CAR, CAT, "9:16") is True


def test_score_script_reports_every_s_item():
    s = json.loads((FIX / "script_t3.json").read_text())
    from engine.checker import check
    rich = SubjectProfile.from_dict({**CAR.to_dict(), "detailPoints": [
        {"kind": "emissive", "point": [2.25, 0.6, 0.7], "normal": [1, 0, 0], "score": 3.0}]})
    r = check(s, rich, CAT)
    assert r.ok, [i.to_dict() for i in r.issues if i.severity == "error"]
    items = {x.id: x for x in cr.score_script(r.script, rich, CAT)}
    for iid in ("T1-X1", "T1-X3", "T2-01", "T2-03", "T2-04", "T2-05", "T2-07", "T3-01", "T3-02",
                "T3-03", "T3-04", "T3-05", "T3-11", "T3-13", "T3-14", "T3-16", "T3-21", "T4-02",
                "T4-03", "V-C02"):
        assert iid in items, iid
    assert items["T3-02"].status == "pass" and items["T3-13"].status == "pass"
    # studio_cyc carries `"studio": true` (owner 2026-09-24: clean studio meets T2-07).
    # Add that key to engine/blocks/world/studio_cyc/block.json in this task; the catalog
    # only rejects MISSING keys, so an extra flag loads fine. Future non-studio worlds omit it.
    assert items["T2-07"].status == "pass"
    assert items["T4-03"].status == "fail"  # no simulation in v1: honest, not n/a
```

`engine/tests/test_sequence.py`

```python
import copy
import json
from pathlib import Path

from engine.catalog import Catalog
from engine.checker import check
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()
CAR = SubjectProfile.from_dict({**json.loads((FIX / "profile_car.json").read_text()), "detailPoints": [
    {"kind": "emissive", "point": [2.25, 0.6, 0.7], "normal": [1, 0, 0], "score": 3.0}]})
T3 = json.loads((FIX / "script_t3.json").read_text())


def _codes(r, sev):
    return {i.code for i in r.issues if i.severity == sev}


def test_t3_fixture_passes_the_sequence_stage():
    r = check(T3, CAR, CAT)
    assert r.ok, [i.to_dict() for i in r.issues if i.severity == "error"]


def test_manifest_templates_name_real_cameras():
    m = CAT.get("edit", "sequence")
    for fam, slots in m["templates"].items():
        assert slots[0]["purpose"] == "hook" and slots[-1]["purpose"] == "hero", fam
        for slot in slots:
            for cam in slot["cameras"]:
                assert CAT.get("camera", cam) is not None, (fam, cam)


def test_too_few_shots_no_detail_bad_ending():
    s = copy.deepcopy(T3)
    s["shots"] = [dict(T3["shots"][0], endS=2.0), dict(T3["shots"][4], startS=2.0, endS=10.0)]
    codes = _codes(check(s, CAR, CAT), "error")
    assert {"seq_shot_count", "seq_no_detail", "seq_shot_length"} <= codes


def test_jump_cut_is_repaired_by_rotating_the_next_shot():
    s = copy.deepcopy(T3)
    s["shots"][2]["camera"]["params"].update({"startAzimuthDeg": -100, "sweepDeg": 20})
    s["shots"][3] = {"startS": 5.5, "endS": 7.0, "purpose": "motion", "focus": "subject",
                     "camera": {"id": "arc_orbit", "params": {"startAzimuthDeg": -80, "sweepDeg": 10, "lensMm": 70, "elevationDeg": 8}}}
    s["shots"][1]["camera"]["params"]["move"] = "push"  # keep one detail shot
    r = check(s, CAR, CAT)
    assert "jump_cut_rotated" in _codes(r, "repaired"), [i.to_dict() for i in r.issues]


def test_ending_without_stillness_is_settled():
    s = copy.deepcopy(T3)
    s["shots"][4]["camera"]["params"]["settleFrac"] = 0.0
    r = check(s, CAR, CAT)
    assert r.ok and "ending_settled" in _codes(r, "repaired")
    assert r.script["shots"][4]["camera"]["params"]["settleFrac"] >= 1.0 / 3.0


def test_missing_purposes_are_inferred():
    s = copy.deepcopy(T3)
    for sh in s["shots"]:
        sh.pop("purpose")
    r = check(s, CAR, CAT)
    assert r.ok and [sh["purpose"] for sh in r.script["shots"]] == ["hook", "detail", "motion", "detail", "hero"]
```

- [ ] **Step 3: Run, expect FAIL** — ImportError / unknown edit block.

- [ ] **Step 4: Implement** — `engine/craft_rules.py`:

```python
"""TIERS.md [S] items as pure functions. The checker's sequence stage and the eval harness call
the same code, so a script the checker passes scores the same way in the harness.
Numbers marked (eng) are starting values to calibrate (see the plan's calibration table)."""
import math
import statistics
from dataclasses import dataclass

from engine.geometry import _basis, _dot, _sub, box_corners, frame_stats
from engine.grade_plan import changes_look
from engine.targets import resolve_target

COC_MM = 0.03            # full-frame circle of confusion
VEHICLE_SIZE_M = 2.5     # "vehicle-sized" for T3-21 / V-C02 (eng)
ARC_CAP_DEG_S = 80.0     # V-C11 (src: camera-car arm)
STILL_FRAC, STILL_S = 0.02, 1.0   # T3-13 / P-E07 (src)
SCALE_EDGES = ((0.35, "LS"), (0.6, "FS"), (0.9, "MS"), (1.3, "CS"))  # dominant-axis coverage (eng)


@dataclass(frozen=True)
class ItemResult:
    id: str
    status: str          # pass | fail | na | unmeasured
    value: object = None
    detail: str = ""


def shot_pose(shot, u, profile, catalog, markers=()):
    ref = shot["camera"]
    m = catalog.get("camera", ref["id"])
    tgt = resolve_target(shot, profile, list(markers)) if m["framing"] == "detail" else None
    return catalog.load_camera_path(ref["id"])(ref["params"], profile, u, tgt)


def azimuth_deg(pose, profile):
    cx, cy, _ = profile.center
    return math.degrees(math.atan2(pose.position[1] - cy, pose.position[0] - cx))


def coverage(pose, profile, aspect):
    return frame_stats(pose, box_corners(profile.boundsMin, profile.boundsMax), aspect)["coverage"]


def scale_class(cov):
    for edge, name in SCALE_EDGES:
        if cov < edge:
            return name
    return "ECS"


def _wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def cut_ok(prev, nxt, profile, catalog, aspect, markers=()):
    """T3-04 / V-E05: >= 30 deg azimuth change about the subject, or >= 1.5x screen size."""
    a = shot_pose(prev, 1.0, profile, catalog, markers)
    b = shot_pose(nxt, 0.0, profile, catalog, markers)
    d_az = abs(_wrap(azimuth_deg(b, profile) - azimuth_deg(a, profile)))
    ca, cb = coverage(a, profile, aspect), coverage(b, profile, aspect)
    ratio = math.inf if min(ca, cb) <= 0 else max(ca, cb) / min(ca, cb)
    return (d_az >= 30.0 or ratio >= 1.5), d_az, ratio


def _poses(shot, profile, catalog, markers, n):
    return [shot_pose(shot, k / (n - 1), profile, catalog, markers) for k in range(n)]


def still_tail_s(shot, profile, catalog, markers=(), n=121):
    """Seconds of true stillness at the end of the shot (T3-13)."""
    poses = _poses(shot, profile, catalog, markers, n)
    dt = (shot["endS"] - shot["startS"]) / (n - 1)
    speeds = [(math.dist(a.position, b.position) + math.dist(a.target, b.target)) / dt
              for a, b in zip(poses, poses[1:])]
    peak = max(speeds)
    if peak <= 0:
        return shot["endS"] - shot["startS"]
    tail = 0
    for v in reversed(speeds):
        if v >= STILL_FRAC * peak:
            break
        tail += 1
    return tail * dt


def max_arc_rate(shot, profile, catalog, markers=(), n=121):
    poses = _poses(shot, profile, catalog, markers, n)
    dt = (shot["endS"] - shot["startS"]) / (n - 1)
    az = [azimuth_deg(p, profile) for p in poses]
    return max(abs(_wrap(b - a)) / dt for a, b in zip(az, az[1:]))


def dof_ok(shot, profile, catalog, aspect, markers=()):
    """T3-21 anti-miniature (V-C07): a fully framed vehicle-sized subject is sharp end to end,
    and no high (> 30 deg) angle at fstop < 4."""
    pose = shot_pose(shot, 0.5, profile, catalog, markers)
    fwd, _, _ = _basis(pose)
    depths = [_dot(_sub(c, pose.position), fwd) for c in box_corners(profile.boundsMin, profile.boundsMax)]
    focus = _dot(_sub(profile.center, pose.position), fwd)
    f, c, n = pose.lens_mm / 1000.0, COC_MM / 1000.0, shot["camera"]["params"]["fstop"]
    hyper = f * f / (n * c) + f
    near = focus * (hyper - f) / (hyper + focus - 2 * f)
    far = math.inf if focus >= hyper else focus * (hyper - f) / (hyper - focus)
    rel = _sub(pose.position, profile.center)
    elev = math.degrees(math.asin(max(-1.0, min(1.0, rel[2] / math.sqrt(_dot(rel, rel))))))
    return (far - near) >= 1.1 * (max(depths) - min(depths)) and not (elev > 30 and n < 4)


def _res(iid, ok, value=None, detail=""):
    return ItemResult(iid, "pass" if ok else "fail", value, detail)


def _cam(shot, catalog):
    return catalog.get("camera", shot["camera"]["id"])


def primitive(shot, catalog):
    mv = _cam(shot, catalog).get("move")
    if isinstance(mv, dict):
        return mv["map"].get(shot["camera"]["params"].get(mv["param"]))
    return mv


def score_script(s, profile, catalog):
    """Every [S] TIERS item (plus V-C02) for a checked script. [S+M] items return their S half;
    the harness ANDs it with the M half."""
    shots, aspect, dur = s["shots"], s["format"]["aspect"], s["format"]["durationS"]
    markers = s.get("markers", [])
    lens = [sh["endS"] - sh["startS"] for sh in shots]
    world = catalog.get("world", s["world"]["id"])
    light = s["lighting"]
    out = []
    # T1 signatures (a fail caps the render at T1).
    arcs = [sh for sh in shots if sh["camera"]["id"] == "arc_orbit"]
    out.append(_res("T1-X1", not (len(shots) == 1 and any(abs(sh["camera"]["params"]["sweepDeg"]) > 180 for sh in arcs))))
    flat = (light["id"] == "softbox_three_point" and light["params"]["rimStrength"] == 0
            and light["params"]["fillRatio"] > 1 / 1.5)
    out.append(_res("T1-X3", not flat))
    # T2
    out.append(_res("T2-01", bool(world.get("hasGround") or world.get("environment"))))
    eased = all(sh["camera"]["params"].get("easing", "linear") != "linear" or _cam(sh, catalog).get("linearByDesign")
                for sh in shots)
    out.append(_res("T2-03", eased))
    out.append(_res("T2-04", all(primitive(sh, catalog) not in (None, "static") for sh in shots)))
    out.append(ItemResult("T2-05", "pass", 0.5, "by construction: the compiler sets a 180-degree shutter"))
    # Owner 2026-09-24: a clean studio backdrop (world block flagged `studio: true`) meets T2-07.
    atmo = (world.get("atmosphere") or world.get("studio")
            or any(catalog.get("effect", fx["id"]).get("atmosphere") for fx in s.get("effects", [])))
    out.append(_res("T2-07", bool(atmo), detail="S half: an atmosphere block or a studio world is present"))
    out.append(ItemResult("T2-08", "pass" if changes_look(s["grade"]) else "fail", detail="S fallback: grade is not identity"))
    # T3
    per10 = len(shots) / (dur / 10.0)
    out.append(_res("T3-01", 3 <= per10 <= 7, round(per10, 2)))
    med = statistics.median(lens)
    out.append(_res("T3-02", 1.0 <= med <= 3.0 and min(lens) >= 0.5 and lens[-1] >= 1.5, round(med, 2)))
    scales = {scale_class(coverage(shot_pose(sh, 0.5, profile, catalog, markers), profile, aspect))
              if _cam(sh, catalog)["framing"] == "full" else "ECS" for sh in shots}
    has_detail = any(_cam(sh, catalog)["framing"] == "detail" for sh in shots)
    out.append(_res("T3-03", len(scales) >= 2 and has_detail, sorted(scales)))
    cuts = [cut_ok(a, b, profile, catalog, aspect, markers)[0] for a, b in zip(shots, shots[1:])]
    out.append(_res("T3-04", all(cuts), cuts))
    moving = s["subject"]["motion"]["id"] != "static"
    out.append(ItemResult("T3-05", "unmeasured" if moving else "na", detail="subject static" if not moving else ""))
    out.append(_res("T3-11", all(primitive(sh, catalog) for sh in shots)))
    tail = still_tail_s(shots[-1], profile, catalog, markers)
    out.append(_res("T3-13", tail >= STILL_S - 1e-6, round(tail, 2)))
    rate = max(max_arc_rate(sh, profile, catalog, markers) for sh in shots)
    out.append(_res("T3-14", rate <= ARC_CAP_DEG_S, round(rate, 1)))
    last = shots[-1]
    out.append(_res("T3-16", _cam(last, catalog)["framing"] == "full" and lens[-1] >= 1.5
                    and last.get("purpose", "hero") in ("hero", "packshot")))
    vehicle = profile.longest >= VEHICLE_SIZE_M
    full = [sh for sh in shots if _cam(sh, catalog)["framing"] == "full"]
    if vehicle and full:
        out.append(_res("T3-21", all(dof_ok(sh, profile, catalog, aspect, markers) for sh in full)))
        out.append(_res("V-C02", all(sh["camera"]["params"]["lensMm"] >= 28 for sh in full)))
    else:
        out.append(ItemResult("T3-21", "na", detail="not a vehicle-sized full frame"))
        out.append(ItemResult("V-C02", "na"))
    # T4 [S] halves
    out.append(ItemResult("T4-02", "na" if not moving else "fail", detail="no vehicle dynamics block yet"))
    out.append(ItemResult("T4-03", "fail", detail="no simulation blocks in v1 (spec §8)"))
    return out
```

(`changes_look` is defined in Task 14's `engine/grade_plan.py`. Until then, create the module
with only `def changes_look(grade_ref): return True`. Task 14 replaces it with the real function
and its test.)

`engine/sequence.py`:

```python
"""Checker stage for the `sequence` edit block (CATALOG-GAPS rank 2). Rules come from the block
manifest; the maths is engine.craft_rules, shared with the harness."""
import math
import statistics

from engine import craft_rules as cr
from engine.issues import Issue

AZIMUTH_PARAMS = ("azimuthDeg", "startAzimuthDeg", "azimuthOffsetDeg")
JUMP_ROTATE_DEG = 35.0


def _framing(shot, catalog):
    return catalog.get("camera", shot["camera"]["id"])["framing"]


def _fill_purposes(shots, catalog, issues):
    last = len(shots) - 1
    for i, sh in enumerate(shots):
        if "purpose" not in sh:
            p = ("hook" if i == 0 else "hero" if i == last
                 else "detail" if _framing(sh, catalog) == "detail" else "motion")
            sh["purpose"] = p
            issues.append(Issue("purpose_inferred", f"shots[{i}].purpose", p, "repaired"))


def _repair_jump(i, s, profile, catalog, issues):
    shots, markers, aspect = s["shots"], s.get("markers", []), s["format"]["aspect"]
    prm = shots[i]["camera"]["params"]
    key = next((k for k in AZIMUTH_PARAMS if k in prm), None)
    if key is None:
        return False
    spec = catalog.get("camera", shots[i]["camera"]["id"])["params"][key]
    old = prm[key]
    prm[key] = min(max(cr._wrap(old + JUMP_ROTATE_DEG), spec["min"]), spec["max"])
    if cr.cut_ok(shots[i - 1], shots[i], profile, catalog, aspect, markers)[0]:
        issues.append(Issue("jump_cut_rotated", f"shots[{i}].camera.params.{key}", f"{old} -> {prm[key]}", "repaired"))
        return True
    prm[key] = old
    return False


def _repair_ending(s, profile, catalog, issues):
    last = s["shots"][-1]
    spec = catalog.get("camera", last["camera"]["id"])["params"].get("settleFrac")
    if spec is None:
        return False
    prm, length = last["camera"]["params"], last["endS"] - last["startS"]
    old = prm["settleFrac"]
    prm["settleFrac"] = round(min(spec["max"], max(old, (cr.STILL_S + 0.1) / length)), 4)
    if cr.still_tail_s(last, profile, catalog, s.get("markers", [])) >= cr.STILL_S - 1e-6:
        issues.append(Issue("ending_settled", f"shots[{len(s['shots']) - 1}].camera.params.settleFrac",
                            f"{old} -> {prm['settleFrac']}", "repaired"))
        return True
    prm["settleFrac"] = old
    return False


def check_sequence(s, profile, catalog, issues):
    """Enforce the sequence rules. Returns indices of shots whose camera params changed."""
    m = catalog.get("edit", "sequence")
    shots, dur = s["shots"], s["format"]["durationS"]
    changed = set()

    def err(code, path, msg):
        issues.append(Issue(code, path, msg, "error"))

    _fill_purposes(shots, catalog, issues)
    lo, hi = m["shotsPer10s"][s["edit"]["params"]["pace"]]
    n_lo, n_hi = math.floor(lo * dur / 10.0), math.ceil(hi * dur / 10.0)
    if not n_lo <= len(shots) <= n_hi:
        err("seq_shot_count", "shots", f"{len(shots)} shots; this pace wants {n_lo}-{n_hi} in {dur} s")
    lens = [sh["endS"] - sh["startS"] for sh in shots]
    a, b = m["shotLenS"]
    for i, length in enumerate(lens):
        if not a - 1e-9 <= length <= b + 1e-9:
            err("seq_shot_length", f"shots[{i}]", f"{length:.2f} s outside {a}-{b} s")
    ma, mb = m["medianLenS"]
    if not ma <= statistics.median(lens) <= mb:
        err("seq_median_length", "shots", f"median shot outside {ma}-{mb} s")
    if (shots[0]["purpose"] not in ("hook", "establish") or _framing(shots[0], catalog) != "full"
            or lens[0] > m["hookMaxS"] + 1e-9):
        err("seq_bad_hook", "shots[0]", f"first shot: full-framing hook/establish, <= {m['hookMaxS']} s")
    if not any(_framing(sh, catalog) == "detail" for sh in shots):
        err("seq_no_detail", "shots", "needs at least one detail shot (T3-03)")
    if (shots[-1]["purpose"] not in ("hero", "packshot") or _framing(shots[-1], catalog) != "full"
            or lens[-1] < m["lastShotMinS"] - 1e-9):
        err("seq_bad_ending", f"shots[{len(shots) - 1}]", f"last shot: full-framing hero/packshot, >= {m['lastShotMinS']} s")
    for i in range(1, len(shots)):
        ok, d_az, ratio = cr.cut_ok(shots[i - 1], shots[i], profile, catalog, s["format"]["aspect"], s.get("markers", []))
        if ok:
            continue
        if _repair_jump(i, s, profile, catalog, issues):
            changed.add(i)
        else:
            err("seq_jump_cut", f"shots[{i}]", f"{d_az:.0f} deg and {ratio:.2f}x from shot {i - 1} (needs 30 deg or 1.5x)")
    if cr.still_tail_s(shots[-1], profile, catalog, s.get("markers", [])) < cr.STILL_S - 1e-6:
        if _repair_ending(s, profile, catalog, issues):
            changed.add(len(shots) - 1)
        else:
            err("seq_no_still_ending", f"shots[{len(shots) - 1}]", "last move must end in >= 1 s of stillness")
    return changed
```

`engine/checker.py` `check()` tail becomes:

```python
    markers = s.get("markers", [])
    for i, shot in enumerate(s["shots"]):
        _fix_shot(i, shot, catalog, profile, s["format"]["aspect"], markers, issues)
    if not errors(issues) and s.get("edit", {}).get("id") == "sequence":
        for i in sorted(check_sequence(s, profile, catalog, issues)):
            _fix_shot(i, s["shots"][i], catalog, profile, s["format"]["aspect"], markers, issues)
    return CheckResult(not errors(issues), s, issues)
```

`engine/blocks/edit/sequence/block.json` (templates transcribed from the shot-template tables in
vehicles.md, products.md, furniture.md, characters.md; the director reads them in phase 3, the
checker enforces the generic rules):

```json
{
  "id": "sequence",
  "kind": "edit",
  "description": "Edit rhythm of a professional ad. 3-7 shots per 10 s (pace sets where in that range), each 0.8-3.5 s. Open on a full-frame hook, include at least one detail shot, change angle by 30 degrees or size by 1.5x at every cut, and land on a still hero shot of at least 1.5 s. Start from the template for the subject's family and fill each slot with one of its cameras.",
  "params": {"pace": {"type": "enum", "values": ["calm", "medium", "hype"], "default": "medium"}},
  "shotsPer10s": {"calm": [3, 5], "medium": [4, 6], "hype": [5, 7]},
  "shotLenS": [0.8, 3.5],
  "medianLenS": [1.0, 3.0],
  "lastShotMinS": 1.5,
  "hookMaxS": 2.5,
  "templates": {
    "vehicle": [
      {"purpose": "hook", "lenS": [1.5, 2.5], "cameras": ["low_hero_push"]},
      {"purpose": "detail", "lenS": [1.0, 2.0], "cameras": ["macro_detail"], "prefer": "emissive"},
      {"purpose": "motion", "lenS": [1.5, 2.5], "cameras": ["arc_orbit"]},
      {"purpose": "detail", "lenS": [1.0, 2.0], "cameras": ["macro_detail"]},
      {"purpose": "hero", "lenS": [2.5, 3.5], "cameras": ["arc_orbit"], "settle": true}
    ],
    "product": [
      {"purpose": "hook", "lenS": [2.0, 2.5], "cameras": ["low_hero_push"]},
      {"purpose": "detail", "lenS": [1.5, 2.0], "cameras": ["macro_detail"], "prefer": "glossy_peak"},
      {"purpose": "motion", "lenS": [1.5, 2.5], "cameras": ["arc_orbit"]},
      {"purpose": "hero", "lenS": [3.0, 3.5], "cameras": ["arc_orbit"], "settle": true}
    ],
    "furniture": [
      {"purpose": "hook", "lenS": [2.0, 2.5], "cameras": ["low_hero_push"]},
      {"purpose": "detail", "lenS": [1.5, 2.0], "cameras": ["macro_detail"], "prefer": "textured"},
      {"purpose": "motion", "lenS": [2.0, 2.5], "cameras": ["arc_orbit"]},
      {"purpose": "hero", "lenS": [2.5, 3.5], "cameras": ["arc_orbit"], "settle": true}
    ],
    "character": [
      {"purpose": "hook", "lenS": [2.0, 2.5], "cameras": ["low_hero_push"]},
      {"purpose": "detail", "lenS": [1.5, 2.0], "cameras": ["macro_detail"]},
      {"purpose": "motion", "lenS": [2.0, 2.5], "cameras": ["arc_orbit"]},
      {"purpose": "hero", "lenS": [2.5, 3.0], "cameras": ["arc_orbit"], "settle": true}
    ]
  },
  "subjectSizeM": [0.02, 30.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "costWeight": 1.0,
  "tags": {"mood": [], "energy": ["calm", "medium", "hype"], "palette": []},
  "tierMax": "T3"
}
```

- [ ] **Step 5: Run, expect PASS** — `py -m pytest engine/tests -q -m "not blender"`. If
  `test_t3_fixture_passes_the_sequence_stage` fails on a cut, adjust the **fixture's** azimuths.
  Never loosen a rule to make a fixture pass: the rules are the point.

- [ ] **Step 6: Commit**
```bash
git add engine/craft_rules.py engine/sequence.py engine/grade_plan.py engine/blocks/edit engine/checker.py engine/tests/fixtures/script_t3.json engine/tests/test_craft_rules.py engine/tests/test_sequence.py
git commit -m "feat(engine): sequence edit block, TIERS script-level rules, checker sequence stage"
```

### Task 14: Grade plans and the `mood_grade` block

A pure grade plan is a dict that `engine/blender/grade.py` (Task 23) turns into compositor nodes.
`neutral_film` becomes the `clean` preset of the same plan (CATALOG-GAPS §3), so there is one
realiser. The six presets match spec §4.3 "6 presets". Every preset number is **(eng)**,
calibrated through T2-08, T3-08, T3-19, T3-20. The separation default is **(src)** V-G01 1.10–1.20.

**Files:**
- Create/replace: `engine/grade_plan.py`, `engine/blocks/grade/mood_grade/block.json`,
  `engine/tests/test_grade_plan.py`

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from engine.catalog import Catalog
from engine.grade_plan import PRESETS, changes_look, plan_for

CAT = Catalog.load()


def _ref(bid, **params):
    return {"id": bid, "params": {**{k: v["default"] for k, v in CAT.get("grade", bid)["params"].items()}, **params}}


def test_mood_grade_offers_six_presets_matching_the_plan():
    assert set(CAT.get("grade", "mood_grade")["params"]["preset"]["values"]) == set(PRESETS) and len(PRESETS) == 6


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_every_preset_builds_a_complete_plan(preset):
    p = plan_for(_ref("mood_grade", preset=preset))
    assert set(p) == {"agxLookCandidates", "exposureEv", "lift", "gamma", "gain", "contrast",
                      "saturation", "subjectSat", "backgroundSat", "bloom", "halation", "vignette"}
    assert p["agxLookCandidates"][-1] == "None"  # always a safe fallback


def test_separation_splits_saturation_between_subject_and_background():
    p = plan_for(_ref("mood_grade", separation=1.2))
    assert p["subjectSat"] / p["backgroundSat"] == pytest.approx(1.2)


def test_effects_scale_zero_turns_bloom_halation_vignette_off():
    p = plan_for(_ref("mood_grade", preset="teal_night", effectsScale=0.0))
    assert p["bloom"]["strength"] == 0 and p["halation"] is None and p["vignette"] == 0


def test_neutral_film_is_the_clean_preset():
    p = plan_for(_ref("neutral_film", bloom=0.3))
    assert p["bloom"]["strength"] == 0.3 and p["agxLookCandidates"][0] == "AgX - Base Contrast"


def test_changes_look():
    assert changes_look(_ref("mood_grade", preset="noir"))
    assert not changes_look(_ref("neutral_film", agxLook="none", contrast=1.0, saturation=1.0, bloom=0.0))
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `engine/grade_plan.py`:

```python
"""Pure grade plans for neutral_film and mood_grade; engine/blender/grade.py realises them.
Preset numbers are (eng) starting values: calibrate via harness items T2-08, T3-08, T3-19, T3-20."""

# Look names differ across Blender versions; the realiser tries them in order ("None" last).
AGX_LOOKS = {
    "none": ["None"],
    "base": ["AgX - Base Contrast", "Base Contrast", "None"],
    "medium_high": ["AgX - Medium High Contrast", "Medium High Contrast", "None"],
    "high": ["AgX - High Contrast", "High Contrast", "None"],
    "very_high": ["AgX - Very High Contrast", "Very High Contrast", "None"],
}

PRESETS = {
    "clean":        {"agx": "base",        "lift": (1.0, 1.0, 1.0),      "gain": (1.0, 1.0, 1.0),    "sat": 1.00, "bloom": 0.10, "halation": 0.00, "vignette": 0.00},
    "premium_dark": {"agx": "medium_high", "lift": (0.985, 0.985, 0.99), "gain": (1.0, 1.0, 1.0),    "sat": 0.95, "bloom": 0.15, "halation": 0.10, "vignette": 0.25},
    "warm_golden":  {"agx": "medium_high", "lift": (1.0, 0.995, 0.985),  "gain": (1.04, 1.0, 0.93),  "sat": 1.08, "bloom": 0.20, "halation": 0.20, "vignette": 0.15},
    "teal_night":   {"agx": "high",        "lift": (0.98, 1.0, 1.02),    "gain": (1.03, 1.0, 0.96),  "sat": 1.05, "bloom": 0.25, "halation": 0.25, "vignette": 0.30},
    "noir":         {"agx": "very_high",   "lift": (0.98, 0.98, 0.98),   "gain": (1.0, 1.0, 1.0),    "sat": 0.10, "bloom": 0.10, "halation": 0.00, "vignette": 0.35},
    "vivid":        {"agx": "high",        "lift": (1.0, 1.0, 1.0),      "gain": (1.0, 1.0, 1.0),    "sat": 1.18, "bloom": 0.15, "halation": 0.05, "vignette": 0.10},
}


def _plan(preset, *, contrast, saturation, separation, effects, exposure_ev, agx=None, bloom=None):
    p = PRESETS[preset]
    halation = p["halation"] * effects
    return {
        "agxLookCandidates": AGX_LOOKS[agx or p["agx"]],
        "exposureEv": exposure_ev,
        "lift": p["lift"], "gamma": (1.0, 1.0, 1.0), "gain": p["gain"],
        "contrast": round((contrast - 1.0) * 50.0, 4),   # Bright/Contrast node units (eng)
        "saturation": p["sat"] * saturation,
        "subjectSat": separation ** 0.5, "backgroundSat": separation ** -0.5,  # ratio = separation (V-G01)
        "bloom": {"strength": p["bloom"] * effects if bloom is None else bloom, "threshold": 1.0, "size": 0.2},
        "halation": None if halation <= 0 else {"strength": halation, "threshold": 1.2, "size": 0.45,
                                                "tint": (1.0, 0.58, 0.38)},  # V-G05 orange near
        "vignette": p["vignette"] * effects,
    }


def plan_for(grade_ref):
    """Plan for a checked grade block reference {id, params}."""
    q = grade_ref["params"]
    if grade_ref["id"] == "neutral_film":
        return _plan("clean", contrast=q["contrast"], saturation=q["saturation"], separation=q["separation"],
                     effects=1.0, exposure_ev=0.0, agx=q["agxLook"], bloom=q["bloom"])
    if grade_ref["id"] == "mood_grade":
        return _plan(q["preset"], contrast=q["contrast"], saturation=q["saturation"],
                     separation=q["separation"], effects=q["effectsScale"], exposure_ev=q["exposureEv"])
    raise ValueError(f"no grade plan for {grade_ref['id']!r}")


def changes_look(grade_ref):
    """TIERS T2-08 script-level fallback: True unless the grade is visually identity."""
    p = plan_for(grade_ref)
    return not (p["agxLookCandidates"] == ["None"] and p["contrast"] == 0 and p["saturation"] == 1.0
                and p["bloom"]["strength"] == 0 and p["halation"] is None and p["vignette"] == 0
                and p["lift"] == (1.0, 1.0, 1.0) and p["gain"] == (1.0, 1.0, 1.0))
```

`engine/blocks/grade/mood_grade/block.json`:

```json
{
  "id": "mood_grade",
  "kind": "grade",
  "description": "Finished commercial grade with a mood preset: clean (true colours), premium_dark (deep blacks, soft vignette), warm_golden (golden-hour warmth, gentle halation), teal_night (cool shadows, warm highlights, glow on lights), noir (near monochrome, hard contrast; use rarely), vivid (punchy saturated). Always keeps the subject a little more saturated than its surroundings and never clips highlights.",
  "params": {
    "preset": {"type": "enum", "values": ["clean", "premium_dark", "warm_golden", "teal_night", "noir", "vivid"], "default": "premium_dark"},
    "contrast": {"type": "number", "min": 0.8, "max": 1.4, "default": 1.0},
    "saturation": {"type": "number", "min": 0.6, "max": 1.4, "default": 1.0},
    "separation": {"type": "number", "min": 1.0, "max": 1.25, "default": 1.12},
    "effectsScale": {"type": "number", "min": 0.0, "max": 1.5, "default": 1.0},
    "exposureEv": {"type": "number", "min": -1.0, "max": 1.0, "default": 0.0}
  },
  "subjectSizeM": [0.02, 30.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "costWeight": 1.0,
  "tags": {"mood": ["clean", "premium", "dramatic", "warm", "night", "noir", "vivid"], "energy": ["calm", "medium", "hype"], "palette": ["neutral", "warm", "teal", "mono", "saturated"]},
  "tierMax": "T3"
}
```

Film grain (V-G05 "grain temporally varying", T4-04) is **deferred**: Blender 5.0's compositor
has no grain node, and a noise-texture grain needs per-frame seeding. T4 only.

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests -q -m "not blender"`.

- [ ] **Step 5: Commit**
```bash
git add engine/grade_plan.py engine/blocks/grade/mood_grade engine/tests/test_grade_plan.py
git commit -m "feat(engine): grade plans; mood_grade with six presets and subject separation"
```

### Task 15: `haze_volume` effect; the T3 fixture uses the T3 blocks

A world-filling volume, depth-graded by nature (V-W02, V-L16, C-L06). A clear pocket around the
subject keeps it crisp, so background contrast drops while the subject stays sharp (T2-07's [M]
half). The pocket idea is ported from render-studio's `distance_fog`
(`C:\Users\deand\Projects\ModVision\tools\render-studio\rain_look.py:391`). Density is relative
and scaled by the subject radius in `build.py`, so a watch and a car get the same look.
Numbers are (eng).

**Files:**
- Create: `engine/blocks/effect/haze_volume/block.json`
- Modify: `engine/tests/fixtures/script_t3.json`, `engine/tests/test_craft_rules.py`

- [ ] **Step 1: Manifest**

```json
{
  "id": "haze_volume",
  "kind": "effect",
  "description": "Soft atmospheric haze filling the set. Pushes the background back (lower contrast with distance) while a clear pocket keeps the subject crisp, and makes light beams visible when a light sits behind the subject. Light (0.1-0.3) for studio products, heavier (0.4-0.8) for moody cars and night scenes.",
  "atmosphere": true,
  "params": {
    "density": {"type": "number", "min": 0.0, "max": 1.0, "default": 0.25},
    "anisotropy": {"type": "number", "min": 0.0, "max": 0.8, "default": 0.4},
    "clearPocket": {"type": "bool", "default": true},
    "tint": {"type": "enum", "values": ["neutral", "warm", "cool"], "default": "neutral"}
  },
  "subjectSizeM": [0.02, 30.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "costWeight": 2.5,
  "tags": {"mood": ["dramatic", "premium", "night"], "energy": ["calm", "medium", "hype"], "palette": []},
  "tierMax": "T3"
}
```

- [ ] **Step 2: Switch the T3 fixture to the T3 blocks** — in `script_t3.json` set
  `"lighting": {"id": "reflection_rig", "params": {}}`,
  `"effects": [{"id": "haze_volume", "params": {"density": 0.2}}]`,
  `"grade": {"id": "mood_grade", "params": {"preset": "premium_dark"}}`. In
  `test_score_script_reports_every_s_item` change the T2-07 assertion to
  `assert items["T2-07"].status == "pass"`.

- [ ] **Step 3: Run, expect PASS** — `py -m pytest engine/tests -q -m "not blender"`.

- [ ] **Step 4: Commit**
```bash
git add engine/blocks/effect engine/tests/fixtures/script_t3.json engine/tests/test_craft_rules.py
git commit -m "feat(engine): haze_volume atmosphere block; T3 fixture uses reflection_rig, haze, mood_grade"
```

---

## Chunk 4: The compiler (JSON scene script → Blender scene → render)

Spec §4.5 fixed build order: world → subject placement → lighting → effects → cameras and cuts →
grade → render settings for the tier. The pure parts (camera keys, cuts, key frames, tiers,
container argv) are tested without Blender. The Blender parts are tested by compiling tiny scenes
and **probing** them: the compiler writes facts about the built scene to `compile.json`, and the
test compares them with the pure maths. Rendering tests render at most 3 frames at 144×256 and
4 samples.

**Porting sources** (read them, don't import them): `tools/product-render/render_product.py`
in this repo's working tree (cyclorama `:181`, `add_area` `:239`, `setup_cycles` `:476`,
`setup_colour` `:537`) and the owner's render-studio in
`C:\Users\deand\Projects\ModVision\tools\render-studio\` (`film_camera.py:367` cuts in the
closed-shutter gap, `rain_look.py:335` compositor). Both are the owner's own code. ModVision's
files and its `beauty-render` task are **not modified** (spec §2).

### Task 16: Camera rotation matrix and the frame timeline (pure)

**Files:**
- Modify: `engine/geometry.py`
- Create: `engine/compiler/__init__.py` (empty), `engine/compiler/timeline.py`,
  `engine/tests/test_timeline.py`

- [ ] **Step 1: Write the failing tests** — `engine/tests/test_timeline.py`

```python
import json
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.compiler.timeline import camera_keys, frame_count, key_frames, shot_u
from engine.geometry import Pose, _basis, camera_matrix
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()
CAR = SubjectProfile.from_dict(json.loads((FIX / "profile_car.json").read_text()))
SCRIPT = check(json.loads((FIX / "script_valid.json").read_text()), CAR, CAT).script  # 0-5 s, 5-10 s


def test_camera_matrix_is_a_rotation_whose_minus_z_is_forward():
    pose = Pose((3.0, -4.0, 1.0), (0.0, 0.0, 0.5), 50.0)
    m = camera_matrix(pose)
    cols = [[m[r][c] for r in range(3)] for c in range(3)]
    for i in range(3):
        for j in range(3):
            assert sum(a * b for a, b in zip(cols[i], cols[j])) == pytest.approx(1.0 if i == j else 0.0, abs=1e-12)
    fwd, right, up = _basis(pose)
    assert cols[0] == pytest.approx(list(right)) and cols[1] == pytest.approx(list(up))
    assert [-v for v in cols[2]] == pytest.approx(list(fwd))


def test_frame_count_and_shot_u_hit_both_ends():
    assert frame_count(SCRIPT["format"]) == 300
    sh = SCRIPT["shots"][0]
    assert shot_u(sh, 0.0, 30) == 0.0
    assert shot_u(sh, 5.0 - 1 / 30, 30) == pytest.approx(1.0)  # last frame of the shot reaches u=1


def test_keys_cover_every_frame_plus_blur_margins_and_cut_subframes():
    keys = camera_keys(SCRIPT, CAR, CAT)
    frames = [k.frame for k in keys]
    assert frames == sorted(frames) and len(set(frames)) == len(frames)
    assert len(keys) == 300 + 2 + 2  # frames 0..301, plus two subframe keys for the one cut
    assert frames[0] == 0 and frames[-1] == 301


def test_cut_lands_in_the_closed_shutter_gap():
    keys = camera_keys(SCRIPT, CAR, CAT)
    by = {k.frame: k for k in keys}
    assert by[150.25].shot == 0 and by[150.75].shot == 1
    assert max(k.frame for k in keys if k.shot == 0) == 150.25
    assert min(k.frame for k in keys if k.shot == 1) == 150.75


def test_integer_frame_keys_equal_the_checker_path():
    keys = camera_keys(SCRIPT, CAR, CAT)
    sample = CAT.load_camera_path("low_hero_push")
    p = SCRIPT["shots"][0]["camera"]["params"]
    k1 = next(k for k in keys if k.frame == 1)
    assert k1.pose == sample(p, CAR, 0.0, None)
    k150 = next(k for k in keys if k.frame == 150)
    assert k150.pose == sample(p, CAR, 1.0, None)
    assert k1.focusM > 0 and k1.fstop == p["fstop"]


def test_key_frames_are_few_and_include_the_hook_frame():
    assert key_frames(SCRIPT) == [16, 76, 226, 300]
    assert key_frames(SCRIPT, limit=3) == [16, 226, 300]
```

- [ ] **Step 2: Run, expect FAIL** — ImportError.

- [ ] **Step 3: Implement** — in `engine/geometry.py`:

```python
def camera_matrix(pose):
    """3x3 world rotation (rows) for a Blender camera, which looks down its local -Z with +Y up.
    Columns are (right, up, -forward) from _basis. The compiler MUST build camera rotation from
    this, never from a TRACK_TO constraint (see _basis)."""
    fwd, right, up = _basis(pose)
    return tuple((right[i], up[i], -fwd[i]) for i in range(3))


def focus_depth(pose, point):
    """Distance from the camera to `point` along the view axis (what Blender's DOF uses)."""
    fwd, _, _ = _basis(pose)
    return _dot(_sub(point, pose.position), fwd)
```

`engine/compiler/timeline.py`:

```python
"""Pure frame timeline: which shot and camera pose every Blender frame gets, and the cut keys.

Blender frame f (1-based) shows time t = (f - 1) / fps. With a centred 0.5 shutter, frame f-1
exposes until f-0.75 and frame f from f-0.25. At a cut the camera jumps between keys at those two
subframes, so no exposure ever sees the jump. This ports render-studio film_camera.animate
(ModVision tools/render-studio/film_camera.py:367)."""
from dataclasses import dataclass

from engine.geometry import Pose, focus_depth
from engine.targets import resolve_target


@dataclass(frozen=True)
class CamKey:
    frame: float
    shot: int
    pose: Pose
    fstop: float
    focusM: float


def frame_count(fmt):
    return int(round(fmt["durationS"] * fmt["fps"]))


def shot_index(shots, t):
    i = 0
    for k, sh in enumerate(shots):
        if sh["startS"] <= t + 1e-9:
            i = k
    return i


def shot_u(shot, t, fps):
    """Progress through a shot; the shot's last frame reaches exactly u = 1 (what the checker sampled)."""
    span = shot["endS"] - shot["startS"] - 1.0 / fps
    if span <= 0:
        return 0.0
    return min(max((t - shot["startS"]) / span, 0.0), 1.0)


def _key(frame, i, s, profile, catalog):
    fps, sh = s["format"]["fps"], s["shots"][i]
    ref = sh["camera"]
    detail = catalog.get("camera", ref["id"])["framing"] == "detail"
    tgt = resolve_target(sh, profile, s.get("markers", [])) if detail else None
    pose = catalog.load_camera_path(ref["id"])(ref["params"], profile, shot_u(sh, (frame - 1) / fps, fps), tgt)
    focus = tgt.point if tgt else profile.center  # spec §4.6: focus is by construction
    return CamKey(frame, i, pose, ref["params"]["fstop"], max(focus_depth(pose, focus), 1e-3))


def camera_keys(s, profile, catalog):
    fps, n, shots = s["format"]["fps"], frame_count(s["format"]), s["shots"]
    keys, prev = [], None
    for f in range(0, n + 2):  # frames 0 and n+1 give motion blur data past both ends
        i = shot_index(shots, (f - 1) / fps)
        if prev is not None and i != prev:
            keys.append(_key(f - 0.75, prev, s, profile, catalog))
            keys.append(_key(f - 0.25, i, s, profile, catalog))
        keys.append(_key(f, i, s, profile, catalog))
        prev = i
    return keys


def key_frames(s, limit=None):
    """A few frames that stand for the clip: the hook frame (t = 0.5 s, TIERS T3-15), each shot's
    middle, and the last frame. Tests pass limit=3. Never render a full sequence in a test."""
    fps, n = s["format"]["fps"], frame_count(s["format"])
    frames = [int(round(0.5 * fps)) + 1, n]
    frames += [int(round((sh["startS"] + sh["endS"]) / 2 * fps)) + 1 for sh in s["shots"]]
    out = sorted({max(1, min(n, f)) for f in frames})
    if limit and len(out) > limit:
        idx = sorted({round(k * (len(out) - 1) / (limit - 1)) for k in range(limit)}) if limit > 1 else [0]
        out = [out[j] for j in idx]
    return out
```

(The cut test: frame 151 is the first frame of shot 1 (t = 5.0), so the subframe keys are
150.25 and 150.75.)

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests/test_timeline.py -q`.

- [ ] **Step 5: Commit**
```bash
git add engine/geometry.py engine/compiler engine/tests/test_timeline.py
git commit -m "feat(compiler): camera rotation from _basis, frame timeline with cuts in the closed-shutter gap"
```

### Task 17: Safe Blender launch, farm container argv, render tiers (pure)

Carry-forward: farm containers get a memory limit and no network. The farm itself is phase 6,
but the argv is written and tested now so phase 6 cannot forget it. Every local Blender launch
(ingest and compile) also gets `--offline-mode`. Blender 5.0 supports it; verified with
`blender --help` on 2026-09-24: "Disallow internet access, overriding the preference".

**Files:**
- Create: `engine/blender_cli.py`, `engine/compiler/sandbox.py`, `engine/compiler/tiers.py`,
  `engine/tests/test_launch.py`
- Modify: `engine/ingest/run.py` (use `blender_argv`; keep re-exporting `BLENDER`)

- [ ] **Step 1: Write the failing tests** — `engine/tests/test_launch.py`

```python
import pytest

from engine.blender_cli import SAFE_FLAGS, blender_argv
from engine.compiler.sandbox import container_argv
from engine.compiler.tiers import TIERS, resolution


def test_blender_argv_is_safe_and_ends_with_the_args():
    argv = blender_argv("x.py", ["job.json"], blender="B")
    assert argv[0] == "B" and argv[-1] == "job.json" and argv[-2] == "--"
    for flag in ("--background", "--factory-startup", "--disable-autoexec", "--offline-mode"):
        assert flag in argv and flag in SAFE_FLAGS


def test_container_has_no_network_and_a_hard_memory_cap():
    argv = container_argv("valora/render:1", "/jobs/abc", memory_gb=24)
    for a in ("--network=none", "--memory=24g", "--memory-swap=24g", "--read-only",
              "--cap-drop=ALL", "--security-opt=no-new-privileges"):
        assert a in argv, a
    assert argv.count("-v") == 1 and "/jobs/abc:/job:rw" in argv
    assert any(a.startswith("--pids-limit=") for a in argv)


@pytest.mark.parametrize("aspect,short,want", [("9:16", 540, (540, 960)), ("16:9", 1080, (1920, 1080)),
                                               ("4:5", 540, (540, 676)), ("1:1", 144, (144, 144))])
def test_resolution_is_even_and_keeps_aspect(aspect, short, want):
    assert resolution(aspect, short) == want


def test_tiers():
    assert set(TIERS) == {"keyframes", "preview", "final"}
    assert TIERS["keyframes"]["samples"] <= 8 and TIERS["preview"]["samples"] < TIERS["final"]["samples"]
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `engine/blender_cli.py`:

```python
"""Where Blender is and how every launch is locked down (spec §7: uploads are untrusted)."""
import os

BLENDER = os.environ.get("BLENDER_EXE", r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
SAFE_FLAGS = ("--background", "--factory-startup", "--disable-autoexec", "--offline-mode",
              "--python-exit-code", "1")


def blender_argv(script, args, blender=None):
    return [blender or BLENDER, *SAFE_FLAGS, "--python", str(script), "--", *map(str, args)]
```

In `engine/ingest/run.py`: `from engine.blender_cli import BLENDER, blender_argv` (delete the
local `BLENDER =` line) and build `cmd = blender_argv(EXTRACT, [model_path, raw_path])`.

`engine/compiler/sandbox.py`:

```python
"""Farm worker container (phase 6 runs it). Carry-forward from the phase-1 review: a hard memory
cap and NO network. An upload is untrusted; the job dir is the only thing mounted."""


def container_argv(image, job_dir, *, memory_gb=24, cpus=8, gpus="all", pids=512):
    return ["docker", "run", "--rm",
            "--network=none",
            f"--memory={memory_gb}g", f"--memory-swap={memory_gb}g",
            f"--cpus={cpus}", f"--pids-limit={pids}",
            "--read-only", "--tmpfs", "/tmp:rw,size=4g",
            "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--user", "1000:1000", f"--gpus={gpus}",
            "-v", f"{job_dir}:/job:rw",
            image]
```

`engine/compiler/tiers.py`:

```python
"""Render tiers (spec §4.7). `keyframes` exists for tests and eval only. Preview = composition and
motion in minutes. Final = the paid clip. Sample counts are (eng): the final default follows the
engine survey's measured 192 spp baseline, and the spec's open question 2 (price per clip) may
change it."""
from engine.geometry import aspect_wh

SHUTTER = 0.5  # 180 degrees, centred (TIERS T2-05)

TIERS = {
    "keyframes": {"shortSide": 144, "samples": 4, "denoise": True, "passes": True},
    "preview": {"shortSide": 540, "samples": 16, "denoise": True, "passes": True},
    "final": {"shortSide": 1080, "samples": 192, "denoise": True, "passes": False},
}


def _even(x):
    x = int(round(x))
    return x + (x % 2)


def resolution(aspect, short_side):
    w, h = aspect_wh(aspect)
    if w <= h:
        return _even(short_side), _even(short_side * h / w)
    return _even(short_side * w / h), _even(short_side)
```

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests -q -m "not blender"` (the
  mocked `test_run.py` still passes: `cmd[-1]` is still the raw JSON path).

- [ ] **Step 5: Commit**
```bash
git add engine/blender_cli.py engine/compiler/sandbox.py engine/compiler/tiers.py engine/ingest/run.py engine/tests/test_launch.py
git commit -m "feat(compiler): offline Blender launches, farm container argv (no network, memory cap), render tiers"
```

### Task 18: Block builders, `BuildContext`, per-block seeds, hero pose

**Files:**
- Modify: `engine/catalog.py` (`load_builder`)
- Create: `engine/compiler/context.py`, `engine/tests/test_context.py`

Rule for every `build.py`: define `build(ctx)` and **import `bpy` inside it**, never at module
level. That lets the catalog load and check every builder outside Blender (Task 24's
completeness test).

- [ ] **Step 1: Write the failing tests** — `engine/tests/test_context.py`

```python
import json
from pathlib import Path

import pytest

from engine.catalog import Catalog, CatalogError
from engine.checker import check
from engine.compiler.context import block_seed, hero_pose
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()
CAR = SubjectProfile.from_dict(json.loads((FIX / "profile_car.json").read_text()))


def _write(root, kind, bid, build_src=None):
    d = root / kind / bid
    d.mkdir(parents=True)
    (d / "block.json").write_text(json.dumps({
        "id": bid, "kind": kind, "description": "x", "params": {}, "subjectSizeM": [0.1, 1.0],
        "aspects": ["9:16"], "costWeight": 1.0, "tags": {"mood": [], "energy": [], "palette": []},
        "tierMax": "T2"}))
    if build_src is not None:
        (d / "build.py").write_text(build_src)


def test_load_builder(tmp_path):
    _write(tmp_path, "world", "w", "def build(ctx):\n    return 'built'\n")
    assert Catalog.load(tmp_path).load_builder("world", "w")(None) == "built"


@pytest.mark.parametrize("bid", ["nope", "../world/w", "", "a/b"])
def test_load_builder_rejects_unknown_or_unsafe(tmp_path, bid):
    _write(tmp_path, "world", "w", "def build(ctx):\n    pass\n")
    with pytest.raises(CatalogError):
        Catalog.load(tmp_path).load_builder("world", bid)


def test_load_builder_missing_file_or_function(tmp_path):
    _write(tmp_path, "world", "a")
    _write(tmp_path, "world", "b", "x = 1\n")
    cat = Catalog.load(tmp_path)
    with pytest.raises(CatalogError, match="build.py"):
        cat.load_builder("world", "a")
    with pytest.raises(CatalogError, match="build"):
        cat.load_builder("world", "b")


def test_block_seed_is_deterministic_and_per_block():
    assert block_seed(7, "lighting", "reflection_rig") == block_seed(7, "lighting", "reflection_rig")
    assert block_seed(7, "lighting", "reflection_rig") != block_seed(8, "lighting", "reflection_rig")
    assert block_seed(7, "lighting", "reflection_rig") != block_seed(7, "effect", "haze_volume")


def test_hero_pose_is_mid_last_hero_shot():
    s = check(json.loads((FIX / "script_valid.json").read_text()), CAR, CAT).script
    sample = CAT.load_camera_path("arc_orbit")
    assert hero_pose(s, CAR, CAT) == sample(s["shots"][1]["camera"]["params"], CAR, 0.5, None)
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — in `Catalog`, factor the id guard and module loading out of
  `load_camera_path` into `_load_module(kind, bid, filename, attr)` (same checks: string, no `/`,
  `\`, `..`, known block, file exists, import errors wrapped, attribute callable). Cache per
  `(kind, bid, filename)`. Then:

```python
    def load_camera_path(self, bid):
        return self._load_module("camera", bid, "path.py", "sample")

    def load_builder(self, kind, bid):
        """build.py's build(ctx). build.py must import bpy inside build(), never at module level."""
        return self._load_module(kind, bid, "build.py", "build")
```

Keep the existing error messages ("camera id … is not a valid block id", "unknown camera",
  "missing path.py", "has no callable sample()"): put the block kind into each message so
  phase-1 tests pass unchanged. The old `_camera_paths` cache is replaced by the
  per-`(kind, id, file)` cache.

`engine/compiler/context.py`:

```python
"""What a block's build(ctx) receives. Pure: Blender objects are passed in, never imported here."""
import hashlib
import random
from dataclasses import dataclass, field

from engine.targets import resolve_target


@dataclass
class BuildContext:
    scene: object            # bpy.types.Scene
    profile: object          # SubjectProfile
    script: dict             # the checked script
    params: dict             # this block's params
    seed: int                # this block's own seed (block_seed)
    rng: random.Random
    subject: object          # the placed subject root (bpy object)
    meshes: list             # subject mesh objects
    hero_pose: object        # engine.geometry.Pose the rig and world face
    camera_positions: list = field(default_factory=list)  # every camera key position (haze domain)
    catalog: object = None


def block_seed(seed, kind, bid):
    """Per-block seed so blocks never share random streams (spec §4.2 seed drives everything)."""
    return int(hashlib.sha256(f"{seed}:{kind}:{bid}".encode()).hexdigest()[:8], 16)


def hero_pose(s, profile, catalog):
    """Mid-point of the last 'hero'/'packshot' shot, else of the last shot."""
    shots = s["shots"]
    shot = next((sh for sh in reversed(shots) if sh.get("purpose") in ("hero", "packshot")), shots[-1])
    ref = shot["camera"]
    tgt = (resolve_target(shot, profile, s.get("markers", []))
           if catalog.get("camera", ref["id"])["framing"] == "detail" else None)
    return catalog.load_camera_path(ref["id"])(ref["params"], profile, 0.5, tgt)
```

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests -q -m "not blender"`.

- [ ] **Step 5: Commit**
```bash
git add engine/catalog.py engine/compiler/context.py engine/tests/test_context.py
git commit -m "feat(compiler): block builders, BuildContext, per-block seeds, hero pose"
```

### Task 19: Compiler skeleton — job, subject placement, placement guard

**Files:**
- Create: `engine/compiler/blender_main.py`, `engine/compiler/run.py`,
  `engine/tests/test_compile_blender.py`

- [ ] **Step 1: Write the failing test** — `engine/tests/test_compile_blender.py`

```python
import json
from pathlib import Path

import pytest

from engine.compiler.run import compile_scene
from engine.profile import SubjectProfile
from engine.tests.conftest import requires_blender

pytestmark = [pytest.mark.blender, requires_blender]
FIX = Path(__file__).parent / "fixtures"
MODELS = Path(__file__).resolve().parents[2] / "assets-in" / "models"


def _profile(name):
    return SubjectProfile.from_dict(json.loads((FIX / "profiles" / f"{name}.json").read_text(encoding="utf-8")))


def _script(name="script_valid.json"):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("model", ["toycar", "pocket_watch"])
def test_subject_is_placed_exactly_where_the_profile_says(model, tmp_path):
    glb = MODELS / model / f"{model}.glb"
    if not glb.exists():
        pytest.skip("model not present")
    prof = _profile(model)
    res = compile_scene(_script(), prof, glb, tmp_path, render=False, build_blocks=False)
    lo, hi = res["placedBounds"][:3], res["placedBounds"][3:]
    tol = 1e-4 * max(prof.sizeM) + 1e-6
    assert lo == pytest.approx(prof.boundsMin, abs=tol) and hi == pytest.approx(prof.boundsMax, abs=tol)
    assert lo[2] == pytest.approx(0.0, abs=tol)


def test_unit_scaled_subject_is_scaled_and_placed(tmp_path):
    # Every reference model has scaleFactor 1.0, so without this the scale and source-centre
    # terms of the placement formula would never be exercised.
    from engine.ingest.run import ingest
    from engine.tests.blender_fixtures import make_glb
    glb = make_glb("scaled", tmp_path / "scaled.glb")
    prof = ingest(glb, workdir=tmp_path / "w")
    assert prof.scaleFactor == 0.001 and prof.sourceCenter[0] == pytest.approx(30.0)
    res = compile_scene(_script(), prof, glb, tmp_path / "c", render=False, build_blocks=False)
    tol = 1e-4 * max(prof.sizeM) + 1e-6
    assert res["placedBounds"] == pytest.approx(prof.boundsMin + prof.boundsMax, abs=tol)


def test_failing_script_never_reaches_blender(tmp_path):
    from engine.compiler.run import CheckFailed
    bad = _script()
    bad["world"]["id"] = "moon"
    with pytest.raises(CheckFailed):
        compile_scene(bad, _profile("toycar"), MODELS / "toycar" / "toycar.glb", tmp_path)
    assert not (tmp_path / "job.json").exists()
```

- [ ] **Step 2: Run, expect FAIL** — ImportError.

- [ ] **Step 3: Implement** — `engine/compiler/run.py`:

```python
"""Host side of the compiler: check, write the job, run headless Blender, read the results.
A script that fails the checker never reaches Blender (spec §4.6)."""
import json
import subprocess
from pathlib import Path

from engine.blender_cli import blender_argv
from engine.catalog import Catalog
from engine.checker import check
from engine.compiler.timeline import key_frames
from engine.ingest.run import preflight
from engine.issues import errors

BLENDER_MAIN = Path(__file__).with_name("blender_main.py")


class CheckFailed(ValueError):
    pass


def _tail(text, n=2000):
    return (text or "").strip()[-n:] or "(empty)"


def compile_scene(script, profile, model, out_dir, *, tier="preview", frames="key", key_limit=None,
                  render=True, save_blend=False, build_blocks=True, skip_kinds=(), probe=None,
                  catalog=None, timeout_s=3600):
    r = check(script, profile, catalog or Catalog.load())
    if not r.ok:
        raise CheckFailed("; ".join(f"{i.code} at {i.path}: {i.message}" for i in errors(r.issues)))
    preflight(model)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if frames == "key":
        frames = key_frames(r.script, limit=key_limit)
    job = {"script": r.script, "profile": profile.to_dict(), "model": str(Path(model).resolve()),
           "tier": tier, "frames": frames, "out": str(out.resolve()), "render": render,
           "saveBlend": save_blend, "buildBlocks": build_blocks, "skipKinds": list(skip_kinds),
           "probe": probe or []}
    (out / "job.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
    proc = subprocess.run(blender_argv(BLENDER_MAIN, [out / "job.json"]), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout_s)
    done = out / "compile.json"
    if proc.returncode != 0 or not done.exists():
        raise RuntimeError(f"Blender compile failed (exit {proc.returncode})\n"
                           f"--- stdout tail ---\n{_tail(proc.stdout)}\n--- stderr tail ---\n{_tail(proc.stderr)}")
    return json.loads(done.read_text(encoding="utf-8"))
```

`engine/compiler/blender_main.py` (skeleton; Tasks 20–24 fill in `build_all` and rendering):

```python
"""Runs INSIDE Blender. Builds the scene for an already-checked script and renders the requested
frames. Launch only through engine/compiler/run.py, which runs the checker first."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))  # phase-1 carry-forward: the engine package is importable here

import bpy  # noqa: E402

from engine.blender.scene_io import import_subject, world_bounds  # noqa: E402
from engine.profile import SubjectProfile  # noqa: E402

PLACEMENT_TOL = 1e-4  # of the subject's longest side


def place_subject(objs, profile):
    """placed = (v - (sourceCenter.xy, sourceMinZ)) * scaleFactor, as a root empty's transform."""
    root = bpy.data.objects.new("valora_subject", None)
    bpy.context.scene.collection.objects.link(root)
    for o in objs:
        if o.parent is None:
            o.parent = root  # parent inverse stays identity, so the root transform applies as-is
    f, c = profile.scaleFactor, profile.sourceCenter
    root.scale = (f, f, f)
    root.location = (-c[0] * f, -c[1] * f, -profile.sourceMinZ * f)
    bpy.context.view_layer.update()
    return root


def assert_placement(meshes, profile):
    lo, hi = world_bounds(meshes, bpy.context.evaluated_depsgraph_get())
    got = [float(v) for v in list(lo) + list(hi)]
    want = list(profile.boundsMin) + list(profile.boundsMax)
    tol = PLACEMENT_TOL * max(profile.sizeM) + 1e-6
    if profile.boundsPosed:  # this pose must fit inside the union over all poses
        ok = all(g >= w - tol for g, w in zip(got[:3], want[:3])) and all(g <= w + tol for g, w in zip(got[3:], want[3:]))
    else:
        ok = all(abs(g - w) <= tol for g, w in zip(got, want))
    if not ok:
        raise SystemExit(f"placement mismatch: got {got}, profile says {want}")
    return got


def main():
    job = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
    out = Path(job["out"])
    profile = SubjectProfile.from_dict(job["profile"])
    objs, meshes = import_subject(job["model"])
    root = place_subject(objs, profile)
    result = {"blender": bpy.app.version_string, "placedBounds": assert_placement(meshes, profile)}
    # Tasks 20-24: build_all(...), camera, passes, render.
    if job.get("saveBlend"):
        bpy.ops.wm.save_as_mainfile(filepath=str(out / "scene.blend"))
    (out / "compile.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests/test_compile_blender.py -q`.
  If placement mismatches, the importer settings differ between ingest and compile. Both must
  call `import_subject`. Do not widen the tolerance.

- [ ] **Step 5: Commit**
```bash
git add engine/compiler/blender_main.py engine/compiler/run.py engine/tests/test_compile_blender.py
git commit -m "feat(compiler): headless compile job; subject placed from the profile with a bounds guard"
```

### Task 20: Camera build — keyframes from the timeline, rotation from `_basis`

The key test: for sampled frames, Blender's own projection of the subject box
(`bpy_extras.object_utils.world_to_camera_view`) must equal `engine.geometry.project` for the
same frame. If it does, what the checker approved is what renders.

**Files:** Modify `engine/compiler/blender_main.py`; Test `engine/tests/test_compile_blender.py`

- [ ] **Step 1: Write the failing test** — append:

```python
from engine.catalog import Catalog
from engine.checker import check
from engine.compiler.timeline import camera_keys
from engine.geometry import box_corners, project


def test_blender_camera_projects_exactly_like_the_checker(tmp_path):
    prof, cat = _profile("toycar"), Catalog.load()
    s = check(_script(), prof, cat).script
    frames = [1, 75, 150, 151, 300]  # includes both sides of the cut
    res = compile_scene(s, prof, MODELS / "toycar" / "toycar.glb", tmp_path, render=False,
                        skip_kinds=("world", "motion", "lighting", "effect", "grade"), probe=frames)
    keys = {k.frame: k for k in camera_keys(s, prof, cat)}
    corners = box_corners(prof.boundsMin, prof.boundsMax)
    for f in frames:
        got = res["probe"][str(f)]["corners"]
        for c, g in zip(corners, got):
            x, y, _ = project(keys[f].pose, c, s["format"]["aspect"])
            assert g[0] == pytest.approx((x + 1) / 2, abs=1e-3) and g[1] == pytest.approx((y + 1) / 2, abs=1e-3), f
        assert res["probe"][str(f)]["lens"] == pytest.approx(keys[f].pose.lens_mm)
        assert res["probe"][str(f)]["focus"] == pytest.approx(keys[f].focusM, rel=1e-4)
    assert res["shutter"] == 0.5 and res["frameEnd"] == 300
```

- [ ] **Step 2: Run, expect FAIL** — KeyError `probe`.

- [ ] **Step 3: Implement** — add to `blender_main.py`:

```python
from mathutils import Matrix, Vector  # noqa: E402

from engine.catalog import Catalog  # noqa: E402
from engine.compiler.tiers import SHUTTER, TIERS, resolution  # noqa: E402
from engine.compiler.timeline import camera_keys, frame_count  # noqa: E402
from engine.geometry import camera_matrix  # noqa: E402


def _fcurves(action):
    """F-curves of an action, for both Blender 5 layered actions and legacy ones
    (ported from render-studio film_camera.animate)."""
    if hasattr(action, "layers"):
        return [c for layer in action.layers for strip in layer.strips for bag in strip.channelbags for c in bag.fcurves]
    return list(action.fcurves)


def build_camera(scene, keys, profile):
    data = bpy.data.cameras.new("valora_camera")
    data.sensor_fit, data.sensor_width = "AUTO", 36.0  # = geometry.SENSOR_MM on the long side
    data.dof.use_dof = True
    data.clip_start = max(1e-4, 0.005 * profile.radius)
    data.clip_end = 400.0 * profile.radius
    cam = bpy.data.objects.new("valora_camera", data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    prev = None
    for k in keys:
        eul = Matrix(camera_matrix(k.pose)).to_euler("XYZ", prev) if prev else Matrix(camera_matrix(k.pose)).to_euler("XYZ")
        prev = eul  # compatible Euler: no 360-degree flips between keys (they would smear motion blur)
        cam.location, cam.rotation_euler = k.pose.position, eul
        data.lens, data.dof.focus_distance, data.dof.aperture_fstop = k.pose.lens_mm, k.focusM, k.fstop
        cam.keyframe_insert("location", frame=k.frame)
        cam.keyframe_insert("rotation_euler", frame=k.frame)
        for path in ("lens", "dof.focus_distance", "dof.aperture_fstop"):
            data.keyframe_insert(data_path=path, frame=k.frame)
    for owner in (cam, data):  # dense keys already carry the easing; linear stops overshoot at cuts
        for curve in _fcurves(owner.animation_data.action):
            for kp in curve.keyframe_points:
                kp.interpolation = "LINEAR"
    return cam


def setup_timing(scene, script, tier):
    fmt = script["format"]
    scene.render.fps, scene.render.fps_base = fmt["fps"], 1.0
    scene.frame_start, scene.frame_end = 1, frame_count(fmt)
    scene.render.resolution_x, scene.render.resolution_y = resolution(fmt["aspect"], TIERS[tier]["shortSide"])
    scene.render.resolution_percentage = 100
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = SHUTTER
    scene.render.motion_blur_position = "CENTER"


def probe(scene, cam, frames, profile):
    from bpy_extras.object_utils import world_to_camera_view
    from engine.geometry import box_corners
    out = {}
    for f in frames:
        scene.frame_set(f)
        corners = [list(world_to_camera_view(scene, cam, Vector(c)))
                   for c in box_corners(profile.boundsMin, profile.boundsMax)]
        out[str(f)] = {"corners": corners, "lens": cam.data.lens, "focus": cam.data.dof.focus_distance}
    return out
```

In `main()`, after placement: `catalog = Catalog.load()`, `script = job["script"]`,
`keys = camera_keys(script, profile, catalog)`, `setup_timing(scene, script, job["tier"])`, then
(after the block builds of Tasks 21–23, which go before the camera per spec order)
`cam = build_camera(scene, keys, profile)`. Record `result["shutter"]`, `result["frameEnd"]`,
and `result["probe"] = probe(scene, cam, job["probe"], profile)` when `job["probe"]` is non-empty.

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests/test_compile_blender.py -q`.
  A mismatch means the rotation or the sensor fit disagrees with `geometry.py`. Fix the compiler,
  never the tolerance.

- [ ] **Step 5: Commit**
```bash
git add engine/compiler/blender_main.py engine/tests/test_compile_blender.py
git commit -m "feat(compiler): keyframed camera from the timeline; Blender projection matches the checker"
```

### Task 21: Build the starter blocks — `studio_cyc`, `softbox_three_point`, `static`

**Files:**
- Create: `engine/softbox.py`, `engine/blender/lights.py`, `engine/blocks/world/studio_cyc/build.py`,
  `engine/blocks/lighting/softbox_three_point/build.py`, `engine/blocks/motion/static/build.py`,
  `engine/tests/test_softbox.py`
- Modify: `engine/compiler/blender_main.py` (`build_all`), `engine/tests/test_compile_blender.py`

- [ ] **Step 1: Write the failing tests** — pure `engine/tests/test_softbox.py`:

```python
import json
import math
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.geometry import point_in_box
from engine.profile import SubjectProfile
from engine.softbox import softbox_layout

FIX = Path(__file__).parent / "fixtures"
CAR = SubjectProfile.from_dict(json.loads((FIX / "profile_car.json").read_text()))
P = {k: v["default"] for k, v in Catalog.load().get("lighting", "softbox_three_point")["params"].items()}


def test_key_is_offset_from_the_hero_camera_and_all_lights_clear_the_subject():
    rig = softbox_layout(CAR, (10.0, 0.0, 1.0), P)  # hero camera on +x
    key = next(l for l in rig.lights if l.role == "key")
    assert math.degrees(math.atan2(key.center[1], key.center[0])) == pytest.approx(P["keyAzimuthDeg"], abs=1e-6)
    assert {l.role for l in rig.lights} == {"key", "fill", "rim"}
    assert all(not point_in_box(l.center, CAR.boundsMin, CAR.boundsMax, 0.10) for l in rig.lights)
```

Append to `engine/tests/test_compile_blender.py`:

```python
def test_studio_scene_has_cyc_and_three_softboxes(tmp_path):
    prof = _profile("toycar")
    res = compile_scene(_script(), prof, MODELS / "toycar" / "toycar.glb", tmp_path, render=False,
                        skip_kinds=("grade",))
    names = {o["name"]: o for o in res["objects"]}
    assert "valora_cyc" in names
    for n in ("valora_key", "valora_fill", "valora_rim"):
        assert names[n]["type"] == "LIGHT" and names[n]["visibleCamera"] is False
    assert res["built"] == ["world:studio_cyc", "motion:static", "lighting:softbox_three_point"]
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `engine/softbox.py` (pure, reuses `LightSpec`/`RigLayout`):

```python
"""softbox_three_point layout, relative to the hero camera. Pure. Distances/sizes are (eng),
re-authored in subject radii from product-render's 1 m-normalised rig (engine spec §10.8)."""
import math

from engine.geometry import _norm, _sub
from engine.reflect import LightSpec, RigLayout


def softbox_layout(profile, hero_pos, params):
    cx, cy, cz = profile.center
    r = profile.radius
    hero_az = math.degrees(math.atan2(hero_pos[1] - cy, hero_pos[0] - cx))

    def at(az_deg, el_deg, dist):
        az, el = math.radians(az_deg), math.radians(el_deg)
        return (cx + dist * math.cos(el) * math.cos(az), cy + dist * math.cos(el) * math.sin(az),
                cz + dist * math.sin(el))

    def spec(name, role, c, sx, sy, power):
        return LightSpec(name, role, c, _norm(_sub(profile.center, c)), sx, sy, power)

    key = at(hero_az + params["keyAzimuthDeg"], params["keyElevationDeg"], 3.0 * r)
    fill = at(hero_az - 40.0, 15.0, 3.5 * r)
    rim = at(hero_az + 150.0, 38.0, 3.0 * r)
    return RigLayout((spec("valora_key", "key", key, 1.2 * r, 0.9 * r, 1.0),
                      spec("valora_fill", "fill", fill, 1.5 * r, 1.0 * r, params["fillRatio"]),
                      spec("valora_rim", "rim", rim, 0.5 * r, 1.1 * r, params["rimStrength"])),
                     ambient=0.05)
```

(Also extend the `LightSpec.role` comment in `reflect.py` with `key | fill`.)

`engine/blender/lights.py`:

```python
"""Realise LightSpecs in Blender. K_RADIANCE is (eng): calibrate on golden renders (T3-07, T3-08)."""
import bpy
from mathutils import Vector

from engine.color import kelvin_to_rgb

K_RADIANCE = 200.0   # watts per m^2 of emitter at power 1.0 (eng); constant radiance at any size
WORLD_FILL = 0.5     # world strength at ambient 1.0 (eng)


def area_light(scene, spec, kelvin, ev=0.0):
    ld = bpy.data.lights.new(spec.name, "AREA")
    ld.shape, ld.size, ld.size_y = "RECTANGLE", spec.sizeX, spec.sizeY
    ld.energy = K_RADIANCE * spec.power * spec.sizeX * spec.sizeY * 2.0 ** ev
    ld.color = kelvin_to_rgb(kelvin)
    ob = bpy.data.objects.new(spec.name, ld)
    scene.collection.objects.link(ob)
    ob.location = spec.center
    ob.rotation_euler = Vector(spec.facing).to_track_quat("-Z", "Y").to_euler()  # area lights emit along -Z
    ob.visible_camera = False  # V-L01: lights are seen in reflections, never directly
    return ob


def black_card(scene, spec):
    """Negative fill (V-L10): a matte black plane seen only in reflections; casts no shadow."""
    hx, hy = spec.sizeX / 2, spec.sizeY / 2
    me = bpy.data.meshes.new(spec.name)
    me.from_pydata([(-hx, -hy, 0), (hx, -hy, 0), (hx, hy, 0), (-hx, hy, 0)], [], [(0, 1, 2, 3)])
    mat = bpy.data.materials.new(spec.name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)
    bsdf.inputs["Roughness"].default_value = 1.0
    me.materials.append(mat)
    ob = bpy.data.objects.new(spec.name, me)
    scene.collection.objects.link(ob)
    ob.location = spec.center
    ob.rotation_euler = Vector(spec.facing).to_track_quat("Z", "Y").to_euler()
    ob.visible_camera, ob.visible_shadow = False, False
    return ob


def realise(scene, layout, kelvin, ev=0.0):
    for spec in layout.lights:
        if spec.role == "negfill":
            black_card(scene, spec)
        else:
            area_light(scene, spec, kelvin, ev)
    bg = scene.world.node_tree.nodes.get("valora_world_bg") if scene.world else None
    if bg is not None:
        bg.inputs["Strength"].default_value = WORLD_FILL * layout.ambient
```

`engine/blocks/lighting/softbox_three_point/build.py`:

```python
def build(ctx):
    from engine.blender.lights import realise
    from engine.softbox import softbox_layout
    realise(ctx.scene, softbox_layout(ctx.profile, ctx.hero_pose.position, ctx.params), ctx.params["colorTempK"])
```

`engine/blocks/motion/static/build.py`:

```python
def build(ctx):
    """The subject does not move; the camera carries all the motion."""
```

`engine/blocks/world/studio_cyc/build.py`: port `build_cyclorama`
(`tools/product-render/render_product.py:181-237`) inside `build(ctx)`, with these changes:
- every length × `k = ctx.profile.longest` (product-render worked at longest = 1 m);
- object and mesh named `valora_cyc`;
- `rotation_euler.z = hero_az + pi/2` where `hero_az = atan2(hero.y - cy, hero.x - cx)`, so the
  wall's local +Y points away from the hero camera;
- tone table (eng): `white` albedo 0.8, `grey` 0.18, `black` 0.02; glossy mix factor
  `0.3 * floorGloss`, glossy roughness 0.25;
- a world named from `bpy.data.worlds.new("valora_world")` whose Background node is named
  `valora_world_bg`: Texture Coordinate (Generated) → Separate XYZ → Math GREATER_THAN 0 →
  Mix (RGBA) between `lower = upper * lowerHemisphereGain` and `upper = tone albedo * 0.5`
  (V-L06).

`build_all` in `blender_main.py` (spec order; cameras are built by the compiler itself):

```python
import random  # noqa: E402

from engine.compiler.context import BuildContext, block_seed, hero_pose  # noqa: E402


def _refs(script):
    yield "world", script["world"]
    yield "motion", script["subject"]["motion"]
    yield "lighting", script["lighting"]
    for fx in script.get("effects", []):
        yield "effect", fx


def build_all(scene, script, profile, catalog, root, meshes, keys, skip_kinds):
    hero = hero_pose(script, profile, catalog)
    built = []
    for kind, ref in _refs(script):
        if kind in skip_kinds:
            continue
        seed = block_seed(script["seed"], kind, ref["id"])
        ctx = BuildContext(scene, profile, script, ref["params"], seed, random.Random(seed), root, meshes,
                           hero, [k.pose.position for k in keys], catalog)
        catalog.load_builder(kind, ref["id"])(ctx)
        built.append(f"{kind}:{ref['id']}")
    return built, hero
```

In `main()`, if `job["buildBlocks"]`: `result["built"], hero = build_all(...)` before
`build_camera`. The grade builds after the camera (Task 23). Add
`result["objects"] = [{"name": o.name, "type": o.type, "location": list(o.location), "visibleCamera": o.visible_camera} for o in scene.objects]`.

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests -q`.

- [ ] **Step 5: Commit**
```bash
git add engine/softbox.py engine/reflect.py engine/blender/lights.py engine/blocks/world/studio_cyc/build.py engine/blocks/lighting/softbox_three_point/build.py engine/blocks/motion/static/build.py engine/compiler/blender_main.py engine/tests/test_softbox.py engine/tests/test_compile_blender.py
git commit -m "feat(compiler): build studio_cyc, softbox_three_point and static in spec order"
```

### Task 22: Build `reflection_rig` and `haze_volume`

> Camera visibility: every rig object (area lights and negfill black cards) MUST get `visible_camera = False` from `LightSpec.cameraVisible` (default False) — invisible to camera rays, still visible in glossy reflections (V-L01).

**Files:**
- Create: `engine/blocks/lighting/reflection_rig/build.py`, `engine/blocks/effect/haze_volume/build.py`
- Test: `engine/tests/test_compile_blender.py`

- [ ] **Step 1: Write the failing test** — append:

```python
from engine.geometry import point_in_box


def test_t3_scene_builds_reflection_rig_and_haze(tmp_path):
    prof = _profile("toycar")
    res = compile_scene(_script("script_t3.json"), prof, MODELS / "toycar" / "toycar.glb", tmp_path,
                        render=False, skip_kinds=("grade",))
    objs = {o["name"]: o for o in res["objects"]}
    assert "valora_overhead" in objs and any(n.startswith("valora_strip_") for n in objs)
    assert any(n.startswith("valora_negfill_") for n in objs)
    for o in res["objects"]:
        if o["name"].startswith(("valora_overhead", "valora_strip_", "valora_accent_", "valora_rim")):
            assert not point_in_box(o["location"], prof.boundsMin, prof.boundsMax, 0.10), o["name"]
    lo, hi = res["hazeDomain"]
    for p in res["cameraPositions"]:
        assert all(l <= v <= h for v, l, h in zip(p, lo, hi))
```

If `check(script_t3, toycar)` fails for the 7 cm toy car, fix the **fixture** (for example the
azimuths). Never change a rule to pass a fixture.

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `reflection_rig/build.py`:

```python
def build(ctx):
    from engine.blender.lights import realise
    from engine.reflect import rig_layout
    layout = rig_layout(ctx.profile, ctx.hero_pose.position, ctx.params)
    realise(ctx.scene, layout, ctx.params["colorTempK"], ctx.params["exposureEv"])
```

`haze_volume/build.py`:

```python
HAZE_K = 0.4        # optical depth ~0.5 across 5 radii at density 0.25 (eng: calibrate via T2-07 [M])
TINTS = {"neutral": (1.0, 1.0, 1.0, 1.0), "warm": (1.0, 0.93, 0.85, 1.0), "cool": (0.86, 0.93, 1.0, 1.0)}


def build(ctx):
    import bpy
    p, prof = ctx.params, ctx.profile
    r = prof.radius
    pts = list(ctx.camera_positions) + [tuple(prof.boundsMin), tuple(prof.boundsMax)]
    lo = [min(q[i] for q in pts) for i in range(3)]
    hi = [max(q[i] for q in pts) for i in range(3)]
    pad = 0.2 * max(h - l for l, h in zip(lo, hi)) + 0.5 * r
    lo = [lo[0] - pad, lo[1] - pad, -0.01 * r]
    hi = [hi[0] + pad, hi[1] + pad, hi[2] + pad]
    me = bpy.data.meshes.new("valora_haze")
    v = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    ob = bpy.data.objects.new("valora_haze", me)
    ctx.scene.collection.objects.link(ob)
    mat = bpy.data.materials.new("valora_haze")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = TINTS[p["tint"]]
    vol.inputs["Anisotropy"].default_value = p["anisotropy"]
    density = p["density"] * HAZE_K / r
    if p["clearPocket"]:
        centre = bpy.data.objects.new("valora_subject_centre", None)
        ctx.scene.collection.objects.link(centre)
        centre.location = prof.center
        tc = nt.nodes.new("ShaderNodeTexCoord"); tc.object = centre
        length = nt.nodes.new("ShaderNodeVectorMath"); length.operation = "LENGTH"
        ramp = nt.nodes.new("ShaderNodeMapRange")
        ramp.inputs["From Min"].default_value, ramp.inputs["From Max"].default_value = 1.0 * r, 2.0 * r
        ramp.inputs["To Min"].default_value, ramp.inputs["To Max"].default_value = 0.0, density
        nt.links.new(tc.outputs["Object"], length.inputs[0])
        nt.links.new(length.outputs["Value"], ramp.inputs["Value"])
        nt.links.new(ramp.outputs["Result"], vol.inputs["Density"])
    else:
        vol.inputs["Density"].default_value = density
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    me.materials.append(mat)
    ob.visible_shadow = False
    ctx.scene["valora_haze_domain"] = [lo, hi]
```

In `main()`, record `result["hazeDomain"] = scene.get("valora_haze_domain")` converted to lists,
and `result["cameraPositions"] = [list(k.pose.position) for k in keys]`.

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests/test_compile_blender.py -q`.

- [ ] **Step 5: Commit**
```bash
git add engine/blocks/lighting/reflection_rig/build.py engine/blocks/effect/haze_volume/build.py engine/compiler/blender_main.py engine/tests/test_compile_blender.py
git commit -m "feat(compiler): build reflection_rig lights and cards, haze_volume with a clear pocket"
```

### Task 23: Grade realiser — compositor, AgX look, subject separation

**Files:**
- Create: `engine/blender/grade.py`, `engine/blocks/grade/neutral_film/build.py`,
  `engine/blocks/grade/mood_grade/build.py`
- Modify: `engine/compiler/blender_main.py`; Test `engine/tests/test_compile_blender.py`

- [ ] **Step 1: Probe the Blender 5.0 compositor API** (this plan cannot verify it offline).
  Run the probe below. Adapt node type names and socket names in Step 3 to what it prints.
  render-studio's `rain_look.py:335` already works on 5.0: it uses `scene.compositing_node_group`,
  a `NodeGroupOutput`, and node properties exposed as **inputs** (e.g. Glare `Type` via
  `inputs['Type']`).
```bash
"C:/Program Files/Blender Foundation/Blender 5.0/blender.exe" --background --factory-startup --python-expr "
import bpy
t = bpy.data.node_groups.new('probe', 'CompositorNodeTree')
for n in ('CompositorNodeRLayers','CompositorNodeExposure','CompositorNodeColorBalance','CompositorNodeIDMask','CompositorNodeHueSat','CompositorNodeBrightContrast','CompositorNodeGlare','CompositorNodeEllipseMask','CompositorNodeBlur','CompositorNodeMixRGB','CompositorNodeOutputFile'):
    try:
        x = t.nodes.new(n); print(n, 'IN', [s.name for s in x.inputs], 'OUT', [s.name for s in x.outputs])
    except Exception as e: print(n, 'MISSING', e)
print([i.identifier for i in bpy.types.ColorManagedViewSettings.bl_rna.properties['look'].enum_items])
"
```
  (`look` is a dynamic enum; if the list prints empty, set `view_transform = "AgX"` on a scene
  first and read `scene.view_settings.bl_rna.properties["look"].enum_items` from it.)

- [ ] **Step 2: Write the failing test** — append:

```python
def test_grade_builds_a_compositor_and_a_valid_look(tmp_path):
    prof = _profile("toycar")
    res = compile_scene(_script("script_t3.json"), prof, MODELS / "toycar" / "toycar.glb", tmp_path, render=False)
    g = res["grade"]
    assert g["viewTransform"] == "AgX" and g["look"] != ""
    for node in ("exposure", "lgg", "separation_mix", "bloom", "vignette"):
        assert node in g["nodes"], node
    assert g["objectIndexPass"] is True and g["subjectPassIndex"] == 1
```

- [ ] **Step 3: Implement** — `engine/blender/grade.py` realises `engine.grade_plan.plan_for(ref)`:

```python
"""Realise a pure grade plan as a Blender 5 compositor tree (port of render-studio
rain_look.compositor, generalised and no longer rain-gated). Node names are stable ids the
tests and passes code look up."""
import bpy


def _set_view(scene, plan):
    vs = scene.view_settings
    vs.view_transform = "AgX"
    for look in plan["agxLookCandidates"]:
        try:
            vs.look = look
            break
        except TypeError:
            continue
    vs.exposure, vs.gamma = plan["exposureEv"], 1.0


def realise(scene, plan, subject_meshes):
    _set_view(scene, plan)
    scene.view_layers[0].use_pass_object_index = True
    for o in subject_meshes:
        o.pass_index = 1
    tree = bpy.data.node_groups.new("valora_grade", "CompositorNodeTree")
    tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    scene.compositing_node_group = tree
    N, L = tree.nodes, tree.links

    def node(kind, name):
        n = N.new(kind)
        n.name = name
        return n

    src = node("CompositorNodeRLayers", "render_layers")
    src.scene = scene
    lgg = node("CompositorNodeColorBalance", "lgg")
    lgg.inputs["Type"].default_value = "Lift/Gamma/Gain"
    for sock, rgb in (("Lift", plan["lift"]), ("Gamma", plan["gamma"]), ("Gain", plan["gain"])):
        next(s for s in lgg.inputs if s.name == sock and s.type == "RGBA").default_value = (*rgb, 1.0)
    idm = node("CompositorNodeIDMask", "subject_mask")
    idm.inputs["Index"].default_value = 1  # probe: may be a property `index` on older builds
    sat_s = node("CompositorNodeHueSat", "subject_sat")
    sat_b = node("CompositorNodeHueSat", "background_sat")
    sat_s.inputs["Saturation"].default_value = plan["saturation"] * plan["subjectSat"]
    sat_b.inputs["Saturation"].default_value = plan["saturation"] * plan["backgroundSat"]
    mix = node("CompositorNodeMixRGB", "separation_mix")  # probe: 5.0 may name this differently
    bc = node("CompositorNodeBrightContrast", "contrast")
    bc.inputs["Contrast"].default_value = plan["contrast"]
    bloom = node("CompositorNodeGlare", "bloom")
    bloom.inputs["Type"].default_value = "Fog Glow"
    bloom.inputs["Threshold"].default_value = plan["bloom"]["threshold"]
    bloom.inputs["Strength"].default_value = plan["bloom"]["strength"]
    bloom.inputs["Size"].default_value = plan["bloom"]["size"]
    # ... exposure node first in the chain (named "exposure"), optional "halation" glare with Tint,
    # "vignette": EllipseMask -> Blur -> multiply toward black by plan["vignette"], then output.
    # Wire: render_layers.Image -> exposure -> lgg -> {subject_sat, background_sat} -> separation_mix
    # (factor = subject_mask.Alpha from render_layers.IndexOB) -> contrast -> bloom [-> halation]
    # -> vignette -> NodeGroupOutput.Image
    return tree
```

Write out the elided wiring in full, using the socket names the Step 1 probe printed. Keep the
node **names** exactly as listed; the test and Task 24's pass outputs look them up.

`neutral_film/build.py` and `mood_grade/build.py` are the same function:

```python
def build(ctx):
    from engine.blender.grade import realise
    from engine.grade_plan import plan_for
    realise(ctx.scene, plan_for({"id": ctx.script["grade"]["id"], "params": ctx.params}), ctx.meshes)
```

In `blender_main.main()`: after `build_camera`, build the grade block (unless `grade` is in
`skipKinds`) through `build_all`'s context pattern. Then record
`result["grade"] = {"viewTransform": …, "look": …, "nodes": [n.name for n in tree.nodes],
"objectIndexPass": …, "subjectPassIndex": 1}`.

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests/test_compile_blender.py -q`.

- [ ] **Step 5: Commit**
```bash
git add engine/blender/grade.py engine/blocks/grade/neutral_film/build.py engine/blocks/grade/mood_grade/build.py engine/compiler/blender_main.py engine/tests/test_compile_blender.py
git commit -m "feat(compiler): grade realiser (AgX look, lift/gamma/gain, subject separation, bloom, halation, vignette)"
```

### Task 24: Render tiers, eval passes, render log, `py -m engine render`

The preview tier is the fast one: one GPU, 540 px short side, 16 samples with OIDN denoise,
final frame rate (spec §4.7). For the harness, `preview` and `keyframes` also write three passes
per frame: a subject mask (object index), a gloss mask (material index, TIERS "gloss" mask) and a
normalised mist depth.

**Files:**
- Create: `engine/blender/render.py`, `engine/tests/test_render_blender.py`,
  `engine/tests/test_blocks_complete.py`
- Modify: `engine/compiler/blender_main.py`, `engine/__main__.py`, `engine/tests/test_cli.py`

- [ ] **Step 1: Probe the File Output node** (Blender 5.0 changed its API). From the Task 23
  probe output, read `CompositorNodeOutputFile`'s properties:
```bash
"C:/Program Files/Blender Foundation/Blender 5.0/blender.exe" --background --factory-startup --python-expr "
import bpy
t = bpy.data.node_groups.new('p', 'CompositorNodeTree'); n = t.nodes.new('CompositorNodeOutputFile')
print([p.identifier for p in n.bl_rna.properties]); print([p for p in dir(n) if 'item' in p or 'slot' in p or 'file' in p])"
```
  Write `_file_output()` in Step 4 against what it prints. **Fallback** if per-pass PNG output
  cannot be made to work: render key frames to `OPEN_EXR_MULTILAYER` (passes included) and read
  them in the harness with the `OpenEXR` pip package (BSD-3; add it to
  `harness/requirements.txt`). Record which path was taken in the commit message.

- [ ] **Step 2: Write the failing tests**

`engine/tests/test_blocks_complete.py` (no Blender):

```python
import sys

from engine.catalog import Catalog

BUILDABLE = ("world", "lighting", "motion", "effect", "grade")


def test_every_buildable_block_has_a_build_py_that_loads_without_bpy():
    cat = Catalog.load()
    for kind in BUILDABLE:
        for bid in cat.ids(kind):
            assert callable(cat.load_builder(kind, bid)), f"{kind}/{bid}"
    assert "bpy" not in sys.modules  # build.py must import bpy inside build()


def test_every_camera_has_a_path_and_a_move_primitive():
    cat = Catalog.load()
    for bid in cat.ids("camera"):
        assert callable(cat.load_camera_path(bid))
        assert cat.get("camera", bid).get("move"), bid  # T3-11
```

`engine/tests/test_render_blender.py`:

```python
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from engine.compiler.run import compile_scene
from engine.profile import SubjectProfile
from engine.tests.conftest import requires_blender

pytestmark = [pytest.mark.blender, requires_blender]
FIX = Path(__file__).parent / "fixtures"
MODELS = Path(__file__).resolve().parents[2] / "assets-in" / "models"


def _run(tmp, grade=None, limit=3):
    prof = SubjectProfile.from_dict(json.loads((FIX / "profiles" / "toycar.json").read_text(encoding="utf-8")))
    s = json.loads((FIX / "script_t3.json").read_text(encoding="utf-8"))
    if grade:
        s["grade"] = {"id": "mood_grade", "params": {"preset": grade}}
    return compile_scene(s, prof, MODELS / "toycar" / "toycar.glb", tmp, tier="keyframes", key_limit=limit)


def test_three_key_frames_render_with_passes_and_a_log(tmp_path):
    res = _run(tmp_path)
    log = json.loads((tmp_path / "render_log.json").read_text())
    assert len(log["frames"]) == 3 and log["resolution"] == [144, 256] and log["samples"] == 4
    for f in (e["frame"] for e in log["frames"]):
        rgb = np.asarray(Image.open(tmp_path / "beauty" / f"{f:04d}.png").convert("RGB"), dtype=np.float32) / 255
        assert rgb.mean() > 0.02  # B-01: not black
        mask = np.asarray(Image.open(next((tmp_path / "passes").glob(f"mask*{f:04d}*.png"))))
        assert (mask > 127).any()  # subject visible in every key frame


def test_mood_presets_change_the_picture(tmp_path):
    a = _run(tmp_path / "a", "clean", limit=1)
    b = _run(tmp_path / "b", "teal_night", limit=1)
    fa = next((tmp_path / "a" / "beauty").glob("*.png"))
    fb = next((tmp_path / "b" / "beauty").glob("*.png"))
    da = np.asarray(Image.open(fa), dtype=np.float32)
    db = np.asarray(Image.open(fb), dtype=np.float32)
    assert np.abs(da - db).mean() > 2.0  # 8-bit levels
```

Add a CLI test to `engine/tests/test_cli.py` with `compile_scene` monkeypatched: `render`
prints JSON and exits 0, and a check failure exits 3.

- [ ] **Step 3: Run, expect FAIL.**

- [ ] **Step 4: Implement** — `engine/blender/render.py`:

```python
"""Render settings per tier, eval passes and the render loop. Device selection ported from
product-render setup_cycles (tools/product-render/render_product.py:476)."""
import json
import os
import time
from pathlib import Path

import bpy

from engine.compiler.tiers import TIERS

DEVICE_ORDER = {"OPTIX": ["OPTIX", "CUDA"], "CUDA": ["CUDA", "OPTIX"], "CPU": []}


def setup_cycles(scene, tier):
    t = TIERS[tier]
    scene.render.engine = "CYCLES"
    cy = scene.cycles
    prefs = bpy.context.preferences.addons["cycles"].preferences
    chosen = "CPU"
    for dt in DEVICE_ORDER.get(os.environ.get("VALORA_DEVICE", "OPTIX").upper(), ["OPTIX", "CUDA"]):
        try:
            prefs.compute_device_type = dt
            prefs.get_devices()
        except Exception:  # noqa: BLE001 - device type absent on this machine
            continue
        if any(d.type == dt for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == dt
            chosen = dt
            break
    cy.device = "GPU" if chosen != "CPU" else "CPU"
    cy.samples = t["samples"]
    cy.use_adaptive_sampling = True
    cy.adaptive_min_samples = max(1, t["samples"] // 8)
    cy.use_denoising = t["denoise"]
    cy.denoiser = "OPENIMAGEDENOISE"
    scene.render.use_persistent_data = True
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    return chosen


def gloss_pass_indices(meshes):
    """Material pass_index 1 = TIERS 'gloss' (metallic >= 0.5 or roughness <= 0.3), measured with
    the same socket reader ingest uses."""
    from engine.ingest.blender_extract import _props
    from engine.ingest.measure import is_gloss
    for o in meshes:
        for slot in o.material_slots:
            if slot.material is not None:
                slot.material.pass_index = 1 if is_gloss(_props(slot.material)) else 0


def add_passes(scene, out_dir, far_m):
    """Subject mask, gloss mask and mist written per frame by a File Output node in the grade tree."""
    vl = scene.view_layers[0]
    vl.use_pass_object_index = vl.use_pass_material_index = vl.use_pass_mist = True
    scene.world.mist_settings.start, scene.world.mist_settings.depth = 0.0, far_m
    # _file_output(tree, Path(out_dir) / "passes", {"mask": IndexOB==1, "gloss": IndexMA==1, "mist": Mist})
    # written against the Step 1 probe; masks 8-bit BW PNG, mist 16-bit BW PNG.


def render_frames(scene, frames, out_dir, tier, device):
    out = Path(out_dir)
    (out / "beauty").mkdir(parents=True, exist_ok=True)
    log = {"blender": bpy.app.version_string, "device": device, "tier": tier, "samples": TIERS[tier]["samples"],
           "resolution": [scene.render.resolution_x, scene.render.resolution_y], "frames": []}
    t_all = time.perf_counter()
    if frames == "all":
        scene.render.filepath = str(out / "beauty" / "####")
        bpy.ops.render.render(animation=True)
    else:
        for f in frames:
            scene.frame_set(f)
            scene.render.filepath = str(out / "beauty" / f"{f:04d}.png")
            t0 = time.perf_counter()
            bpy.ops.render.render(write_still=True)
            log["frames"].append({"frame": f, "seconds": round(time.perf_counter() - t0, 3)})
    log["totalSeconds"] = round(time.perf_counter() - t_all, 3)
    (out / "render_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    return log
```

In `blender_main.main()`, after the grade: `device = setup_cycles(scene, tier)`; if
`TIERS[tier]["passes"]`, call `gloss_pass_indices(meshes)` and `add_passes(scene, out, far)`,
where `far = max(distance from any camera key to the subject centre) + 2 * radius`. If
`job["render"]`, call `render_frames(scene, job["frames"], out, tier, device)`.

`engine/__main__.py`: add a `render` subcommand:

```python
    rd = sub.add_parser("render")
    rd.add_argument("script")
    rd.add_argument("--profile", required=True)
    rd.add_argument("--model", required=True)
    rd.add_argument("--out", required=True)
    rd.add_argument("--tier", default="preview", choices=["keyframes", "preview", "final"])
    rd.add_argument("--frames", default="key", help="key | all | comma-separated frame numbers")
    rd.add_argument("--save-blend", action="store_true")
```

and in `_run`, for `render`: parse `--frames` (`"key"`, `"all"`, or `[int(x) for x in s.split(",")]`),
call `compile_scene(...)`, and print `{"ok": true, "out": …, "compile": …}`. Map
`CheckFailed` → `EXIT_CHECK_FAILED` (3).

- [ ] **Step 5: Run, expect PASS** — `py -m pytest engine/tests -q`.

- [ ] **Step 6: Measure the preview tier** (manual, about a minute; not a test):
```bash
py -m engine render engine/tests/fixtures/script_t3.json --profile engine/tests/fixtures/profiles/toycar.json --model assets-in/models/toycar/toycar.glb --out "$TEMP/valora-preview-timing" --tier preview --frames key
```
  Record the per-frame seconds from `render_log.json` in the commit body, as a (eng) budget
  check: the target is **≤ 2 s/frame at 540×960 / 16 spp on the RTX 5080**, i.e. a 10 s clip in
  about 10 minutes. If it is over budget, report that; do not lower quality in this task.

- [ ] **Step 7: Commit**
```bash
git add engine/blender/render.py engine/compiler/blender_main.py engine/__main__.py engine/tests/test_render_blender.py engine/tests/test_blocks_complete.py engine/tests/test_cli.py
git commit -m "feat(compiler): preview/keyframes/final tiers, eval passes, render log, py -m engine render"
```

---

## Chunk 5: Eval harness v0 (report-only) and calibration

Spec §9: improvement is measured, not eyeballed. v0 renders **fixed, hand-written scripts** (the
director is phase 3) as key frames, and scores each case against every TIERS.md item:

- **[S]** items come from `engine.craft_rules`, the same code the checker uses.
- **[M]** items come from `harness/metrics.py`, computed on the beauty frame plus the subject
  mask, gloss mask and mist passes (Task 24).
- **[V]** items (vision judge) are `unmeasured` in v0. The judge is phase 3+ and is never trusted
  until it agrees with the owner's grades (spec §9).
- [M] items that need dense frames or optical flow (B-03 flicker, T3-12 smoothness, T3-17
  motivated cut) are `unmeasured` in v0, because tests and eval render key frames only. They
  arrive with the full-preview QC work (spec §4.8, phase 6).

**Report-only.** Every threshold in `harness/thresholds.json` starts as TIERS.md's initial value
with `"calibrated": false`. Nothing blocks a render, and no score is quoted as a quality claim,
until Task 29's calibration moves the threshold and the owner signs it off. This follows the
calibrate-before-you-model rule.

### Task 25: Harness skeleton — item registry and thresholds

**Files:**
- Create: `harness/__init__.py` (empty), `harness/requirements.txt`, `harness/.gitignore`,
  `harness/items.py`, `harness/thresholds.json`, `harness/tests/__init__.py` (empty),
  `harness/tests/conftest.py`, `harness/tests/test_items.py`

- [ ] **Step 1: Files that are not code**

`harness/requirements.txt`:
```
numpy>=2.0
Pillow>=10.0
scikit-image>=0.24
scipy>=1.11
```
`harness/.gitignore`:
```
out/
__pycache__/
```
`harness/tests/conftest.py`: the same `blender` marker registration and `requires_blender` as
`engine/tests/conftest.py` (import `requires_blender` from there; do not duplicate the path logic).

- [ ] **Step 2: Write the failing test** — `harness/tests/test_items.py`

```python
import json
from pathlib import Path

from harness.items import ITEMS, by_id

TH = json.loads((Path(__file__).resolve().parents[1] / "thresholds.json").read_text())


def test_registry_covers_every_tiers_item_once():
    ids = [i["id"] for i in ITEMS]
    assert len(ids) == len(set(ids)) == 47  # TIERS.md: 5 B + 3 T1 + 9 T2 + 23 T3 + 6 T4, plus V-C02
    assert {i["tier"] for i in ITEMS} == {"B", "T1", "T2", "T3", "T4"}
    assert by_id("T3-06")["method"] == "M" and by_id("T2-09")["method"] == "V"


def test_thresholds_are_known_items_and_start_uncalibrated():
    for iid, t in TH.items():
        assert by_id(iid)["method"] in ("M", "S+M"), iid
        assert t["calibrated"] is False and t["source"].startswith("TIERS"), iid
        assert t["op"] in (">=", "<=") and t["primary"] in t, iid
```

- [ ] **Step 3: Implement** — `harness/items.py`: one dict per TIERS.md §2 item,
  `{"id", "tier", "method", "text"}`, where `tier` is `B | T1 | T2 | T3 | T4` and `method` is
  `S | M | V | S+M` exactly as tagged in TIERS.md. Special cases: T3-01 is `M` but uses the
  script's cut times for our own renders (TIERS allows this). T2-08 is `M` with an S fallback.
  T4-01 is `V` with an S half. `V-C02` is `S` at tier `T3`. Transcribe `text` from TIERS.md,
  shortened to one line. Add `by_id(iid)`.

`harness/thresholds.json`: the initial values from TIERS.md, every entry
`"calibrated": false`, with a `primary` key naming the value compared, and `op`:

```json
{
  "B-01": {"primary": "minMeanLum", "op": ">=", "minMeanLum": 0.02, "calibrated": false, "source": "TIERS B-01"},
  "B-02": {"primary": "maxBrightShare", "op": "<=", "maxBrightShare": 0.02, "bright": 0.99, "maxDarkShare": 0.05, "dark": 0.01, "calibrated": false, "source": "TIERS B-02"},
  "B-05": {"primary": "minCoverage", "op": ">=", "minCoverage": 0.25, "calibrated": false, "source": "TIERS B-05"},
  "T1-X2": {"primary": "minBgStd", "op": ">=", "minBgStd": 0.02, "shadowRatio": 0.9, "calibrated": false, "source": "TIERS T1-X2 (shadowRatio eng)"},
  "T2-02": {"primary": "minGlossStd", "op": ">=", "minGlossStd": 0.08, "calibrated": false, "source": "TIERS T2-02"},
  "T2-06": {"primary": "minRatio", "op": ">=", "minRatio": 1.5, "maxFstop": 5.6, "calibrated": false, "source": "TIERS T2-06"},
  "T2-07": {"primary": "maxFarNearRatio", "op": "<=", "maxFarNearRatio": 0.8, "calibrated": false, "source": "TIERS T2-07"},
  "T3-03": {"primary": "minDetailCoverage", "op": ">=", "minDetailCoverage": 0.6, "calibrated": false, "source": "TIERS T3-03"},
  "T3-06": {"primary": "minElongation", "op": ">=", "minElongation": 2.0, "minElongationVehicle": 3.0, "highlight": 0.85, "calibrated": false, "source": "TIERS T3-06"},
  "T3-07": {"primary": "minDarkShare", "op": ">=", "minDarkShare": 0.25, "dark": 0.15, "minBrightShare": 0.15, "bright": 0.6, "calibrated": false, "source": "TIERS T3-07"},
  "T3-08": {"primary": "maxBlownShare", "op": "<=", "maxBlownShare": 0.005, "blown": 0.99, "calibrated": false, "source": "TIERS T3-08"},
  "T3-09": {"primary": "minBoundaryShare", "op": ">=", "minBoundaryShare": 0.6, "minContrast": 0.1, "band": 3, "calibrated": false, "source": "TIERS T3-09"},
  "T3-15": {"primary": "minArea", "op": ">=", "minArea": 0.10, "hookS": 0.5, "calibrated": false, "source": "TIERS T3-15 (area reading eng)"},
  "T3-18": {"primary": "insideShare", "op": ">=", "insideShare": 1.0, "box1080x1920": [60, 220, 960, 1500], "calibrated": false, "source": "TIERS T3-18 (TikTok and Reels boxes intersected)"},
  "T3-19": {"primary": "minRatio", "op": ">=", "minRatio": 1.10, "monoChroma": 2.0, "calibrated": false, "source": "TIERS T3-19"},
  "T3-20": {"primary": "maxDeltaE", "op": "<=", "maxDeltaE": 10.0, "calibrated": false, "source": "TIERS T3-20"},
  "T3-22": {"primary": "maxRatio", "op": "<=", "maxRatio": 0.5, "minLens": 85, "calibrated": false, "source": "TIERS T3-22"}
}
```

- [ ] **Step 4: Run, expect PASS** — `py -m pytest harness/tests -q`.

- [ ] **Step 5: Commit**
```bash
git add harness
git commit -m "feat(harness): TIERS item registry and uncalibrated initial thresholds"
```

### Task 26: Frame metrics for the [M] items

**Files:** Create `harness/metrics.py`, `harness/tests/test_metrics.py`

- [ ] **Step 1: Write the failing tests** — synthetic frames, one known-pass and one
  known-fail per item. Every item gets both: a metric whose failing case was never shown to fail
  cannot be trusted.

```python
import json
from pathlib import Path

import numpy as np
import pytest

from harness import metrics as m

TH = json.loads((Path(__file__).resolve().parents[1] / "thresholds.json").read_text())
H, W = 256, 144


def frame(rgb=0.3, mask=None, gloss=None, mist=None):
    img = np.full((H, W, 3), rgb, dtype=np.float32) if np.isscalar(rgb) else rgb
    mk = np.zeros((H, W), bool) if mask is None else mask
    return m.Frame(frame=1, t=0.0, shot=0, lens=50.0, fstop=4.0, rgb=img, mask=mk,
                   gloss=mk.copy() if gloss is None else gloss, mist=mist)


def centre_mask(h=0.5, w=0.5):
    mk = np.zeros((H, W), bool)
    mk[int(H * (0.5 - h / 2)):int(H * (0.5 + h / 2)), int(W * (0.5 - w / 2)):int(W * (0.5 + w / 2))] = True
    return mk


def test_box_mean_matches_naive():
    rng = np.random.default_rng(0)
    a = rng.random((20, 30))
    naive = np.array([[np.pad(a, 2, mode="edge")[y:y + 5, x:x + 5].mean() for x in range(30)] for y in range(20)])
    assert np.allclose(m.box_mean(a, 2), naive)


def test_b01():
    assert m.b01(frame(0.0, centre_mask()), TH["B-01"])[1] is False
    assert m.b01(frame(0.3, centre_mask()), TH["B-01"])[1] is True


def test_b02_bright_clipping():
    img = np.full((H, W, 3), 0.4, np.float32)
    img[:20] = 1.0  # ~8% blown
    assert m.b02(frame(img, centre_mask()), TH["B-02"], black_world=False)[1] is False
    assert m.b02(frame(0.4, centre_mask()), TH["B-02"], black_world=False)[1] is True


def test_b05_dominant_axis_coverage():
    assert m.b05(frame(0.3, centre_mask(0.1, 0.1)), TH["B-05"])[1] is False
    assert m.b05(frame(0.3, centre_mask(0.2, 0.9)), TH["B-05"])[1] is True  # wide subject fills the width


def test_t306_strips_pass_blobs_fail():
    mk = centre_mask(0.6, 0.8)
    strip = np.full((H, W, 3), 0.3, np.float32)
    strip[120:124, 30:110] = 0.95
    blob = np.full((H, W, 3), 0.3, np.float32)
    blob[115:130, 60:75] = 0.95
    assert m.t306(frame(strip, mk), TH["T3-06"], vehicle=False)[1] is True
    assert m.t306(frame(blob, mk), TH["T3-06"], vehicle=False)[1] is False


def test_t307_planned_darks_and_highlights():
    mk = centre_mask(0.6, 0.8)
    img = np.full((H, W, 3), 0.4, np.float32)
    assert m.t307(frame(img, mk), TH["T3-07"])[1] is False
    img[:H // 2] = 0.05
    img[H // 2: H // 2 + 40] = 0.8
    assert m.t307(frame(img, mk), TH["T3-07"])[1] is True


def test_t308_blown_speculars():
    mk = centre_mask(0.6, 0.8)
    img = np.full((H, W, 3), 0.5, np.float32)
    img[100:110, 40:100] = 1.0
    assert m.t308(frame(img, mk), TH["T3-08"])[1] is False
    assert m.t308(frame(np.full((H, W, 3), 0.5, np.float32), mk), TH["T3-08"])[1] is True


def test_t309_silhouette_separation():
    mk = centre_mask()
    img = np.where(mk[..., None], 0.8, 0.1).repeat(3, -1).astype(np.float32)
    assert m.t309(frame(img, mk), TH["T3-09"])[1] is True
    assert m.t309(frame(np.full((H, W, 3), 0.5, np.float32), mk), TH["T3-09"])[1] is False


def test_t319_subject_chroma_over_background():
    mk = centre_mask()
    red_on_grey = np.where(mk[..., None], np.array([0.8, 0.1, 0.1]), 0.5).astype(np.float32)
    grey_on_red = np.where(mk[..., None], 0.5, np.array([0.8, 0.1, 0.1])).astype(np.float32)
    assert m.t319(frame(red_on_grey, mk), TH["T3-19"])[1] is True
    assert m.t319(frame(grey_on_red, mk), TH["T3-19"])[1] is False


def test_t207_far_background_is_softer():
    mk = centre_mask(0.3, 0.3)
    rng = np.random.default_rng(1)
    mist = np.tile(np.linspace(0, 1, H)[:, None], (1, W)).astype(np.float32)
    noisy = (0.4 + 0.2 * rng.random((H, W, 1))).repeat(3, -1).astype(np.float32)
    soft = noisy.copy()
    soft[mist > 0.6] = 0.4
    assert m.t207(frame(noisy, mk, mist=mist), TH["T2-07"])[1] is False
    assert m.t207(frame(soft, mk, mist=mist), TH["T2-07"])[1] is True


def test_t318_safe_zone():
    top_left = np.zeros((H, W), bool)
    top_left[:20, :20] = True
    assert m.t318(frame(0.3, top_left), TH["T3-18"], "9:16")[1] is False
    assert m.t318(frame(0.3, centre_mask()), TH["T3-18"], "9:16")[1] is True
    assert m.t318(frame(0.3, centre_mask()), TH["T3-18"], "16:9")[1] is None  # n/a
```

- [ ] **Step 2: Run, expect FAIL** — ImportError.

- [ ] **Step 3: Implement** — `harness/metrics.py`. Each item function returns
  `(value, ok)`, where `ok` is `True` / `False`, or `None` for not applicable. Core helpers:

```python
"""TIERS [M] items on rendered key frames. Display-referred sRGB in [0, 1] (the thresholds in
TIERS.md are display values). Every threshold comes from harness/thresholds.json; report-only."""
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion  # skimage's versions go away in 0.28
from skimage.measure import label, regionprops
from skimage.morphology import disk  # pass as structure=disk(r)


@dataclass
class Frame:
    frame: int
    t: float
    shot: int
    lens: float
    fstop: float
    rgb: np.ndarray            # H x W x 3 float32
    mask: np.ndarray           # subject (object index 1)
    gloss: np.ndarray          # TIERS gloss mask: subject pixels on gloss materials
    mist: np.ndarray | None    # 0 near .. 1 far


def lum(rgb):
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def srgb_to_lab(rgb):
    c = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = c @ np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]).T
    xyz = xyz / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def box_mean(img, r):
    p = np.pad(img, r, mode="edge")
    c = np.pad(np.cumsum(np.cumsum(p, 0), 1), ((1, 0), (1, 0)))
    k = 2 * r + 1
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def laplacian(L):
    out = np.zeros_like(L)
    out[1:-1, 1:-1] = 4 * L[1:-1, 1:-1] - L[:-2, 1:-1] - L[2:, 1:-1] - L[1:-1, :-2] - L[1:-1, 2:]
    return out


def sharpness(L, region):
    v = laplacian(L)[region]
    return float(v.var()) if v.size >= 50 else None
```

Then one function per item, following the TIERS.md definitions and the threshold keys in
`thresholds.json`. **Wrap every `ok` in `bool(...)`**: numpy comparisons return `np.bool_`, and
the tests check `is True` / `is False`. Shared conventions: "near" = mist ≤ p30 and "far" =
mist ≥ p70 (inclusive); a gloss share is gloss pixels / all frame pixels; wherever a band or
region mean would divide by zero, that pixel is excluded; `evaluate` stores
`[(frame, value, ok), …]` in `ItemResult.value` and returns `na` when no frame applies. Add one
known-pass/known-fail test each for `t1x2`, `t202`, `t206`, `t303m`, `t315`, `t320` and `t322`
(the block above shows the pattern), plus one `evaluate` test on two synthetic frames.

- `b01(fd, th)`: mean luminance > `minMeanLum` **and** the mask is non-empty.
- `b02(fd, th, black_world)`: share of luminance ≥ `bright` < `maxBrightShare`, and share
  ≤ `dark` < `maxDarkShare`. When `black_world` is true, count dark pixels only inside the mask.
- `b05(fd, th)`: mask bounding box, max(width/W, height/H) ≥ `minCoverage`. Not applicable
  (`None`) on detail shots (the caller passes only full-framing frames).
- `t1x2(fd, th)`: background luminance std, plus a contact-shadow test (mean luminance of a strip
  5% of H tall directly under the mask's bottom edge, within the mask's x-extent, < `shadowRatio`
  × background median). Returns `(std, not (std < minBgStd and not shadow))`: pass means "not the
  T1 signature".
- `t202(fd, th)`: std of luminance on gloss pixels ≥ `minGlossStd`; `None` if gloss pixels
  < 0.5% of the frame.
- `t206(fd, th)`: `None` if `fd.fstop > maxFstop`; otherwise sharpness(subject) /
  sharpness(background) ≥ `minRatio`.
- `t207(fd, th)`: background pixels split at mist percentiles 30 / 70. Local contrast =
  |L − box_mean(L, 4)|. Ratio = mean(far) / mean(near) ≤ `maxFarNearRatio`. `None` without mist
  or with an empty group.
- `t303m(fd, th)`: detail frames only: mask touches the frame border or its area fraction
  ≥ `minDetailCoverage`.
- `t306(fd, th, vehicle)`: pixels with luminance ≥ `highlight` inside the gloss mask; connected
  components (8-connectivity) of area ≥ max(4, 2e-4 × pixels); mean of
  `axis_major_length / max(axis_minor_length, 1)`. Pass if ≥ `minElongationVehicle` for
  vehicles, else ≥ `minElongation`. No components gives value 0, a fail (no highlight at all).
  `None` if gloss < 0.5% of the frame.
- `t307(fd, th)`: within gloss: share < `dark` ≥ `minDarkShare` and share > `bright`
  ≥ `minBrightShare`.
- `t308(fd, th)`: within gloss: share ≥ `blown` ≤ `maxBlownShare`.
- `t309(fd, th)`: inner band = mask minus erosion(disk(band)); outer band = dilation(disk(band))
  minus mask; edge = mask minus erosion(disk(1)). At each edge pixel, compare the band means
  (`box_mean` of L × band divided by `box_mean` of the band, radius band+1). Share of edge pixels
  with |inner − outer| ≥ `minContrast` must be ≥ `minBoundaryShare`.
- `t315(fd, th)`: only frames with t ≤ `hookS`; mask area fraction ≥ `minArea`.
- `t318(fd, th, aspect)`: `None` unless aspect is 9:16. Scale the 1080×1920 box
  `[x0, y0, x1, y1]` to the frame size; pass when the mask centroid is inside.
- `t319(fd, th)`: Lab chroma mean(subject) / max(mean(background), 1e-6) ≥ `minRatio`. Only
  when **both** subject and background chroma are < `monoChroma` (a monochrome look) use
  |L*subject − L*background| / 100 ≥ 0.10 instead. (A red subject on a grey background is
  separated by colour, not a monochrome look.)
- `t320(frames, th)`: clip-level. Per shot, mean background Lab; every shot within ΔE76
  `maxDeltaE` of the clip mean.
- `t322(fd, th)`: `None` unless `fd.lens ≥ minLens`; sharpness(background) / sharpness(subject)
  ≤ `maxRatio`.

`evaluate(frames, script, profile, catalog, th)` applies each per-frame function to the frames
where it applies (full vs detail framing from the shot's camera manifest), and aggregates:
**an item passes only if every applicable frame passes** (strict for v0; calibration may relax it
to a share). It returns `{id: engine.craft_rules.ItemResult}` with the per-frame values in
`value`. Items it cannot measure in v0 (B-03, T3-12, T3-17, T4-04) come back as `unmeasured`
with the reason in `detail`.

- [ ] **Step 4: Run, expect PASS** — `py -m pytest harness/tests -q`.

- [ ] **Step 5: Commit**
```bash
git add harness/metrics.py harness/tests/test_metrics.py
git commit -m "feat(harness): frame metrics for TIERS [M] items with known-pass and known-fail tests"
```

### Task 27: Scoring and reports

**Files:** Create `harness/score.py`, `harness/frames.py`, `harness/tests/test_score.py`

- [ ] **Step 1: Write the failing tests**

```python
from engine.craft_rules import ItemResult
from harness.items import ITEMS
from harness.score import tier_reached


def _all(status="pass", **over):
    return {i["id"]: ItemResult(i["id"], over.get(i["id"], status)) for i in ITEMS}


def test_everything_passing_but_no_sim_is_t3():
    r = _all(**{"T4-03": "fail"})
    assert tier_reached(r) == {"tier": "T3", "provisional": False, "blocking": ["T4-03"]}


def test_a_baseline_or_t1_signature_failure_caps_at_t1():
    assert tier_reached(_all(**{"B-02": "fail"}))["tier"] == "T1"
    assert tier_reached(_all(**{"T1-X3": "fail"}))["tier"] == "T1"


def test_tiers_are_cumulative():
    assert tier_reached(_all(**{"T2-07": "fail"}))["tier"] == "T1"
    assert tier_reached(_all(**{"T3-06": "fail"}))["tier"] == "T2"


def test_unmeasured_items_make_the_result_provisional_not_failing():
    r = tier_reached(_all(**{"T3-10": "unmeasured", "T4-03": "fail"}))
    assert r["tier"] == "T3" and r["provisional"] is True
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `harness/score.py`:

```python
"""Combine [S] (engine.craft_rules) and [M] (harness.metrics) results into TIERS items and the
tier reached (TIERS §3: cumulative; n/a counts as pass; unmeasured makes the result provisional)."""
from harness.items import ITEMS

ORDER = ("T2", "T3", "T4")


def tier_reached(results):
    def status(tier):
        return [(i["id"], results[i["id"]].status) for i in ITEMS if i["tier"] == tier]

    base = [iid for t in ("B", "T1") for iid, st in status(t) if st == "fail"]
    if base:
        return {"tier": "T1", "provisional": False, "blocking": base}
    reached, provisional = "T1", False
    for tier in ORDER:
        fails = [iid for iid, st in status(tier) if st == "fail"]
        if fails:
            return {"tier": reached, "provisional": provisional, "blocking": fails}
        provisional = provisional or any(st == "unmeasured" for _, st in status(tier))
        reached = tier
    return {"tier": reached, "provisional": provisional, "blocking": []}


def merge(s_items, m_items):
    """One ItemResult per registry item. S+M: fail if either half fails; unmeasured if the M half
    is. V: unmeasured in v0. B-04 passes by construction (the checker passed the script)."""
```

Write `merge` in full following its docstring: T2-08 uses the S fallback, and T3-01 uses the S
result for our own renders. For S+M items: fail if either half fails; `unmeasured` if a half is
missing or unmeasured; `na` only when both halves are `na`. Add tests for these three cases and
for `score_case` on a tiny synthetic case directory (two frames written with Pillow).

`harness/frames.py`: `load_frames(case_dir, script, catalog)` reads `render_log.json`, then each
beauty PNG and its `passes/mask*`, `passes/gloss*`, `passes/mist*` files. It fills `Frame.shot`,
`lens` and `fstop` from `engine.compiler.timeline.shot_index` and the shot's camera params, and
returns the frames in order.

`score_case(case_dir, script, profile, catalog, th)` returns
`{"items": {id: {status, value, detail}}, **tier_reached(...)}`.
`write_report(case_dir, score)` writes `report.json` and a `report.md` table (item, tier, status,
value, threshold, calibrated) with failing items first.

- [ ] **Step 4: Run, expect PASS** — `py -m pytest harness/tests -q`.

- [ ] **Step 5: Commit**
```bash
git add harness/score.py harness/frames.py harness/tests/test_score.py
git commit -m "feat(harness): merge S and M items, cumulative tier reached, per-case reports"
```

### Task 28: Suite v0 and the runner

Three fixed scripts per model, chosen so calibration has both ends:

| Script | Built to be | Why |
|---|---|---|
| `t1_control.json` | Known-bad T1 | One 10 s `arc_orbit` shot, flat `softbox_three_point` (`fillRatio` 1.0, `rimStrength` 0), grey cyc, no effects, `neutral_film` with `agxLook: none`, bloom 0. Hits T1-X3 and fails T2-07/T2-08 and every T3 edit rule. The negative control. |
| `t2_studio.json` | T2-ish | Two shots (`low_hero_push`, `arc_orbit`), black cyc, softbox, `haze_volume` 0.2, `mood_grade` `premium_dark`. |
| `t3_attempt.json` | Best phase-2 attempt | Same as `engine/tests/fixtures/script_t3.json`: `reflection_rig`, `sequence`, two `macro_detail`s, `haze_volume`, `mood_grade`. |

Negative-control rule (memory `feedback_negative_control_can_contain_the_defect`): before any
calibration uses `t1_control` as "bad", check that none of its renders was graded T3 by the owner.
If one was, the control is wrong; fix it before using it.

**Files:**
- Create: `harness/suites/v0/suite.json`, `harness/suites/v0/{t1_control,t2_studio,t3_attempt}.json`,
  `harness/run.py`, `harness/__main__.py`, `harness/tests/test_suite_scripts.py`,
  `harness/tests/test_run_blender.py`

- [ ] **Step 1: Suite** — `harness/suites/v0/suite.json`:
```json
{"models": ["camera_01", "flighthelmet", "mid_century_lounge_chair", "pocket_watch", "toycar", "vintage_microscope"],
 "scripts": ["t1_control", "t2_studio", "t3_attempt"],
 "profiles": "engine/tests/fixtures/profiles", "glb": "assets-in/models/{m}/{m}.glb"}
```
Write the three scripts as specified above. Each must pass `check()` for all six profiles.
`harness/tests/test_suite_scripts.py` (no Blender) asserts this for every suite model × script,
and that `t1_control` really fails T1-X3 in `craft_rules.score_script`. It catches fixtures that
only work on one subject.

- [ ] **Step 2: Write the failing Blender smoke test** — `harness/tests/test_run_blender.py`:

```python
import json

import pytest

from engine.tests.conftest import requires_blender
from harness.run import run_suite

pytestmark = [pytest.mark.blender, requires_blender]


def test_one_case_end_to_end(tmp_path):
    summary = run_suite("v0", models=["toycar"], scripts=["t3_attempt"], tier="keyframes", key_limit=3,
                        out_root=tmp_path, run_id="smoke")
    case = tmp_path / "smoke" / "toycar__t3_attempt"
    rep = json.loads((case / "report.json").read_text())
    assert rep["tier"] in ("T1", "T2", "T3", "T4") and "items" in rep
    assert (tmp_path / "smoke" / "summary.md").read_text().count("toycar__t3_attempt") >= 1
    assert summary["cases"][0]["case"] == "toycar__t3_attempt"
```

- [ ] **Step 3: Implement** — `harness/run.py`: `run_suite(suite, models=None, scripts=None,
  tier="preview", key_limit=None, out_root="harness/out", run_id=None, encode=False)`. For each
  (model, script): load the profile, then `compile_scene(..., tier=tier, frames="key",
  key_limit=key_limit)` into `<out_root>/<run_id>/<model>__<script>/`. Save `check.json`
  (issues), score with `score_case`, write the report. A failing case is recorded in the summary
  with its error, never skipped silently. Finish with `summary.json` and `summary.md`: a table of
  case × tier reached × provisional × blocking items, plus the per-item pass rate across cases.
  With `--encode` and `--frames all`, also encode `preview.mp4` via
  `ffmpeg -framerate <fps> -i beauty/%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18`
  (colour-tagged encode is phase 6).

`harness/__main__.py`: `py -m harness run --suite v0 [--models a,b] [--scripts x,y] [--tier keyframes|preview] [--key-limit N] [--frames key|all] [--encode] [--run-id ID]`.

- [ ] **Step 4: Run, expect PASS** — `py -m pytest harness/tests -q`.

- [ ] **Step 5: Commit**
```bash
git add harness/suites harness/run.py harness/__main__.py harness/tests/test_run_blender.py harness/tests/test_suite_scripts.py
git commit -m "feat(harness): v0 suite (T1 control, T2 studio, T3 attempt) and runner with summary"
```

### Task 29: Calibration tooling (never writes thresholds by itself)

Three calibrations, all **report-only**. Each writes a proposal to
`harness/out/calibration-<date>.json`. A human (Claude plus the owner's sign-off) edits
`thresholds.json` and flips `calibrated` to true, one item at a time, citing the proposal file.

1. **Cut detector** (T3-01 [M], used when scoring clips that have no script: reference clips and
   later user uploads). Ground truth: `cutTimesS` in `research/corpus/refs/*.json` against
   `assets-in/refs/clips/<id>.mp4` (both local and untracked; skip if absent). Sweep the ffmpeg
   scene threshold over 0.08–0.4 plus TIERS's "union of 0.12 and 0.3". Report precision, recall
   and F1 with a ±2-frame match tolerance. Caveat for the report: those cut times were
   vision-extracted in the pilot, so the ground truth itself has error. Say so next to the
   number.
2. **Mask-free frame statistics on the owner's references** (`assets-in/refs/frames/*.jpg`,
   known-good but compressed): B-01, B-02 and whole-frame luminance std, to see where real ads
   sit. Mask-based items cannot be computed on refs (there are no masks). The report states this.
3. **Separation on our own renders**: owner grades vs metric values. Grades live in
   `harness/grades/owner-grades.jsonl`, one line per graded case:
   `{"case": "<runId>/<model>__<script>", "tier": "T1|T2|T3|T4", "by": "owner", "date": "YYYY-MM-DD", "notes": "…"}`.
   Only `"by": "owner"` lines count. Never calibrate on the harness's own verdicts or a judge's.
   Per metric: good = owner tier ≥ T3, bad = owner tier T1 (T2 reported separately). If
   separable, propose the midpoint; else report the overlap with counts. Print the population
   size next to every number (n good, n bad).

**Files:** Create `harness/calibrate.py`, `harness/contact_sheet.py`,
`harness/grades/owner-grades.jsonl` (empty), `harness/tests/test_calibrate.py`

- [ ] **Step 1: Write the failing tests**

```python
from harness.calibrate import match_cuts, separation
from harness.contact_sheet import sheet


def test_match_cuts_counts_hits_misses_and_false_alarms():
    tp, fp, fn = match_cuts(pred=[1.0, 2.52, 7.0], truth=[1.02, 2.5, 5.0], tol_s=2 / 30)
    assert (tp, fp, fn) == (2, 1, 1)


def test_separation_proposes_a_midpoint_only_when_clean():
    assert separation(good=[0.5, 0.6], bad=[0.1, 0.2], op=">=") == {
        "status": "separable", "proposed": 0.35, "nGood": 2, "nBad": 2}
    r = separation(good=[0.3, 0.6], bad=[0.1, 0.4], op=">=")
    assert r["status"] == "overlap" and r["proposed"] is None
    assert separation(good=[], bad=[0.1], op=">=")["status"] == "insufficient"


def test_contact_sheet_lays_frames_in_a_row(tmp_path):
    from PIL import Image
    paths = []
    for i in range(3):
        p = tmp_path / f"{i}.png"
        Image.new("RGB", (144, 256), (i * 60, 0, 0)).save(p)
        paths.append(p)
    out = sheet(paths, "case-x", tmp_path / "s.png", thumb_h=128)
    assert Image.open(out).size == (3 * 72, 128 + 24)
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** `match_cuts` (greedy one-to-one within tolerance), `separation`
  (per the description above; `op` `<=` mirrors it; `proposed` rounded to 6 decimals), `detect_cuts(clip, threshold)` (runs
  `ffmpeg -hide_banner -i <clip> -vf "select='gt(scene,T)',showinfo" -an -f null -` and parses
  `pts_time:` from stderr), and the three subcommands `py -m harness.calibrate cuts|refs|separate
  --run <runId>`. `sheet(paths, label, out, thumb_h)` pastes thumbnails left to right with a 24 px
  label strip, so the owner can grade a case at a glance.

- [ ] **Step 4: Run, expect PASS** — `py -m pytest harness/tests -q`. Then run
  `py -m harness.calibrate cuts` once, if the clips are present. It is CPU-light (ffmpeg decode
  of 10 short clips). Commit its proposal numbers in the commit body.

- [ ] **Step 5: Commit**
```bash
git add harness/calibrate.py harness/contact_sheet.py harness/grades harness/tests/test_calibrate.py
git commit -m "feat(harness): calibration tooling (cut detector, ref stats, owner-grade separation), contact sheets"
```

### Task 30: Eval subjects — a character, a shoe, a real-scale vehicle (licence-checked)

Spec §9 and D2: the eval set must span products, furniture, vehicles and characters. The six
current models have no character, no apparel and no real-scale vehicle. The 7 cm toy car cannot
calibrate any metre-scale (eng) number (overhead height, strip distance, T3-21 DOF, V-C02 lens
rule, wheels).

**Files:** `assets-in/models/<name>/<name>.glb` (local, untracked), `assets-in/models/LICENSES.md`
(append), `engine/tests/fixtures/profiles/<name>.json`, `engine/tests/test_real_profiles.py`
(`MODELS` list), `harness/suites/v0/suite.json`

- [ ] **Step 1: Source, CC0 first.** Poly Haven models (CC0, PRIOR-ART #1) via the Blender MCP
  (`search_polyhaven_assets` with `asset_type="models"`). Then Sketchfab with a
  downloadable + CC0 or CC-BY filter (`search_sketchfab_models`). Record URL, author, licence and
  date in `assets-in/models/LICENSES.md`. CC-BY is accepted (owner 2026-09-24); record the
  attribution. A ModVision fleet GLB may be used **locally** as the real-scale vehicle (owner
  2026-09-24): never committed, shipped or shown. If no licence-clean real-scale vehicle exists, stop and
  report it; do not substitute.
- [ ] **Step 2: Ingest each** — `py -m engine ingest assets-in/models/<n>/<n>.glb --out engine/tests/fixtures/profiles/<n>.json`,
  check the true-scale result is plausible (vehicle 3.5–5.5 m, shoe 0.25–0.35 m, character
  0.2–2 m), add the names to `MODELS` and the suite.
- [ ] **Step 3: Run** `py -m pytest engine/tests harness/tests -q -m "not blender"` → pass
  (every suite script must check on the new profiles too).
- [ ] **Step 4: Commit**
```bash
git add assets-in/models/LICENSES.md engine/tests/fixtures/profiles engine/tests/test_real_profiles.py harness/suites/v0/suite.json
git commit -m "test(eval): character, shoe and real-scale vehicle eval subjects (licences recorded)"
```
(`LICENSES.md` may be untracked like the rest of `assets-in/`. If so, keep it local and put the
licence table in the commit body instead.)

### Task 31: Baseline run and the owner's first grading pass

**Deferred until ALL director phases are built** (owner 2026-09-24: "all phases complete before
we start doing tests"). Automated unit and key-frame tests inside each task still run as normal;
this task is the owner-facing render + grading pass and runs once, at the end of the last phase.
Phase 3+ plans must not depend on its numbers; use the report-only starting thresholds.

Not code: this produces the calibration numbers. **Ask the owner before Step 1.** It is
the heaviest local job in this plan, and the owner games on this machine.

- [ ] **Step 1: Key-frame baseline** — `py -m harness run --suite v0 --tier preview --run-id baseline-<date>`.
  That is 9 models × 3 scripts × about 7 key frames ≈ 190 preview frames (about 6 minutes at the
  2 s/frame budget).
- [ ] **Step 2: Full-motion previews for grading** — only `t3_attempt` and `t1_control`, all
  frames, encoded: `--scripts t3_attempt,t1_control --frames all --encode`. That is 18 clips ×
  300 frames. Measure the first clip and give the owner the time estimate before running the
  rest.
- [ ] **Step 3: Contact sheets + owner grading.** Generate sheets, give the owner the list of
  preview MP4s, and record the grades in `harness/grades/owner-grades.jsonl` with `"by": "owner"`.
  The owner grades; Claude never fills this file with its own opinion.
- [ ] **Step 4: Calibrate** — `py -m harness.calibrate separate --run baseline-<date>`. Then, per
  item, update `thresholds.json` only where the separation is clean, set `calibrated: true`, and
  cite the proposal file and n. Items that overlap stay uncalibrated, with a note.
- [ ] **Step 5: Report** — `summary.md` plus the calibration proposal, into the next handoff:
  tier reached per case, the most common blocking items (they order phase 3's taste guide and the
  catalog-growth queue), s/frame per tier, and which (eng) numbers moved.

---

## Calibration register — every (eng) number this plan introduces

Each number below is a starting value translated from a qualitative source (the craft files'
**(eng)** tag) or chosen here. None may be quoted as a quality fact until Task 29/31 calibrates
it on golden renders with owner grades. Numbers marked (src) came straight from a source and are
listed only where a scene-unit mapping was still needed.

| Number(s) | Where | Calibrated through | Needs |
|---|---|---|---|
| Overhead scale 1.3 L / width 1.1 W / height 0.6 r; strip length 1.0 L, aspect 8, distance 0.8 r; accent 0.4 × 0.5 r; neg-card size factor (1 + 4·darkShare) | `reflection_rig` defaults, `reflect.py` | T3-06, T3-07, T3-09 (+ T3-10 when the judge exists) | Glossy product + real-scale vehicle goldens (Task 30) |
| `K_RADIANCE` 200 W/m², `WORLD_FILL` 0.5 | `engine/blender/lights.py` | T3-08 (hood/roof peak 0.85–0.95 display, V-L02), B-02 | Same |
| Softbox distances 3–3.5 r, sizes, fill azimuth −40°, rim 150°/38° | `engine/softbox.py` | T1-X3, T2 items | Any golden |
| Cyc albedos 0.8/0.18/0.02, gloss mix 0.3×, roughness 0.25 | `studio_cyc/build.py` | T1-X2, B-02 (black world) | Any golden |
| `HAZE_K` 0.4, clear pocket 1–2 r | `haze_volume/build.py` | T2-07 [M] far/near ≤ 0.8, T3-19 | Studio + vehicle goldens |
| Preset lift/gain/saturation/bloom/halation/vignette; contrast ×50 mapping; halation threshold 1.2, size 0.45 | `engine/grade_plan.py` | T2-08, T3-08, T3-19, T3-20 | Owner grades per preset |
| macro distance 0.45 r, slide 0.4, `LOOK_DRIFT` 0.15, `DETAIL_CENTER` 0.6, `DETAIL_MIN_COVERAGE` 0.6 | `macro_detail`, `checker.py` | T3-03 [M], T3-22 | Owner grades of detail shots |
| `hookMaxS` 2.5, `medianLenS` 1.0–3.0, `shotLenS` 0.8–3.5, pace ranges | `sequence` manifest | Owner grades on pacing; corpus cut statistics (`research/corpus`) | Full-motion previews (Task 31 Step 2) |
| `SCALE_EDGES`, `VEHICLE_SIZE_M` 2.5, CoC 0.03 mm | `craft_rules.py` | T3-03, T3-21 | Real-scale vehicle |
| Detail cell 0.08 L, separation 0.15 L, curvature percentiles 90/95, kind base scores | `measure.detail_points` | Owner review of which details get picked | All 9 subjects |
| Wheel contact 2% H, window sizes, IQR 0.15 r | `measure.wheels` | First vehicle block (deferred) | Real-scale vehicle |
| Preview 16 spp / 540 px; final 192 spp / 1080 px | `tiers.py` | s/frame budget (Task 24 Step 6); owner Q2 price per clip | — |
| Every threshold in `harness/thresholds.json` | TIERS.md initial values | Task 29 separation | Task 31 owner grades |

---

## Deferred (and why)

- **Catalog gaps not built** (see the table at the top of Chunk 3): `rolling_track` + `drive`
  (rank 5), new worlds (7), `ground_fog`/`rain`/`dust_motes`, transitions (8, names reserved),
  `handheld_operator` (9), `light_sweep`/`edge_reveal` (10, 14: need animated lighting params),
  `hero_settle` as its own block (11, partly covered by `settleFrac`), and ranks 12–20. Next
  catalog growth follows CATALOG-GAPS order after the owner grades this phase's goldens.
- **Ingest:** eyes, anisotropy direction, wheel spoke count (no consumer yet).
- **Per-shot accent re-solve** in `reflection_rig` (continuity first: T4-01).
- **Harness:** the [V] vision judge, flow-based items (B-03, T3-12, T3-17), T4-04 grain/halation
  realism, variety score (phase 4), and frame QC gating (phase 6). Film grain in `mood_grade`
  (T4 only).
- **Director, rulebook, dice, farm** — phases 3, 4, 6.

## Later (site phase, spec §2b) — not in this plan

- **Viewer marker placement UI.** The user clicks the model to drop a marker and types its
  instruction. The viewer sends `anchor.space: "gltf"` points; Task 3's schema and checker
  already accept them.
- **Three viewer display modes, Plain by default:** *Plain* (the whole model in one matte neutral
  colour), *Material zones* (each material/texture region in its own flat colour, so the user can
  point at every separately controllable surface), *Final* (full materials and textures).
- **Remove the rain layer, weather and other fake "render" effects from the viewer.** The viewer
  is a brief-writing tool; the final look comes only from the Blender render.
- **Landing gallery:** varied subjects, worlds and moods at T3 once the director produces them.

---

## Done when

- `py -m pytest engine/tests harness/tests -q` passes, including the Blender tests.
- `py -m engine render engine/tests/fixtures/script_t3.json --profile engine/tests/fixtures/profiles/toycar.json --model assets-in/models/toycar/toycar.glb --out <dir> --tier preview --frames key`
  produces beauty frames, three passes per frame and `render_log.json`, and refuses any script
  the checker fails (exit 3).
- Blender's own camera projection matches `engine.geometry.project` to 1e-3 on sampled frames
  on both sides of a cut (Task 20).
- The subject is placed exactly where the SubjectProfile says, for static and rigged subjects
  (Tasks 6, 19).
- `py -m harness run --suite v0 --tier keyframes --models toycar` writes per-case reports and a
  summary. Every TIERS item appears as pass / fail / n/a / unmeasured, and the tier reached is
  marked provisional wherever items are unmeasured.
- Task 31's baseline numbers and the owner's first grades are in the next handoff. Thresholds
  are still report-only unless Task 31 Step 4 calibrated them with the owner's grades.

## Owner answers (2026-09-24)

1. **T2-07:** a clean studio world counts as meeting the atmosphere item (Task 13 code above;
   studio world blocks carry `studio: true` in the manifest). `haze_volume` is still built.
2. **Eval subjects:** CC-BY with attribution is fine. A ModVision fleet GLB may be used locally
   as the real-scale vehicle, never committed, shipped or shown.
3. **Grading:** Task 31 (baseline + owner grading) runs only after every director phase is built.
