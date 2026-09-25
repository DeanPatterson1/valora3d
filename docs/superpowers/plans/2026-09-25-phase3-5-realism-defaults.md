# Valora3D Phase 3½ — Realism Defaults Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every render quietly gets the physics nobody asks for — a grounded subject with a contact
seam, loaded tyres with a flat contact patch, a car body that sits on its springs and settles after a
stop, wheels that roll at the speed the subject moves, a landing that overshoots and settles (soft goods
squash), a soft subject that dips where it rests, wind-driven sway of foliage and hanging straps, grass
that gives way under the subject, dust that shows only in light shafts, and shadow caustics under glass —
all added by the **compiler** when the
subject qualifies, never chosen by the director, all stateless (no bake), all cheap.

**Architecture:**

- **Two new block kinds** (research/physics/BLOCKS.md §1). `realism`: always-on defaults, each with an
  `appliesWhen` rule evaluated against the SubjectProfile, the world, the motion and the effects.
  `field`: one singleton, `wind`, calm unless the script asks for wind. Both are system-owned: the
  checker resolves them (`realism[]`, `wind`) with `info`-severity issues, so the director's
  "pass before repair" metric is untouched.
- **Built on phase 3's contract, not beside it.** Phase-3 Task 12 (capability tags,
  `directorSelectable`, `requiresProfile`) and Task 12a (`alwaysOn`, `engine/realism.py`,
  pipeline-owned `script["realism"]`, compiler realism loop) define the contract. This plan adds
  the realism blocks, the richer `appliesWhen` resolution, the `field` kind and the ingest facts the
  rules need. **No file under `engine/director/` is edited.** Anything the director side must do is
  a hand-off item (end of this plan).
- **Pure maths in `engine/physics/`** (stdlib only, host-testable): tyre deflection and bulge, ground
  sink, suspension sag and settle, landing overshoot and squash, wheel angle from the path, motion
  events, wind envelope, sway bend, and the resolver. Blender code mirrors these functions and a
  Blender test proves the mirror.
- **One subject hierarchy** in every compiled scene: `valora_motion` (motion blocks keyframe it) →
  `valora_realism_offset` (realism keyframes it: sink, deflection, settle, squash) → `valora_subject`
  (placement) → the upload. **Placed space** P = the offset empty's local space: placed metres before
  motion and realism. All per-vertex realism is a Geometry Nodes deformer that works in P, reads named
  vertex attributes written once at compile time (`valora_tyre`, `valora_spin`, `valora_unsprung`,
  `valora_sway`, `valora_sway_len`), and reads time only through keyframed driver empties or Scene
  Time — so frame N never depends on frame N−1 (METHODS R1) and a frame range can render anywhere.
- **Checks.** Pure checker rules (resolution, wind default, catalog validation) plus Blender
  compile-probe checks ([C], research/physics/BLOCKS.md §5: `grounded`, `tyre_patch_present`,
  `wheel_roll_no_slip`, `settle_bounded`, `wind_coherent`, `no_particles_in_subject`), recorded in
  `compile.json` → `realismProbe`, report-only. Harness items PH-01 and PH-02 (BLOCKS.md §6).

**Tech Stack:** Python 3.12 dev / Blender 5.0.1 bundled 3.11. `engine/` stays stdlib-only at import
time (numpy only inside Blender helpers and behind a lazy import in one mask function that the host
tests use with the dev `py`'s numpy 2.4). Geometry Nodes (5.0 node idnames probed 2026-09-24, listed
where used), Cycles shadow caustics (`ob.cycles.is_caustics_caster/receiver`,
`light.cycles.is_caustics_light`, probed). pytest 8. `harness/` keeps numpy/Pillow/scikit-image.

**Spec and research:** `docs/superpowers/specs/2026-09-24-director-layer-design.md` §4.1–§4.6, §10
("Physics re-phasing", step 3½). `research/physics/PHASING.md` §2 "Phase 3½", `BLOCKS.md` §1 (kinds),
§2.1–§2.2 (block table), §5 (checker + compile-probe), §6 (PH-xx), `METHODS.md` §0 (R1–R10), §2.1,
§2.2, §2.4–§2.6, §2.9–§2.11, §3 (ingest facts), `TAXONOMY.md` §14 (always-on list), `ASSETS.md` (no
asset is needed in this phase: everything is procedural). Previous plans (style + what exists):
`docs/superpowers/plans/2026-09-24-director-phase2-compiler-t3-blocks.md`,
`docs/superpowers/plans/2026-09-25-director-phase3-director.md` (Tasks 12, 12a, 28, 29).

**Conventions (same as phases 1–3):**

- Run every command from the repo root `C:\Users\deand\Projects\rendering`, branch `renderer/director`.
- Use `py`, never bare `python` (Windows Store stub).
- Fast loop: `py -m pytest engine/tests harness/tests -q -m "not blender and not live"`. Blender loop
  for this plan: `py -m pytest engine/tests/test_realism_blender.py engine/tests/test_ingest_realism_blender.py -q -m blender`.
  Record the fast-loop count before Task 2 (Task 1 Step 3).
- Each commit message ends with the two attribution lines given in the session. Run
  `git diff --cached --name-only` before every commit and stage **only** the files the task names.
  Other terminals (phase 3, the harness agent) share the index.
- **Re-read before you edit.** Phase 3 is being built at the same time and edits `engine/catalog.py`,
  `engine/script.py`, `engine/checker.py`, `engine/compiler/blender_main.py`, `engine/profile.py`,
  `engine/ingest/*` and `harness/*`. Every task that touches one of those files starts by reading it at
  HEAD; the code blocks below show *what to add*, anchored on names (functions, constants), never on line
  numbers. Keep edits additive and small so both lanes rebase cleanly.
- **Render tests use ≤ 3 frames** (`keyframes` tier, 144 px short side, 4 samples). Compile-probe tests
  render nothing; they evaluate geometry at ≤ 3 frames. **The owner games on this machine:** Task 7
  (nine ingest launches) and Task 25 (a handful of ≤ 3-frame renders) ask first.
- **No owner grading in this phase** (owner rule 2026-09-24: all phases are built before owner
  render/grading tests). Every (eng) number goes in the calibration register at the end.
- **Codex is unavailable until 2026-09-29.** Delegate implementation to Opus subagents
  (`model: "opus"`), never Codex.
- **Network.** Nothing in this plan needs the network. If anything tries `api.anthropic.com` or a pip
  install and Avast/WebShield/Norton blocks it or it returns 403, **stop and report**; do not work
  around it.
- **Blender 5.0 API names:** the node idnames, socket names and enum values in this plan were probed in
  Blender 5.0.1 on 2026-09-24 (listed in the Task 12 header). Anything not listed there gets a probe
  step; **the Blender test is the arbiter, not this plan's text.**

---

## Coordination with phase 3 (the contract this plan builds on)

**Branch state when this plan was written (HEAD `7385eec`, 2026-09-25):** Task 12 (`8b44326`) and Task 12a
(`3084d5f`) have landed. `engine/catalog.py` already has `KINDS` with `realism`, `field` **and `sim`**,
treats every `realism` block as always-on (`_always_on`), accepts `requiresProfile` as a string or a list,
and `blender_main._refs` already yields `script["realism"]` after effects. Raw ingest sample rows are
already **10 wide**: column 9 is `open` (camera openness, `99a3ae2`), and `measure.Sample` has an `open`
field. The code below is written against that state.

| Phase-3 item | What this plan relies on | If it is missing |
|---|---|---|
| Task 12 | `Catalog.capabilities()`, `selectable_ids()`, `directorSelectable`, `capabilities` on manifests, `engine/director/vocabulary.json` with `KNOWN_TAGS` | Task 1 stops: report to the coordinator. Do not implement it here (two lanes writing the same files) |
| Task 12a | `alwaysOn`, `Catalog.always_on()`, `Catalog.applies()`, `REQUIRES_PROFILE`, `engine/realism.py::realism_defaults(profile, catalog)`, `script["realism"]` validation (`bad_realism`, `realism_not_always_on`), the realism build loop in `blender_main.py`, `engine/tests/test_realism.py` | Task 1 stops (as above) |
| Physics hand-off in the phase-3 plan | Vocabulary holds the block-only tags this plan's manifests declare: `sim.tyre_contact` (already in Task 12's table), `contact.tyre`, `contact.ground`, `contact.soft`, `vehicle.suspension`, `secondary.follow_through`, `foliage.sway` | Task 1 stops and sends the coordinator the exact JSON lines (Task 1 Step 2). This plan never edits `vocabulary.json` |
| Task 22/23 (`sanitize`, `fallback`) call `realism_defaults(profile, catalog)` | Kept working: Task 11 adds an **optional** `script=` argument; without it the old behaviour holds. The checker re-resolves `realism` anyway, with `info` issues only | — |
| Task 24 drift test (`every error code has a hint`) scans `engine/**/*.py` for `Issue(..., "error")` | This plan adds **no new error-severity issue codes**. Realism and wind resolution use `info`; malformed `wind` reuses the existing `bad_block_ref` / `unknown_block` codes through `_block` | — |
| Task 28 (`animationClips`) also regenerates the nine profiles | Task 7 regenerates after whichever ingest change lands last; both fields must be present in the committed profiles | Regenerate again; the fields are independent |
| Task 29 edits `blender_main.probe` and `checker._compat` | Anchored, additive edits here; re-read first | — |

**What realism does NOT do to the director:** realism blocks are `alwaysOn: true` and
`directorSelectable: false`, so they are never on the menu, never in the output schema, and never
reported as unsupported asks (PHASING §3 rule 5). The `wind` field is `directorSelectable: false` in
this phase and declares **no** capability tags, so a "windy" prompt stays honestly unsupported until
the director can set wind (hand-off H3).

---

## File map

| File | Responsibility | Task |
|---|---|---|
| `engine/catalog.py` | (`KINDS` already has `realism`, `field`, `sim`) validation of `appliesWhen`, `autoParams`, `physics`, world `groundType`/`hasFoliage`/`windDefault`, motion `subjectMotion`; wind params only on the field; `REQUIRES_PROFILE` + `softParts`, `danglingParts` | 2 |
| `engine/issues.py` | `info` severity (system decisions; nothing to fix) | 2 |
| `engine/blocks/world/studio_cyc/{block.json,build.py}` | `groundType: studio`, `windDefault: 0`; tags its floor `valora_ground` | 2, 14 |
| `engine/profile.py` | + `vehicle`, `groundContacts`, `softParts`, `danglingParts`; wheels gain `width`, `tyreBand`, `contact`, `separable` | 3 |
| `engine/blender/islands.py` | Per-vertex mesh-island ids (temporary GN modifier) and island summaries | 4 |
| `engine/ingest/blender_extract.py` | Raw `islands`, sample object/island columns, parts `obj` | 4 |
| `engine/tests/blender_fixtures.py` | + `wheeled`, `strap`, `plush` synthetic GLBs | 4 |
| `engine/physics/wheel_mask.py` | Which island spins, which vertices are tyre band, wheel box (one rule for ingest and compiler) | 5 |
| `engine/ingest/measure.py` | Wheel extras, vehicle facts, ground contacts, soft parts, dangling parts | 5, 6 |
| `engine/tests/fixtures/profiles/*.json` | Regenerated nine reference profiles | 7 |
| `engine/physics/{contact,tyre}.py` | Ground sink by ground type, AO distance, tyre deflection / patch / bulge | 8 |
| `engine/physics/{events,settle,suspension,wheel_spin}.py` | Stops and landings from the motion track; overshoot and squash; sag and settle; wheel angle | 9 |
| `engine/physics/{wind,sway}.py` | Wind vector, Beaufort, gust envelope; cantilever bend in wind | 10 |
| `engine/physics/applies.py`, `engine/realism.py`, `engine/checker.py`, `engine/script.py` | Resolver (`appliesWhen`, confidence, auto params), wind default, checker hook | 11 |
| `engine/physics/probes.py` | Pure pass rules for the compile-probe records | 11, 14–23 |
| `engine/blender/gn.py` | Geometry Nodes builder + placed-space helpers | 12 |
| `engine/blender/realism_rig.py` | The subject hierarchy, placed points, attribute writers, wheel tags, motion track, key series | 12 |
| `engine/blender/realism_probe.py` | Compile-probe measurements at ≤ 3 frames | 12, 14–23 |
| `engine/compiler/blender_main.py`, `engine/compiler/run.py` | Rig after placement; build order world → field → motion → lighting → effects → realism; `realismProbe` | 12 |
| `engine/tests/fixtures/blocks/{motion/test_slide_stop,motion/test_drop,world/test_lawn}/` | Test-only blocks (never in the shipped catalog) | 12, 20 |
| `engine/tests/realism_catalog.py` | Shipped catalog + fixture blocks in a temp root | 12 |
| `engine/blocks/field/wind/` | The wind field: `valora_wind` node group + scene record | 13 |
| `engine/blocks/effect/haze_volume/build.py` | Haze drifts with the wind (inactive when calm) | 13 |
| `engine/blocks/realism/{contact_ground,tyre_contact,suspension,wheel_roll,landing_settle,soft_rest,foliage_sway,ground_conform,dangling_sway,shaft_dust,glass_caustics}/` | The eleven realism blocks | 14–23 |
| `engine/blender/sway_nodes.py` | The one wind-bend deformer (foliage and dangling parts) | 20, 21 |
| `engine/tests/test_realism_blender.py` | Every realism Blender test (compile probes, ≤ 3 frames) | 12–23, 25 |
| `harness/physics.py`, `harness/score.py`, `harness/thresholds.json` | PH-01, PH-02 ([C] from `realismProbe`, [M] seam ratio) in a separate `physics` report section | 24 |

**Task list at a glance:** Chunk 0 gate + contracts (1–2) · Chunk 1 profile + ingest (3–7) ·
Chunk 2 pure physics + resolution (8–11) · Chunk 3 Blender plumbing (12–13) · Chunk 4 realism
blocks (14–23) · Chunk 5 harness, smoke, finish (24–26).

---
## Chunk 0: Gate and contracts

### Task 1: Gate — phase-3 Tasks 12 and 12a have landed

This plan builds on phase 3's capability and always-on contract. Do not start Task 2 until it exists.

**Files:** none changed.

- [ ] **Step 1: Check the contract is on the branch.**

Run: `py -m pytest engine/tests/test_realism.py engine/tests/test_capabilities.py -q`
Expected: PASS. Also confirm by eye that `engine/catalog.py` defines `always_on`, `applies`,
`capabilities`, `selectable_ids` and `REQUIRES_PROFILE`, and that `engine/realism.py` defines
`realism_defaults(profile, catalog)`.
If either test file is missing or fails: **stop.** Report "phase-3 Task 12/12a not landed; phase 3½
waits" to the coordinator. Do not implement Task 12 or 12a here.

- [ ] **Step 2: Check the vocabulary holds this plan's block-only tags.**

Run: `py -m pytest engine/tests/test_capabilities.py -q -k vocabulary` (it must pass) and search
`engine/director/vocabulary.json` for each of: `sim.tyre_contact`, `contact.tyre`, `contact.ground`,
`contact.soft`, `vehicle.suspension`, `secondary.follow_through`, `foliage.sway`.
If any is missing: **stop** and send the coordinator (phase-3 lane) exactly these entries to add under
`"tags"` (block-only tags: no phrases, no note; research/physics/BLOCKS.md §4.2 last rows):

```json
"contact.tyre": {"phrases": [], "note": null},
"contact.ground": {"phrases": [], "note": null},
"contact.soft": {"phrases": [], "note": null},
"vehicle.suspension": {"phrases": [], "note": null},
"secondary.follow_through": {"phrases": [], "note": null},
"foliage.sway": {"phrases": [], "note": null}
```

This plan never edits `vocabulary.json` (a director file).

- [ ] **Step 3: Record the baseline.**

Run: `py -m pytest engine/tests harness/tests -q -m "not blender and not live"`
Write the pass count into the task tracker ("baseline N passed, M deselected, date"). No commit.

---

### Task 2: Catalog — `realism` and `field` kinds, physics manifest keys, `info` severity

**Files:**
- Modify: `engine/catalog.py`, `engine/issues.py`, `engine/blocks/world/studio_cyc/block.json`
- Modify tests: `engine/tests/test_blocks_complete.py` (`BUILDABLE`), `engine/tests/test_issues.py`
  (`KINDS` already holds `realism`, `field`, `sim` since Task 12a: do not touch it or its test)
- Create: `engine/tests/test_catalog_physics.py`

- [ ] **Step 1: Write the failing tests.**

In `engine/tests/test_blocks_complete.py`:

```python
BUILDABLE = ("world", "lighting", "motion", "effect", "grade", "realism", "field")
```

Append to `engine/tests/test_issues.py`:

```python
def test_info_is_a_severity_and_never_an_error():
    i = Issue("realism_applied", "realism", "tyre_contact: profile wheels", "info")
    assert errors([i]) == [] and i.to_dict()["severity"] == "info"
```

Create `engine/tests/test_catalog_physics.py`:

```python
import pytest

from engine.catalog import GROUND_TYPES, KINDS, Catalog, CatalogError
from engine.tests.test_catalog import _base, _write


def _realism(bid="r", **extra):
    m = _base(bid, kind="realism", alwaysOn=True, directorSelectable=False,
              appliesWhen={"placement": ["ground"]})
    m.update(extra)
    return m


def test_new_kinds_exist():
    assert {"realism", "field", "sim"} <= set(KINDS)
    assert "studio" in GROUND_TYPES and "grass" in GROUND_TYPES


def test_a_realism_block_loads(tmp_path):
    _write(tmp_path, "realism", "r", _realism(autoParams=["x"], params={
        "x": {"type": "number", "min": 0, "max": 1, "default": 0.5}}))
    assert Catalog.load(tmp_path).ids("realism") == ["r"]


@pytest.mark.parametrize("extra,match", [
    ({"alwaysOn": False}, "always on"),
    ({"directorSelectable": True}, "always on"),
    ({"appliesWhen": None}, "appliesWhen"),
    ({"appliesWhen": {"weather": ["rain"]}}, "appliesWhen"),
    ({"appliesWhen": {"profile": ["wings"]}}, "appliesWhen.profile"),
    ({"appliesWhen": {"motion": ["flies"]}}, "appliesWhen.motion"),
    ({"appliesWhen": {"world": {"groundType": ["lava"]}}}, "appliesWhen.world"),
    ({"appliesWhen": {"materials": {"glass": 1.5}}}, "appliesWhen.materials"),
    ({"appliesWhen": {"sizeM": [2.0, 1.0]}}, "appliesWhen.sizeM"),
    ({"autoParams": ["nope"]}, "autoParams"),
    ({"physics": {"taxonomy": ["cd-2"]}}, "physics.taxonomy"),
    ({"physics": {"state": "fluid"}}, "physics.state"),
    ({"physics": {"windDriven": "yes"}}, "physics.windDriven"),
])
def test_bad_realism_manifests_are_rejected(tmp_path, extra, match):
    _write(tmp_path, "realism", "r", _realism(**extra))
    with pytest.raises(CatalogError, match=match):
        Catalog.load(tmp_path)


def test_applies_when_effects_must_exist(tmp_path):
    _write(tmp_path, "realism", "r", _realism(appliesWhen={"effects": ["rain"]}))
    with pytest.raises(CatalogError, match="unknown effect 'rain'"):
        Catalog.load(tmp_path)


def test_the_only_field_is_wind(tmp_path):
    _write(tmp_path, "field", "gravity", _base("gravity", kind="field", directorSelectable=False))
    with pytest.raises(CatalogError, match="only field is 'wind'"):
        Catalog.load(tmp_path)


def test_only_the_field_owns_wind_params(tmp_path):
    _write(tmp_path, "effect", "e", _base("e", kind="effect", params={
        "windSpeed": {"type": "number", "min": 0, "max": 1, "default": 0}}))
    with pytest.raises(CatalogError, match="wind params"):
        Catalog.load(tmp_path)


@pytest.mark.parametrize("extra,match", [({"groundType": "lava"}, "groundType"),
                                         ({"hasFoliage": "yes"}, "hasFoliage"),
                                         ({"windDefault": 20}, "windDefault")])
def test_world_physics_keys_are_validated(tmp_path, extra, match):
    _write(tmp_path, "world", "w", _base("w", **extra))
    with pytest.raises(CatalogError, match=match):
        Catalog.load(tmp_path)


@pytest.mark.parametrize("bad", [{"flies": True}, {"translates": "yes"}, ["translates"]])
def test_motion_subject_motion_is_validated(tmp_path, bad):
    _write(tmp_path, "motion", "m", _base("m", kind="motion", subjectMotion=bad))
    with pytest.raises(CatalogError, match="subjectMotion"):
        Catalog.load(tmp_path)


def test_realism_may_require_the_new_profile_facts(tmp_path):
    _write(tmp_path, "realism", "r", _realism(requiresProfile="softParts"))
    assert Catalog.load(tmp_path).get("realism", "r")["requiresProfile"] == "softParts"


def test_shipped_studio_declares_its_ground_and_still_air():
    m = Catalog.load().get("world", "studio_cyc")
    assert m["groundType"] == "studio" and m["hasFoliage"] is False and m["windDefault"] == 0.0
```

- [ ] **Step 2: Run, expect FAIL.**

Run: `py -m pytest engine/tests/test_catalog_physics.py engine/tests/test_catalog.py engine/tests/test_issues.py -q`
Expected: FAIL (`ImportError: cannot import name 'GROUND_TYPES'`).

- [ ] **Step 3: Implement.**

`engine/issues.py`:

```python
SEVERITIES = ("info", "repaired", "warning", "error")
```
and the field comment: `# "info" (the system decided something, e.g. which realism applies; nothing to fix),
"repaired" (fixed in place), "warning" (renders; worth a look) or "error" (back to the director)`.

`engine/catalog.py` — read it first (Tasks 12/12a changed it). Leave `KINDS` alone, extend
`REQUIRES_PROFILE`, add the constants and three checkers, call them, and add the post-load check:

```python
REQUIRES_PROFILE = ("animationClips", "wheels", "parts", "rigged", "softParts", "danglingParts")
```
(keep whatever Task 12a listed, and add the last two.)

```python
# Physics (research/physics/BLOCKS.md §1-§2). Ground types drive realism appliesWhen and auto params.
GROUND_TYPES = ("studio", "asphalt", "dirt", "gravel", "sand", "snow", "grass", "water", "interior_floor", "rug")
MOTION_FLAGS = ("translates", "stops", "lands")          # what a motion block does to the subject
PROFILE_FACTS = ("wheels", "wheelsSeparable", "tyreBand", "bodySeparable", "softParts", "softGround",
                 "danglingParts")                          # engine/physics/applies.py computes each
MATERIAL_CLASSES = ("emissive", "glass", "skin", "metal", "glossy", "fabric", "matte")  # measure.material_class
_APPLIES_KEYS = ("placement", "profile", "profileNot", "world", "motion", "effects", "materials", "sizeM")
_WIND_PARAM = re.compile(r"^(?:wind|gust)", re.I)
_TAXON = re.compile(r"^[A-Z]{2}-\d{2}$")


def _str_list(where, aw, key, allowed=None):
    v = aw.get(key, [])
    if (not isinstance(v, list) or not all(isinstance(x, str) for x in v)
            or (allowed is not None and set(v) - set(allowed))):
        raise CatalogError(f"{where}: appliesWhen.{key} must be a list of strings"
                           + (f" from {list(allowed)}" if allowed is not None else ""))


def _check_applies(where, aw):
    """appliesWhen: every present key must hold (AND). Resolved by engine/physics/applies.py."""
    if not isinstance(aw, dict) or set(aw) - set(_APPLIES_KEYS):
        raise CatalogError(f"{where}: appliesWhen must be an object with keys from {list(_APPLIES_KEYS)}")
    _str_list(where, aw, "placement", ("ground", "float"))
    _str_list(where, aw, "profile", PROFILE_FACTS)
    _str_list(where, aw, "profileNot", PROFILE_FACTS)
    _str_list(where, aw, "motion", MOTION_FLAGS)
    _str_list(where, aw, "effects")
    w = aw.get("world", {})
    if (not isinstance(w, dict) or set(w) - {"groundType", "hasFoliage"}
            or ("groundType" in w and (not isinstance(w["groundType"], list) or set(w["groundType"]) - set(GROUND_TYPES)))
            or ("hasFoliage" in w and not isinstance(w["hasFoliage"], bool))):
        raise CatalogError(f"{where}: appliesWhen.world takes groundType (list from {list(GROUND_TYPES)}) "
                           "and hasFoliage (bool)")
    mats = aw.get("materials", {})
    if (not isinstance(mats, dict) or set(mats) - set(MATERIAL_CLASSES)
            or not all(_is_num(v) and 0 < v <= 1 for v in mats.values())):
        raise CatalogError(f"{where}: appliesWhen.materials maps a material class to a share in (0, 1]")
    if "sizeM" in aw:
        s = aw["sizeM"]
        if not (isinstance(s, list) and len(s) == 2 and all(_is_num(v) for v in s) and 0 <= s[0] <= s[1]):
            raise CatalogError(f"{where}: appliesWhen.sizeM must be [min, max] metres")


def _check_physics_meta(where, p):
    if not isinstance(p, dict):
        raise CatalogError(f"{where}: physics must be an object")
    tx = p.get("taxonomy", [])
    if not isinstance(tx, list) or not all(isinstance(t, str) and _TAXON.match(t) for t in tx):
        raise CatalogError(f"{where}: physics.taxonomy must be TAXONOMY ids like 'CD-02'")
    if p.get("state", "stateless") not in ("stateless", "baked"):
        raise CatalogError(f"{where}: physics.state must be 'stateless' or 'baked'")
    for k in ("touchesSubject", "windDriven"):
        if not isinstance(p.get(k, False), bool):
            raise CatalogError(f"{where}: physics.{k} must be true or false")


def _check_physics(where, kind, m):
    if kind != "field":
        bad = [p for p in m["params"] if _WIND_PARAM.match(p)]
        if bad:
            raise CatalogError(f"{where}: only the wind field owns wind params, found {bad}")
    if kind == "world":
        if m.get("groundType", "studio") not in GROUND_TYPES:
            raise CatalogError(f"{where}: groundType must be one of {list(GROUND_TYPES)}")
        if not isinstance(m.get("hasFoliage", False), bool):
            raise CatalogError(f"{where}: hasFoliage must be true or false")
        wd = m.get("windDefault", 0.0)
        if not _is_num(wd) or not 0 <= wd <= 14:
            raise CatalogError(f"{where}: windDefault must be a wind speed in [0, 14] m/s")
    if kind == "motion":
        sm = m.get("subjectMotion", {})
        if (not isinstance(sm, dict) or set(sm) - set(MOTION_FLAGS)
                or not all(isinstance(v, bool) for v in sm.values())):
            raise CatalogError(f"{where}: subjectMotion maps {list(MOTION_FLAGS)} to true/false")
    if kind == "realism":
        # Task 12a: every realism block is always-on (alwaysOn may be omitted); it can never be chosen.
        if m.get("alwaysOn", True) is not True or m.get("directorSelectable", False) is not False:
            raise CatalogError(f"{where}: realism blocks are always on and never director-selectable")
        if "appliesWhen" in m:          # absent = applies to every subject (phase-3 test fixtures omit it)
            _check_applies(where, m["appliesWhen"])
        auto = m.get("autoParams", [])
        if not isinstance(auto, list) or set(auto) - set(m["params"]):
            raise CatalogError(f"{where}: autoParams must name params of this block")
    if kind == "field" and m["id"] != "wind":
        raise CatalogError(f"{where}: the only field is 'wind' (one shared wind per clip)")
    if "physics" in m:
        _check_physics_meta(where, m["physics"])
```

In `_check_manifest`, right after the `for name, spec in m["params"].items(): _check_param(...)` loop:

```python
    _check_physics(where, folder_kind, m)
```

In `Catalog.load`, after the kind loop and before `return cls(blocks, root)`:

```python
        for (kind, bid), m in blocks.items():
            for eid in (m.get("appliesWhen") or {}).get("effects", []):
                if ("effect", eid) not in blocks:
                    raise CatalogError(f"{kind}/{bid}: appliesWhen.effects names unknown effect '{eid}'")
```

(`re` is already imported by Task 12; add `import re` if it is not.)

`engine/blocks/world/studio_cyc/block.json` — add three keys (keep the rest):

```json
  "groundType": "studio",
  "hasFoliage": false,
  "windDefault": 0.0,
```

- [ ] **Step 4: Run, expect PASS.**

Run: `py -m pytest engine/tests/test_catalog_physics.py engine/tests/test_catalog.py engine/tests/test_realism.py engine/tests/test_issues.py engine/tests/test_blocks_complete.py -q`, then the fast loop.
`test_catalog.py::test_physics_kinds_are_accepted_and_realism_is_never_selectable` and
`test_realism.py::test_realism_kind_is_always_on_and_delivers_its_tag_when_the_subject_qualifies` (phase 3)
must still pass: they write realism blocks without `alwaysOn` or `appliesWhen`.
Expected: PASS; fast loop = baseline + the new tests.

- [ ] **Step 5: Commit.**

```bash
git add engine/catalog.py engine/issues.py engine/blocks/world/studio_cyc/block.json engine/tests/test_blocks_complete.py engine/tests/test_issues.py engine/tests/test_catalog_physics.py
git commit -m "feat(catalog): realism and field kinds, appliesWhen and physics manifest keys, info severity"
```

---

## Chunk 1: SubjectProfile and ingest

PHASING §2 "Phase 3½" and METHODS §3 list the ingest facts the realism rules need. This chunk adds
exactly those, each with a confidence, and nothing for later phases (`collisionProxy`, `upFacing`,
`container`, `emitterPoints` stay phase 5–6). Names are never trusted (spec §4.1): every fact is
geometry + material properties.

### Task 3: SubjectProfile fields

**Files:**
- Modify: `engine/profile.py`
- Test: `engine/tests/test_profile.py`

- [ ] **Step 1: Write the failing tests** — append to `engine/tests/test_profile.py` (the file has no
document helper; add one):

```python
def _doc():
    return json.loads((FIX / "profile_car.json").read_text())


def test_realism_fields_default_empty_for_older_documents():
    p = SubjectProfile.from_dict(_doc())
    assert p.vehicle == {} and p.groundContacts == [] and p.softParts == [] and p.danglingParts == []


def test_realism_fields_round_trip():
    d = _doc()
    d.update(vehicle={"forwardAxis": [0.0, 1.0, 0.0], "wheelbaseM": 2.5, "trackM": 1.6, "rideHeightM": 0.12,
                      "bodySeparable": True, "vehicleClass": "sport"},
             groundContacts=[{"center": [0.0, 0.0, 0.0], "radius": 0.1, "share": 1.0}],
             softParts=[{"part": 0, "share": 0.9, "touchesGround": True, "confidence": "high"}],
             danglingParts=[{"pivot": [0, 0, 0.3], "tip": [0, 0, 0.15], "radius": 0.005, "lengthM": 0.15,
                             "confidence": "high"}])
    assert SubjectProfile.from_dict(d).to_dict() == SubjectProfile.from_dict(SubjectProfile.from_dict(d).to_dict()).to_dict()
    assert SubjectProfile.from_dict(d).vehicle["vehicleClass"] == "sport"
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_profile.py -q` (AttributeError `vehicle`).

- [ ] **Step 3: Implement** — in `SubjectProfile`, after the last field that exists at HEAD (phase 3
adds `animationClips`; keep it) and before `schema`:

```python
    vehicle: dict = field(default_factory=dict)          # {forwardAxis, wheelbaseM, trackM, rideHeightM, bodySeparable, vehicleClass}
    groundContacts: list = field(default_factory=list)   # [{center, radius, share}] support patches at z ~ 0
    softParts: list = field(default_factory=list)        # [{part, share, touchesGround, confidence}]
    danglingParts: list = field(default_factory=list)    # [{pivot, tip, radius, lengthM, confidence}]
```

and extend the class docstring's extension list:

```
    wheels[]           also width, tyreBand [inner/r, 1.0], contact [x, y, 0], separable (a spin-safe
                       mesh island per wheel); missing on older documents
    vehicle            vehicle facts when wheels were found: forward (long) axis, wheelbase, track, ride
                       height, whether the body is a separate island from every wheel, class hint
                       (sport | comfort | offroad | toy; a hint for suspension params, never a gate)
    groundContacts     the support patches where the subject touches z = 0
    softParts          parts that read soft (fabric/skin-like), with confidence; high only when the
                       subject is hand- or furniture-sized, unrigged and wheel-less
    danglingParts      thin parts attached at one end that hang (straps, cords), with confidence
```

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests/test_profile.py -q`, then the fast loop.

- [ ] **Step 5: Commit**

```bash
git add engine/profile.py engine/tests/test_profile.py
git commit -m "feat(profile): vehicle, ground contacts, soft and dangling parts for realism defaults"
```

---

### Task 4: Mesh islands in ingest (raw `islands`, sample origins, part objects)

Wheel separability, spin safety and dangling detection all need to know which vertices form one
connected piece. Blender computes that natively: a temporary Geometry Nodes modifier stores
`Mesh Island → Island Index` as a point attribute (`GeometryNodeInputMeshIsland`,
`GeometryNodeStoreNamedAttribute` with `data_type="INT"`, `domain="POINT"`; probed in 5.0.1).

**Files:**
- Create: `engine/blender/islands.py`
- Modify: `engine/ingest/blender_extract.py`, `engine/tests/blender_fixtures.py`
- Create: `engine/tests/test_ingest_realism_blender.py`

- [ ] **Step 1: Add the synthetic fixtures** — in `engine/tests/blender_fixtures.py`, add three scripts
and register them in `make_glb`'s dict (`"wheeled": _WHEELED, "strap": _STRAP, "plush": _PLUSH`) and
its docstring:

```python
_MATS = r'''
def mat(name, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True
    n = next(x for x in m.node_tree.nodes if x.type == "BSDF_PRINCIPLED")
    for k, v in kw.items(): n.inputs[k].default_value = v
    return m
'''

# A car-like block on four separate wheels (tyre torus + rim + an off-axis caliper), axle along x.
# Tyre outer radius 0.35, inner 0.21 (tyreBand ~0.6), tube 0.14 wide. Body 1.4 x 4.0, z 0.20-1.10.
_WHEELED = r'''
import bpy, sys, math
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
''' + _MATS + r'''
rubber, metal, paint = mat("rubber", Roughness=0.9), mat("rim", Metallic=1.0, Roughness=0.3), mat("paint", Metallic=0.0, Roughness=0.2)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.65)); b = bpy.context.object
b.scale = (1.4, 4.0, 0.9); b.data.materials.append(paint)
bpy.ops.object.transform_apply(scale=True)
for x in (-0.8, 0.8):
    for y in (-1.3, 1.3):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.28, minor_radius=0.07, major_segments=64, minor_segments=16,
                                         location=(x, y, 0.35), rotation=(0, math.pi / 2, 0))
        bpy.context.object.data.materials.append(rubber)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.21, depth=0.12, vertices=48, location=(x, y, 0.35),
                                            rotation=(0, math.pi / 2, 0))
        bpy.context.object.data.materials.append(metal)
        bpy.ops.mesh.primitive_cube_add(size=0.08, location=(x, y + 0.12, 0.47))  # caliper: inside the wheel, off the axle
        bpy.context.object.data.materials.append(metal)
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
'''

# A camera-sized box on a pedestal with a thin strap hanging from its side (top touches the box).
_STRAP = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
''' + _MATS + r'''
body = mat("body", Roughness=0.5)
bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.30, location=(0, 0, 0.15)); bpy.context.object.data.materials.append(body)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.36)); c = bpy.context.object
c.scale = (0.20, 0.10, 0.12); bpy.ops.object.transform_apply(scale=True); c.data.materials.append(body)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.104, 0, 0.345)); s = bpy.context.object
s.scale = (0.004, 0.012, 0.15); bpy.ops.object.transform_apply(scale=True); s.data.materials.append(mat("strap", Roughness=0.9))
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
'''

# A soft round cushion-like object: fabric-rough, 0.3 m, resting on its base.
_PLUSH = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
''' + _MATS + r'''
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, segments=48, ring_count=24, location=(0, 0, 0.15))
bpy.context.object.data.materials.append(mat("felt", Roughness=0.95))
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB")
'''
```

The strap's top (z 0.42) sits inside the box's side band (box x 0.00–0.10 +/-, strap centred at
x 0.104 with half-thickness 0.002, so it touches the box face at x 0.10); its bottom is at z 0.27,
free and off the ground.

- [ ] **Step 2: Write the failing Blender test** — `engine/tests/test_ingest_realism_blender.py`:

```python
import json

import pytest

from engine.ingest.run import _extract
from engine.tests.blender_fixtures import make_glb
from engine.tests.conftest import requires_blender

pytestmark = [pytest.mark.blender, requires_blender]


def _raw(kind, tmp_path):
    glb = make_glb(kind, tmp_path / f"{kind}.glb")
    _extract(glb, tmp_path)  # writes raw.json next to it
    return json.loads((tmp_path / "raw.json").read_text(encoding="utf-8"))


def test_raw_carries_islands_sample_origins_and_part_objects(tmp_path):
    raw = _raw("wheeled", tmp_path)
    assert all(len(r) == 12 for r in raw["samples"])            # [.., curv, open, obj, island]
    objs = {int(r[10]) for r in raw["samples"]}
    assert len(objs) >= 9                                        # body + 4 tyres + 4 rims (+ calipers)
    assert all(int(r[11]) >= 0 for r in raw["samples"])
    assert all({"obj", "id", "n", "lo", "hi", "centroid"} <= set(i) for i in raw["islands"])
    assert len(raw["islands"]) >= 13                             # every separate piece is one island
    assert all("obj" in p for p in raw["parts"])
```

`surface_samples` keeps returning 9 columns (its `(500, 9)` test stays as is); the origins travel in a
separate list and `main()` appends them after the `open` column.

- [ ] **Step 3: Run, expect FAIL** — `py -m pytest engine/tests/test_ingest_realism_blender.py -q -m blender`
(KeyError `islands` or 9-wide rows).

- [ ] **Step 4: Implement.**

`engine/blender/islands.py`:

```python
"""Per-vertex mesh-island ids via a temporary Geometry Nodes modifier (runs inside Blender).

Ingest (island summaries, the island of every surface sample) and the compiler (wheel tags) use the same
helper, so both see the same pieces. Blender numbers islands deterministically for a given mesh."""
import bpy

ATTR = "valora_island"
_GROUP = "valora_island_ids"
MOD = "valora_islands"


def _group():
    ng = bpy.data.node_groups.get(_GROUP)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(_GROUP, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi, go = ng.nodes.new("NodeGroupInput"), ng.nodes.new("NodeGroupOutput")
    st = ng.nodes.new("GeometryNodeStoreNamedAttribute")
    st.data_type, st.domain = "INT", "POINT"
    st.inputs["Name"].default_value = ATTR
    isl = ng.nodes.new("GeometryNodeInputMeshIsland")
    ng.links.new(gi.outputs[0], st.inputs["Geometry"])
    ng.links.new(isl.outputs["Island Index"], st.inputs["Value"])
    ng.links.new(st.outputs[0], go.inputs[0])
    return ng


def add_island_modifier(obj):
    mod = obj.modifiers.new(MOD, "NODES")
    mod.node_group = _group()
    return mod


def island_array(mesh):
    """int32 island id per vertex of an evaluated mesh that went through add_island_modifier, else None."""
    import numpy as np
    a = mesh.attributes.get(ATTR)
    if a is None or a.domain != "POINT":
        return None
    out = np.empty(len(mesh.vertices), dtype=np.int32)
    a.data.foreach_get("value", out)
    return out


def vertex_islands(obj):
    """Island id per ORIGINAL vertex of obj, or None when evaluation changed the vertex count."""
    mod = add_island_modifier(obj)
    try:
        bpy.context.view_layer.update()
        ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        try:
            arr = island_array(me)
            return arr if arr is not None and len(arr) == len(obj.data.vertices) else None
        finally:
            ev.to_mesh_clear()
    finally:
        obj.modifiers.remove(mod)


def summaries(co, isl, obj_index, min_n=8):
    """[{obj, id, n, lo, hi, centroid}] per island with >= min_n vertices. co: (n, 3) points."""
    import numpy as np
    if isl is None or not len(isl):
        return []
    n = np.bincount(isl)
    lo = np.full((len(n), 3), np.inf)
    hi = np.full((len(n), 3), -np.inf)
    np.minimum.at(lo, isl, co)
    np.maximum.at(hi, isl, co)
    sums = np.stack([np.bincount(isl, weights=co[:, k], minlength=len(n)) for k in range(3)], 1)
    return [{"obj": int(obj_index), "id": int(i), "n": int(n[i]), "lo": lo[i].tolist(), "hi": hi[i].tolist(),
             "centroid": (sums[i] / n[i]).tolist()} for i in np.nonzero(n >= min_n)[0]]
```

`engine/ingest/blender_extract.py`:

1. Imports: `from engine.blender.islands import add_island_modifier, island_array, summaries`.
2. Constant: `MAX_ISLANDS = 4096  # largest islands kept (wheels, straps and bodies are all large)`.
3. `surface_samples(meshes, deps, gidx_of, k=MAX_SAMPLES, seed=0, origins=None)`: rows stay 9 wide; when
   `origins` is a list, one `(obj, island)` pair is appended to it per row, in row order. Pass 1 also
   records island summaries. In pass 1, after `rec = {...}`:

```python
        isl = island_array(mesh)
        if len(mesh.vertices):
            co = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
            mesh.vertices.foreach_get("co", co)
            rec["islands"] = summaries(co.reshape(-1, 3), isl, meshes.index(obj))
```
   In pass 2, before the triangle loop: `isl = island_array(mesh)` and `oi = meshes.index(obj)`; right
   after each `rows.append(...)` add

```python
                if origins is not None:
                    origins.append((oi, int(isl[lt.vertices[0]]) if isl is not None else -1))
```
   Document it in the docstring: origins = (index in `meshes`, that object's island id, -1 if unknown).
4. `main()`: right after `objs, meshes = import_subject(glb)` and `posed_bounds(...)`, before
   `surface_samples`: `for o in meshes: add_island_modifier(o)`. Then:

```python
    parts = [{"boundsMin": [float(v) for v in r["lo"]], "boundsMax": [float(v) for v in r["hi"]],
              "polys": r["polys"], "obj": i} for i, r in enumerate(info) if r["polys"]]
    islands = sorted((s for r in info for s in r.get("islands", [])), key=lambda s: -s["n"])[:MAX_ISLANDS]
```
   and add `"islands": [{**s, "lo": [round(v, 6) for v in s["lo"]], "hi": [round(v, 6) for v in s["hi"]],
   "centroid": [round(v, 6) for v in s["centroid"]]} for s in islands],` to `raw`. Call
   `samples, info = surface_samples(meshes, deps, gidx_of, origins=origins)` with `origins = []`, and
   after the existing `open` column is stacked (`np.column_stack([samples, openness(...)])`) stack the
   origins too: `samples = np.column_stack([samples, np.array(origins, dtype=np.float64).reshape(-1, 2)])`.
   Rows are now `[x, y, z, nx, ny, nz, w, mat, curv, open, obj, island]`; in the sample-row rounding
   comprehension keep columns 10 and 11 as ints (`int(v) if i >= 10 else ...`), column 9 (`open`) stays a
   float.

`posed_bounds` runs before the island modifiers are added, so bounds are unaffected; `world_bounds`
still sees the same geometry (the modifier only stores an attribute).

- [ ] **Step 5: Run, expect PASS** — `py -m pytest engine/tests/test_ingest_realism_blender.py engine/tests/test_ingest_sampling_blender.py engine/tests/test_ingest_blender.py -q -m blender`.
`measure._samples` reads `row[:9]` and `row[9]` only, so 12-wide rows load unchanged until Task 5.

- [ ] **Step 6: Commit**

```bash
git add engine/blender/islands.py engine/ingest/blender_extract.py engine/tests/blender_fixtures.py engine/tests/test_ingest_realism_blender.py
git commit -m "feat(ingest): mesh islands, sample object and island ids, part objects"
```

---

### Task 5: Wheel extras and vehicle facts

**Files:**
- Create: `engine/physics/__init__.py`, `engine/physics/wheel_mask.py`, `engine/tests/test_physics_wheel_mask.py`
- Modify: `engine/ingest/measure.py`
- Test: `engine/tests/test_measure.py`

- [ ] **Step 1: Write the failing tests.**

`engine/tests/test_physics_wheel_mask.py`:

```python
import random

import pytest

from engine.physics.wheel_mask import half_width, in_wheel_box, island_spins, tyre_mask, tyre_weight

W = {"center": [0.8, 1.3, 0.35], "radius": 0.35, "axis": [1.0, 0.0, 0.0], "width": 0.14, "tyreBand": [0.6, 1.0]}


def test_half_width_falls_back_when_ingest_found_no_width():
    assert half_width(W) == pytest.approx(0.07)
    assert half_width({**W, "width": None}) == pytest.approx(0.3 * 0.35)


def test_whole_tyre_and_rim_spin_but_an_off_axis_caliper_does_not():
    tyre = ([0.73, 0.95, 0.0], [0.87, 1.65, 0.70], [0.8, 1.3, 0.35])
    caliper = ([0.74, 1.38, 0.43], [0.82, 1.46, 0.51], [0.78, 1.42, 0.47])
    body = ([-0.7, -2.0, 0.2], [0.7, 2.0, 1.1], [0.0, 0.0, 0.65])
    assert island_spins(*tyre, W) and in_wheel_box(*tyre[:2], W)
    assert in_wheel_box(*caliper[:2], W) and not island_spins(*caliper, W)
    assert not in_wheel_box(*body[:2], W)


def test_tyre_band_is_the_rubber_ring_not_the_rim():
    assert tyre_weight([0.8, 1.3, 0.0], W) == 1           # bottom of the tread
    assert tyre_weight([0.8, 1.3, 0.35 - 0.25], W) == 1   # sidewall at 0.71 r
    assert tyre_weight([0.8, 1.3, 0.35 - 0.10], W) == 0   # rim face at 0.29 r
    assert tyre_weight([0.5, 1.3, 0.0], W) == 0           # outside the tyre's width


def test_numpy_mask_matches_the_scalar_rule():
    np = pytest.importorskip("numpy")
    rng = random.Random(1)
    pts = [[0.8 + rng.uniform(-0.2, 0.2), 1.3 + rng.uniform(-0.4, 0.4), rng.uniform(-0.05, 0.75)] for _ in range(3000)]
    got = tyre_mask(np.array(pts), W)
    assert got.tolist() == [bool(tyre_weight(p, W)) for p in pts]
```

Append to `engine/tests/test_measure.py`:

```python
import math

from engine.ingest.measure import Sample, vehicle_facts, wheel_extras


def _torus(c, R, tube, cls, obj, island, n=240, gloss=False):
    """Samples on a tyre-like torus whose axle is x (placed coords)."""
    out = []
    for i in range(n):
        u, v = 2 * math.pi * i / n, 2 * math.pi * ((i * 7) % n) / n
        rho = R + tube * math.cos(v)
        p = (c[0] + tube * math.sin(v), c[1] + rho * math.cos(u), c[2] + rho * math.sin(u))
        nrm = (math.sin(v), math.cos(v) * math.cos(u), math.cos(v) * math.sin(u))
        out.append(Sample(p, nrm, 1e-4, cls, gloss, False, 0.0, obj=obj, island=island))
    return out


def test_wheel_extras_measure_width_tyre_band_contact_and_separability():
    w = {"center": [0.8, 1.3, 0.35], "radius": 0.35, "axis": [1.0, 0.0, 0.0], "confidence": "high"}
    samples = _torus(w["center"], 0.28, 0.07, "fabric", 1, 0)
    islands = [{"key": (1, 0), "n": 1024, "lo": [0.73, 0.95, 0.0], "hi": [0.87, 1.65, 0.70], "centroid": [0.8, 1.3, 0.35]}]
    bmin, bmax = [-0.9, -2.0, 0.0], [0.9, 2.0, 1.1]
    wheel_extras([w], samples, islands, bmin, bmax)
    assert 0.09 <= w["width"] <= 0.14
    assert 0.55 <= w["tyreBand"][0] <= 0.66 and w["tyreBand"][1] == 1.0
    assert w["contact"] == [0.8, 1.3, 0.0] and w["separable"] is True


def test_a_wheel_welded_into_the_body_is_not_separable():
    w = {"center": [0.8, 1.3, 0.35], "radius": 0.35, "axis": [1.0, 0.0, 0.0], "confidence": "high"}
    body = [{"key": (0, 0), "n": 9000, "lo": [-0.9, -2.0, 0.0], "hi": [0.9, 2.0, 1.1], "centroid": [0, 0, 0.6]}]
    wheel_extras([w], _torus(w["center"], 0.28, 0.07, "fabric", 0, 0), body, [-0.9, -2.0, 0.0], [0.9, 2.0, 1.1])
    assert w["separable"] is False


def test_vehicle_facts_classify_a_low_separable_car_as_sport():
    ws = [{"center": [x, y, 0.35], "radius": 0.35, "axis": [1.0, 0.0, 0.0], "separable": True, "width": 0.14,
           "tyreBand": [0.6, 1.0]} for x in (-0.8, 0.8) for y in (-1.3, 1.3)]
    body = [Sample((x / 10, y / 10, 0.2 + z / 10), (0, 0, -1), 1e-4, "glossy", True, False, 0.0, obj=0, island=0)
            for x in range(-6, 7) for y in range(-19, 20) for z in (0, 9)]
    v = vehicle_facts(ws, body, [-0.9, -2.0, 0.0], [0.9, 2.0, 1.1])
    assert v["forwardAxis"] == [0.0, 1.0, 0.0] and v["wheelbaseM"] == pytest.approx(2.6)
    assert v["trackM"] == pytest.approx(1.6) and v["rideHeightM"] == pytest.approx(0.2, abs=0.01)
    assert v["bodySeparable"] is True and v["vehicleClass"] == "sport"
```

(`pytest` is already imported in `test_measure.py`; add it if not.)

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_physics_wheel_mask.py engine/tests/test_measure.py -q`.

- [ ] **Step 3: Implement.**

`engine/physics/__init__.py`:

```python
"""Pure physics maths for realism defaults (research/physics/). Stdlib only: the checker (host) and the
compiler (Blender) call the same functions, so what is checked is what renders."""
```

`engine/physics/wheel_mask.py`:

```python
"""Which pieces of a wheel spin and which vertices are tyre (METHODS §2.1 CD-02, §3). One rule for ingest
(island summaries) and the compiler (vertex arrays). Placed coordinates; wheels as SubjectProfile.wheels."""
import math

RADIAL_MAX = 1.05       # x r: a wheel piece lies within the tyre's outer radius (+5% for tread noise)
AXIAL_MARGIN = 0.05     # x r beyond the half width
SPIN_AXIS_TOL = 0.05    # x r: a spinning piece is round, so its centroid sits on the axle (a caliper does not)
BAND_SLACK = 0.02       # x r below tyreBand[0]
DEFAULT_BAND = (0.62, 1.0)   # METHODS CD-02 "tyre ring r in [0.62 r, 1.0 r]"
DEFAULT_HALF_WIDTH = 0.3     # x r when ingest measured no width (eng)


def _frame(w):
    ai = max(range(3), key=lambda k: abs(w["axis"][k]))
    return ai, [k for k in range(3) if k != ai]


def half_width(w):
    return 0.5 * w["width"] if w.get("width") else DEFAULT_HALF_WIDTH * w["radius"]


def in_wheel_box(lo, hi, w):
    """The axis-aligned box of a piece fits inside the wheel's cylinder box (tyre, rim, disc, caliper)."""
    ai, rad = _frame(w)
    c, r = w["center"], w["radius"]
    hw = half_width(w) + AXIAL_MARGIN * r
    return (lo[ai] >= c[ai] - hw and hi[ai] <= c[ai] + hw
            and all(lo[k] >= c[k] - RADIAL_MAX * r and hi[k] <= c[k] + RADIAL_MAX * r for k in rad))


def island_spins(lo, hi, centroid, w):
    ai, rad = _frame(w)
    off = math.hypot(*(centroid[k] - w["center"][k] for k in rad))
    return in_wheel_box(lo, hi, w) and off <= SPIN_AXIS_TOL * w["radius"]


def tyre_weight(p, w):
    """1 when p is in the tyre band (rubber ring within the tyre's width), else 0."""
    ai, rad = _frame(w)
    r = w["radius"]
    rho = math.hypot(*(p[k] - w["center"][k] for k in rad))
    inner = (w.get("tyreBand") or DEFAULT_BAND)[0]
    return int((inner - BAND_SLACK) * r <= rho <= RADIAL_MAX * r
               and abs(p[ai] - w["center"][ai]) <= half_width(w) + AXIAL_MARGIN * r)


def tyre_mask(points, w):
    """Vectorised tyre_weight for an (n, 3) numpy array (Blender side and host tests)."""
    import numpy as np
    ai, rad = _frame(w)
    r = w["radius"]
    c = np.asarray(w["center"], dtype=np.float64)
    rho = np.hypot(points[:, rad[0]] - c[rad[0]], points[:, rad[1]] - c[rad[1]])
    inner = (w.get("tyreBand") or DEFAULT_BAND)[0]
    return ((rho >= (inner - BAND_SLACK) * r) & (rho <= RADIAL_MAX * r)
            & (np.abs(points[:, ai] - c[ai]) <= half_width(w) + AXIAL_MARGIN * r))
```

`engine/ingest/measure.py`:

1. `Sample = namedtuple("Sample", "p n w cls gloss textured curv open obj island", defaults=(1.0, -1, -1))`
   (keep `open`: `detail_points` filters on it). Construct samples with keywords after `curv`.
2. `_samples`: accept 9-, 10- or 12-wide rows:

```python
    for row in raw.get("samples", []):
        x, y, z, nx, ny, nz, w, mi, curv = row[:9]
        opn = row[9] if len(row) > 9 else 1.0
        obj, isl = (int(row[10]), int(row[11])) if len(row) >= 12 else (-1, -1)
        m = mats[int(mi)] if 0 <= int(mi) < len(mats) else {}
        out.append(Sample(tuple(place([x, y, z])), tuple(_unit([nx, ny, nz])), w * f * f,
                          material_class(m), is_gloss(m), bool(m.get("textured")), curv,
                          open=opn, obj=obj, island=isl))
```
3. Islands in placed coordinates (add after `_parts`):

```python
def _islands(raw_islands, place, f):
    return [{"key": (i["obj"], i["id"]), "n": i["n"], "lo": place(i["lo"]), "hi": place(i["hi"]),
             "centroid": place(i["centroid"])} for i in raw_islands]
```
4. Wheel extras and vehicle facts (after `wheels`):

```python
RUBBER = ("fabric", "matte")   # rough non-metal, non-glass: tyres (material_class, never names)


def wheel_extras(ws, samples, islands, bmin, bmax):
    """Adds width, tyreBand, contact and separable to each wheel in place (METHODS §3)."""
    from engine.physics.wheel_mask import island_spins
    for w in ws:
        c, r = w["center"], w["radius"]
        ai = max(range(3), key=lambda k: abs(w["axis"][k]))
        rad = [k for k in range(3) if k != ai]
        rub = []
        for s in samples:
            rho = math.hypot(*(s.p[k] - c[k] for k in rad))
            ax = s.p[ai] - c[ai]
            if abs(ax) <= 0.6 * r and 0.4 * r <= rho <= 1.02 * r and s.cls in RUBBER and not s.gloss:
                rub.append((ax, rho))
        if len(rub) >= 10:
            axs, rhos = sorted(a for a, _ in rub), sorted(p for _, p in rub)
            w["width"] = round(_pct(axs, 0.95) - _pct(axs, 0.05), 5)
            w["tyreBand"] = [round(_pct(rhos, 0.05) / r, 3), 1.0]
        w["contact"] = _r([c[0], c[1], 0.0])
        spin = [i for i in islands if island_spins(i["lo"], i["hi"], i["centroid"], w)]
        reach = max((max(i["hi"][k] - c[k], c[k] - i["lo"][k]) for i in spin for k in rad), default=0.0)
        w["separable"] = bool(spin) and reach >= 0.9 * r
    return ws


VEHICLE_TOY_M = 1.0        # shorter than this: a toy; no suspension dynamics (METHODS VD-01 scale note)
OFFROAD_CLEARANCE = 0.9    # ride height >= 0.9 r (eng)
SPORT_HEIGHT_RATIO = 0.32  # height / length <= 0.32 (eng; sports_car 0.305)


def vehicle_facts(ws, samples, bmin, bmax):
    """Vehicle hints for suspension params (never a gate). {} when there are no wheels."""
    from engine.physics.wheel_mask import in_wheel_box
    if not ws:
        return {}
    la, wa = _LONG_AXIS(bmin, bmax)
    L, W, H = bmax[la] - bmin[la], bmax[wa] - bmin[wa], bmax[2] - bmin[2]
    fwd = [0.0, 0.0, 0.0]
    fwd[la] = 1.0
    ls, wsd = [w["center"][la] for w in ws], [w["center"][wa] for w in ws]
    r = sorted(w["radius"] for w in ws)[len(ws) // 2]
    body = [s for s in samples if abs(s.p[wa]) <= 0.3 * W
            and not any(in_wheel_box(s.p, s.p, w) for w in ws)]
    ride = min((s.p[2] for s in body), default=0.0)
    cls = ("toy" if L < VEHICLE_TOY_M else "offroad" if ride >= OFFROAD_CLEARANCE * r
           else "sport" if H / L <= SPORT_HEIGHT_RATIO else "comfort")
    return {"forwardAxis": fwd, "wheelbaseM": round(max(ls) - min(ls), 5), "trackM": round(max(wsd) - min(wsd), 5),
            "rideHeightM": round(ride, 5), "bodySeparable": all(w.get("separable") for w in ws), "vehicleClass": cls}
```
5. In `build_profile`: compute `isl = _islands(raw.get("islands", []), place, f)`, then
   `ws = wheel_extras(wheels(samples, bmin, bmax), samples, isl, bmin, bmax)` and pass `wheels=ws`,
   `vehicle=vehicle_facts(ws, samples, bmin, bmax)`.

`forwardAxis` is the long axis with a **+** sign: GLBs carry no trustworthy "front". Nothing in this
phase needs the sign (settle pitch is symmetric about the wheelbase centre; wheel angle comes from the
actual displacement). Phase 5 `drive` must derive heading from its own path (hand-off H5).

- [ ] **Step 4: Run, expect PASS** — the two test files, then the fast loop.

- [ ] **Step 5: Commit**

```bash
git add engine/physics/__init__.py engine/physics/wheel_mask.py engine/ingest/measure.py engine/tests/test_physics_wheel_mask.py engine/tests/test_measure.py
git commit -m "feat(ingest): tyre band, wheel width, contact point, separable wheels, vehicle hints"
```

---

### Task 6: Ground contacts, soft parts, dangling parts

**Files:**
- Modify: `engine/ingest/measure.py`
- Test: `engine/tests/test_measure.py`

- [ ] **Step 1: Write the failing tests** — append to `engine/tests/test_measure.py`:

```python
from engine.ingest.measure import dangling_parts, ground_contacts, soft_parts


def _s(p, cls="matte", obj=0, island=0):
    return Sample(tuple(p), (0.0, 0.0, 1.0), 1e-4, cls, False, False, 0.0, obj=obj, island=island)


def test_ground_contacts_are_the_patches_at_z0():
    feet = [_s((x / 100 + dx, y / 100 + dy, 0.0)) for dx, dy in ((-0.4, -0.4), (0.4, -0.4), (0.4, 0.4), (-0.4, 0.4))
            for x in range(3) for y in range(3)]
    top = [_s((0, 0, 0.5))] * 20
    got = ground_contacts(feet + top, [-0.5, -0.5, 0.0], [0.5, 0.5, 0.8])
    assert len(got) == 4 and all(g["center"][2] == 0.0 for g in got)
    assert sum(g["share"] for g in got) == pytest.approx(1.0)


def test_soft_parts_high_only_for_small_unrigged_wheel_less_fabric():
    ss = [_s((0, 0, z / 100), "fabric", obj=0) for z in range(30)]
    parts = {0: 0}
    hi = soft_parts(ss, parts, "hand", has_wheels=False, rigged=False, H=0.3)
    assert hi == [{"part": 0, "share": 1.0, "touchesGround": True, "confidence": "high"}]
    assert soft_parts(ss, parts, "vehicle", has_wheels=True, rigged=False, H=0.3)[0]["confidence"] == "low"
    assert soft_parts(ss, parts, "furniture", has_wheels=False, rigged=True, H=0.3)[0]["confidence"] == "low"
    assert soft_parts([_s((0, 0, z / 100), "metal") for z in range(30)], parts, "hand", False, False, 0.3) == []


def test_a_strap_hanging_from_one_end_is_dangling():
    box = [_s((x / 100, y / 100, 0.30 + z / 100), obj=0, island=0) for x in range(0, 11) for y in range(-5, 6) for z in range(0, 13)]
    strap = [_s((0.104, 0.0, 0.27 + z / 1000), obj=1, island=0) for z in range(0, 151, 5)]
    isl = [{"key": (1, 0), "n": 24, "lo": [0.102, -0.006, 0.27], "hi": [0.106, 0.006, 0.42], "centroid": [0.104, 0, 0.345]},
           {"key": (0, 0), "n": 8, "lo": [0.0, -0.05, 0.30], "hi": [0.10, 0.05, 0.42], "centroid": [0.05, 0, 0.36]}]
    got = dangling_parts(box + strap, isl, longest=0.42, H=0.42)
    assert len(got) == 1 and got[0]["confidence"] == "high"
    assert got[0]["pivot"][2] > got[0]["tip"][2] and got[0]["lengthM"] == pytest.approx(0.15, abs=0.01)


def test_a_rail_attached_at_both_ends_or_lying_on_the_ground_is_not_high():
    rail = [_s((0.0, y / 100, 0.001), obj=1) for y in range(0, 31)]
    ends = [_s((0.0, -0.005, 0.001), obj=0), _s((0.0, 0.305, 0.001), obj=2)]
    isl = [{"key": (1, 0), "n": 31, "lo": [-0.002, 0.0, 0.0], "hi": [0.002, 0.30, 0.002], "centroid": [0, 0.15, 0.001]}]
    assert all(d["confidence"] != "high" for d in dangling_parts(rail + ends, isl, longest=0.4, H=0.3))
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_measure.py -q`.

- [ ] **Step 3: Implement** — add to `engine/ingest/measure.py`:

```python
def ground_contacts(samples, bmin, bmax, max_n=16):
    """Where the subject touches z = 0: patches of samples within 2% of the height (same test wheels() uses)."""
    H = bmax[2] - bmin[2]
    cell = 0.1 * max(min(bmax[0] - bmin[0], bmax[1] - bmin[1]), 1e-9)
    low = [(s.p[0], s.p[1]) for s in samples if s.p[2] <= 0.02 * H]
    comps = [c for c in _components(low, cell) if len(c) >= 3]
    total = sum(len(c) for c in comps) or 1
    out = []
    for c in sorted(comps, key=len, reverse=True)[:max_n]:
        cx, cy = sum(p[0] for p in c) / len(c), sum(p[1] for p in c) / len(c)
        out.append({"center": _r([cx, cy, 0.0]), "radius": round(max(math.dist(p, (cx, cy)) for p in c), 5),
                    "share": round(len(c) / total, 4)})
    return out


SOFT_CLASSES = ("fabric", "skin")
SOFT_MIN_SHARE, SOFT_HIGH_SHARE = 0.5, 0.8   # (eng) part sample share in a soft class


def soft_parts(samples, obj_to_part, size_class, has_wheels, rigged, H):
    """Parts that read soft. 'fabric' is just rough non-metal (tyres and matte plastic read fabric too), so
    confidence is high only for hand- or furniture-sized, unrigged, wheel-less subjects."""
    by = {}
    for s in samples:
        if s.obj in obj_to_part:
            by.setdefault(obj_to_part[s.obj], []).append(s)
    eligible = size_class in ("hand", "furniture") and not has_wheels and not rigged
    out = []
    for pi in sorted(by):
        ss = by[pi]
        if len(ss) < 20:
            continue
        share = sum(1 for s in ss if s.cls in SOFT_CLASSES) / len(ss)
        if share < SOFT_MIN_SHARE:
            continue
        out.append({"part": pi, "share": round(share, 4), "touchesGround": min(s.p[2] for s in ss) <= 0.02 * H,
                    "confidence": "high" if eligible and share >= SOFT_HIGH_SHARE else "low"})
    return out


DANGLE_MIN_FRAC = 0.08    # a dangling piece is at least 8% of the subject's longest side (eng)
DANGLE_ASPECT = 4.0       # and at least 4x longer than its second extent (eng)
ATTACH_FRAC = 0.02        # "touching": another piece's sample within 2% of the longest side (eng)


def dangling_parts(samples, islands, longest, H, max_n=8, max_candidates=32):
    """Thin pieces attached at exactly one end whose free end hangs below the pivot, off the ground."""
    cands = []
    for i in islands:
        ext = [h - l for l, h in zip(i["lo"], i["hi"])]
        order = sorted(range(3), key=lambda k: ext[k])
        L, second = ext[order[2]], ext[order[1]]
        if L >= DANGLE_MIN_FRAC * longest and L >= DANGLE_ASPECT * max(second, 1e-9):
            cands.append((L, i, order[2], second))
    cands = sorted(cands, key=lambda c: -c[0])[:max_candidates]
    near_r = ATTACH_FRAC * longest
    out = []
    for L, isl, ax, second in cands:
        own = [s for s in samples if (s.obj, s.island) == isl["key"]]
        if len(own) < 5:
            continue
        others = [s for s in samples if (s.obj, s.island) != isl["key"]]
        # Ends on the box's long axis, centred in its two short extents (surface samples sit off-axis;
        # the compiler's capsule test needs the true axis).
        c = [(l + h) / 2 for l, h in zip(isl["lo"], isl["hi"])]
        e0, e1 = list(c), list(c)
        e0[ax], e1[ax] = isl["lo"][ax], isl["hi"][ax]
        a0 = any(math.dist(s.p, e0) <= near_r for s in others)
        a1 = any(math.dist(s.p, e1) <= near_r for s in others)
        if a0 == a1:
            continue  # attached at both ends (a rail, a handle) or floating free
        pivot, tip = (e0, e1) if a0 else (e1, e0)
        hangs = tip[2] < pivot[2] - 0.25 * L
        off_ground = tip[2] > 0.02 * H
        short = sorted(h - l for l, h in zip(isl["lo"], isl["hi"]))[:2]
        out.append({"pivot": _r(pivot), "tip": _r(tip), "radius": round(0.5 * math.hypot(*short), 5),
                    "lengthM": round(L, 5), "confidence": "high" if hangs and off_ground else "low"})
    return out[:max_n]
```

In `build_profile`: build `obj_to_part` from the raw parts (the same ordering `_parts` uses:
`rows = sorted(parts, key=lambda p: -p.get("polys", 0))[:64]` → `{p["obj"]: i for i, p in enumerate(rows) if "obj" in p}`),
and pass:

```python
        groundContacts=ground_contacts(samples, bmin, bmax),
        softParts=soft_parts(samples, obj_to_part, size_class(max(size)), bool(ws), raw.get("rigged", False), bmax[2] - bmin[2]),
        danglingParts=dangling_parts(samples, isl, max(size), bmax[2] - bmin[2]),
```

`dangling_parts` is O(candidates × samples); with ≤ 32 candidates and ≤ 20 000 samples it stays well
under a second.

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests/test_measure.py -q`, then the fast loop.

- [ ] **Step 5: Commit**

```bash
git add engine/ingest/measure.py engine/tests/test_measure.py
git commit -m "feat(ingest): ground contacts, soft parts and dangling parts with confidence"
```

---

### Task 7: End-to-end ingest on the fixtures, then regenerate the nine reference profiles

**Owner OK first:** nine headless Blender ingest launches (no rendering, about 1–3 minutes total;
the 46 MB `sports_car` is the slowest). Tell the owner before Step 4 and wait for "ok" (phase-3 O4
style). If phase-3 Task 28 (`animationClips`) has not landed yet, still regenerate now; whichever
ingest change lands later regenerates again.

**Files:**
- Modify: `engine/tests/test_ingest_realism_blender.py`, `engine/tests/test_real_profiles.py`,
  `engine/tests/fixtures/profiles/*.json` (regenerated)

- [ ] **Step 1: Write the failing tests.** Append to `engine/tests/test_ingest_realism_blender.py`:

```python
from engine.ingest.run import ingest


def test_wheeled_fixture_yields_four_separable_tyres_and_a_sport_body(tmp_path):
    p = ingest(make_glb("wheeled", tmp_path / "w.glb"), workdir=tmp_path / "x")
    assert len(p.wheels) == 4 and all(w["confidence"] == "high" for w in p.wheels)
    for w in p.wheels:
        assert w["separable"] is True and 0.5 <= w["tyreBand"][0] <= 0.7 and 0.08 <= w["width"] <= 0.16
    assert p.vehicle["bodySeparable"] is True and p.vehicle["vehicleClass"] == "sport"
    assert p.softParts == [] or all(s["confidence"] == "low" for s in p.softParts)


def test_strap_fixture_yields_one_high_confidence_dangling_part(tmp_path):
    p = ingest(make_glb("strap", tmp_path / "s.glb"), workdir=tmp_path / "x")
    high = [d for d in p.danglingParts if d["confidence"] == "high"]
    assert len(high) == 1 and high[0]["pivot"][2] > high[0]["tip"][2]


def test_plush_fixture_is_soft_and_touches_the_ground(tmp_path):
    p = ingest(make_glb("plush", tmp_path / "p.glb"), workdir=tmp_path / "x")
    assert [s["confidence"] for s in p.softParts] == ["high"] and p.softParts[0]["touchesGround"]
    assert len(p.groundContacts) == 1 and p.wheels == []
```

Append to `engine/tests/test_real_profiles.py`:

```python
def _prof(name):
    return SubjectProfile.from_dict(json.loads((FIX / "profiles" / f"{name}.json").read_text(encoding="utf-8")))


def test_sports_car_carries_the_realism_facts():
    p = _prof("sports_car")
    assert len(p.wheels) == 4 and all(w["confidence"] == "high" for w in p.wheels)
    for w in p.wheels:
        assert 0.15 <= w["width"] <= 0.40, w           # a GT3 RS tyre is 0.275-0.335 m wide
        assert 0.5 <= w["tyreBand"][0] <= 0.8, w      # 20-21 in rims on ~0.35 m tyres
        assert w["contact"][2] == 0.0
    assert p.vehicle["vehicleClass"] == "sport"
    assert 2.3 <= p.vehicle["wheelbaseM"] <= 2.7      # 992 GT3 RS: 2.457 m


@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.stem)
def test_every_profile_has_ground_contacts(path):
    p = SubjectProfile.from_dict(json.loads(path.read_text(encoding="utf-8")))
    assert p.groundContacts and all(g["center"][2] == 0.0 for g in p.groundContacts)


def test_only_small_unrigged_fabric_subjects_are_soft():
    high = {path.stem for path in PROFILES
            if any(s["confidence"] == "high" for s in _prof(path.stem).softParts)}
    assert high <= {"sneaker"}, high   # measured 2026-09-xx: fill in the observed set in Step 5
```

- [ ] **Step 2: Run the fixture tests, expect FAIL until Tasks 4–6 are in; then PASS** —
`py -m pytest engine/tests/test_ingest_realism_blender.py -q -m blender`. If a fixture assertion fails,
print the profile (`p.to_dict()` minus `surfaceSamples`) and fix the **measurement**, not the fixture,
unless the fixture geometry is wrong (re-check the Task 4 fixture comments against the numbers).

- [ ] **Step 3: Ask the owner** (see the header of this task).

- [ ] **Step 4: Regenerate the nine profiles** exactly as phase-2 Task 30 did, one launch per model:

```
py -m engine ingest assets-in/models/camera_01/camera_01.glb --out engine/tests/fixtures/profiles/camera_01.json
```
(repeat for `cesium_man`, `flighthelmet`, `mid_century_lounge_chair`, `pocket_watch`, `sneaker`,
`sports_car`, `toycar`, `vintage_microscope`). `sports_car.glb` is local-only (never committed); its
**profile** is committed like the others (phase-2 precedent).

- [ ] **Step 5: Run and pin.** `py -m pytest engine/tests/test_real_profiles.py -q`. Then record what was
measured (a reader must be able to reproduce it): for each model, the `softParts` high set, the
`danglingParts` high set, `vehicle.vehicleClass`, and each wheel's `width`/`tyreBand`. Replace the
`high <= {"sneaker"}` assertion with the observed set as an equality **only if** every member is a
plausible soft subject; if a hard subject (toycar, microscope, helmet) reads high, that is a
measurement bug: tighten `SOFT_HIGH_SHARE` or the eligibility rule in Task 6, re-run, and note the
change in the calibration register. Add a test that no reference model has a high-confidence dangling
part unless one was observed and eyeballed in the GLB (a false dangling part would make a rigid part
sway). Also run `py -m pytest engine/tests/test_real_profiles.py engine/tests/test_checker.py -q` —
the default script must still frame every model.

- [ ] **Step 6: Commit**

```bash
git add engine/tests/test_ingest_realism_blender.py engine/tests/test_real_profiles.py engine/tests/fixtures/profiles
git commit -m "test(ingest): realism facts end to end on fixtures; regenerate the nine reference profiles"
```

---
## Chunk 2: Pure physics maths and the resolver

Every number that shapes a look is here, in stdlib Python, with a test. Blender blocks call these
functions (Python keyframes) or mirror them in node trees (a Blender test proves each mirror).

### Task 8: Ground contact and tyre maths

**Files:**
- Create: `engine/physics/contact.py`, `engine/physics/tyre.py`, `engine/tests/test_physics_contact_tyre.py`

- [ ] **Step 1: Write the failing tests** — `engine/tests/test_physics_contact_tyre.py`:

```python
import pytest

from engine.physics import contact, tyre


def test_sink_depends_on_ground_type_and_never_swallows_a_small_subject():
    assert contact.sink_m("studio", 1.4) == 0.0 and contact.sink_m("asphalt", 1.4) == 0.0
    assert contact.sink_m("grass", 1.4) == pytest.approx(0.012)
    assert contact.sink_m("snow", 0.05) == pytest.approx(0.005)   # capped at 10% of a 5 cm subject
    with pytest.raises(KeyError):
        contact.sink_m("lava", 1.0)


def test_ao_distance_scales_with_height():
    assert contact.ao_distance(1.4) == pytest.approx(0.07) and contact.ao_distance(0.0) > 0


def test_grounded_window():
    assert contact.grounded(0.0, 0.0) and contact.grounded(-0.012, 0.012)
    assert not contact.grounded(0.004, 0.0)            # a 4 mm gap: floating
    assert not contact.grounded(-0.02, 0.012)          # sunk deeper than the ground allows


def test_deflection_from_patch_length_is_chord_geometry():
    d = tyre.deflection(0.33, 0.45)                     # METHODS CD-02: r 0.33 m -> d 5-12 mm
    assert d == pytest.approx(0.45 ** 2 * 0.33 / 8) and 0.005 <= d <= 0.012
    assert tyre.patch_length(0.33, d) == pytest.approx(0.45 * 0.33, rel=0.02)


def test_deform_clamps_to_the_ground_and_bulges_the_sidewall():
    r, d, hw = 0.35, tyre.deflection(0.35, 0.45), 0.14
    z, ax = tyre.deform(-0.004, 0.14, ground=0.0, d=d, radius=r, half_width=hw, bulge_frac=0.25)
    assert z == 0.0 and ax == pytest.approx(0.14 + 0.25 * d)          # full bulge at the patch, outer wall
    z, ax = tyre.deform(-0.004, -0.14, ground=0.0, d=d, radius=r, half_width=hw, bulge_frac=0.25)
    assert ax == pytest.approx(-0.14 - 0.25 * d)                       # inner wall bulges inward
    assert tyre.deform(0.3 * r, 0.14, 0.0, d, r, hw, 0.25) == (0.3 * r, 0.14)   # no bulge 0.3 r up
    z, ax = tyre.deform(0.0, 0.0, 0.0, d, r, hw, 0.25)
    assert (z, ax) == (0.0, 0.0)                                       # the tread centre does not move sideways
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_physics_contact_tyre.py -q`.

- [ ] **Step 3: Implement.**

`engine/physics/contact.py`:

```python
"""Contact with the ground (TAXONOMY CD-01, CD-07, CD-10; METHODS §2.1). Placed metres."""

# How far a subject settles into the ground, by ground type (eng; METHODS CD-07 "5-20 mm" into cover,
# CD-10 "5-10 mm" into rug pile). Hard floors: 0. Calibrate on golden renders of each world.
SINK_MM = {"studio": 0.0, "interior_floor": 0.0, "asphalt": 0.0, "water": 0.0, "rug": 7.0, "dirt": 5.0,
           "gravel": 8.0, "sand": 10.0, "grass": 12.0, "snow": 15.0}
MAX_SINK_FRAC = 0.1      # never sink more than 10% of the subject's height (a 5 cm lipstick on snow)
AO_DIST_FRAC = 0.05      # contact-occlusion reach, x subject height (eng; TAXONOMY CD-01 falloff 2-10%)
GROUND_TOL_M = 0.001     # a lowest point more than 1 mm above the ground is a visible gap


def sink_m(ground_type, subject_height):
    return min(SINK_MM[ground_type] / 1000.0, MAX_SINK_FRAC * subject_height)


def ao_distance(subject_height):
    return max(1e-4, AO_DIST_FRAC * subject_height)


def grounded(min_z, sink, tol=GROUND_TOL_M):
    """The lowest evaluated point sits on the ground (or in it by at most the ground's sink)."""
    return -sink - tol <= min_z <= tol
```

`engine/physics/tyre.py`:

```python
"""Loaded tyre: a flat contact patch and a sidewall bulge (TAXONOMY CD-02; METHODS §2.1 M-GND).

The whole vehicle drops by the tyre deflection d; tyre-band points below the ground are clamped onto
it (the flat patch), and points low on the sidewall move out along the axle. Chord geometry: a
circle of radius r cut d below its lowest point leaves a flat chord L = 2 sqrt(2 r d - d^2), so
d = L^2 / (8 r) for small d. Car tyres: L 0.12-0.18 m, d 2-3.5% of r (METHODS)."""
import math

BULGE_FALLOFF = 0.3   # the bulge fades to zero 0.3 r above the patch (eng; METHODS CD-02)


def deflection(radius, patch_len_frac):
    length = patch_len_frac * radius
    return length * length / (8.0 * radius)


def patch_length(radius, d):
    return 2.0 * math.sqrt(max(0.0, 2.0 * radius * d - d * d))


def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def deform(z, axial, ground, d, radius, half_width, bulge_frac):
    """(z', axial') of one tyre-band point in placed space. axial = signed offset from the tyre's
    mid-plane along the axle. The Blender deformer (tyre_contact/build.py) is this function in nodes."""
    z2 = max(z, ground)
    k = bulge_frac * d * (1.0 - smoothstep(0.0, BULGE_FALLOFF * radius, z2 - ground))
    side = min(1.0, abs(axial) / half_width) if half_width > 0 else 0.0
    return z2, (axial + math.copysign(k * side, axial)) if axial else axial
```

- [ ] **Step 4: Run, expect PASS**, then the fast loop.

- [ ] **Step 5: Commit**

```bash
git add engine/physics/contact.py engine/physics/tyre.py engine/tests/test_physics_contact_tyre.py
git commit -m "feat(physics): ground sink, contact occlusion reach, tyre deflection and bulge"
```

---

### Task 9: Motion events, settle, suspension, wheel angle

**Files:**
- Create: `engine/physics/events.py`, `engine/physics/settle.py`, `engine/physics/suspension.py`,
  `engine/physics/wheel_spin.py`, `engine/tests/test_physics_motion.py`

- [ ] **Step 1: Write the failing tests** — `engine/tests/test_physics_motion.py`:

```python
import math

import pytest

from engine.physics import events, settle, suspension, wheel_spin

FPS = 30


def _slide_then_stop():
    """1 m/s along +y for 30 frames, then parked (positions per frame, frame 1 first)."""
    return [(0.0, min(i, 30) / FPS, 0.0) for i in range(60)]


def test_a_stop_is_found_with_its_deceleration_and_direction():
    got = events.stops(_slide_then_stop(), FPS, longest=4.0)
    assert len(got) == 1 and got[0]["frame"] == 32
    assert got[0]["decelMs2"] == pytest.approx(3.75) and got[0]["dir"] == [0.0, 1.0]


def test_standing_still_or_creeping_is_not_a_stop():
    assert events.stops([(0.0, 0.0, 0.0)] * 60, FPS, 4.0) == []
    creep = [(0.0, i * 0.001, 0.0) for i in range(60)] + [(0.0, 0.059, 0.0)] * 10
    assert events.stops(creep, FPS, 4.0) == []          # 3 cm/s < 2% of 4 m per second


def test_a_drop_lands_once_with_its_impact_speed():
    h = 0.5
    t_land = math.sqrt(2 * h / 9.81)
    pos = [(0.0, 0.0, max(0.0, h - 0.5 * 9.81 * (i / FPS) ** 2)) for i in range(40)]
    got = events.landings(pos, FPS, longest=0.3)
    assert len(got) == 1 and abs((got[0]["frame"] - 1) / FPS - t_land) <= 1.5 / FPS
    assert 2.0 <= got[0]["impactMs"] <= 3.2               # sqrt(2 g h) = 3.13, sampled a frame early


def test_overshoot_peaks_at_amp_and_is_gone_after_settle():
    xs = [settle.overshoot(i / 1000, 0.05, 0.3) for i in range(1000)]
    assert max(xs) == pytest.approx(0.05, rel=0.01) and xs[0] == 0.0
    assert all(abs(x) <= 0.04 * 0.05 for x in xs[300:])


def test_squash_starts_squashed_and_preserves_volume():
    assert settle.squash_z(0.0, 0.92, 0.3) == pytest.approx(0.92)
    assert settle.squash_z(0.5, 0.92, 0.3) == pytest.approx(1.0, abs=0.004)
    sz = settle.squash_z(0.0, 0.92, 0.3)
    assert sz * settle.squash_xy(sz) ** 2 == pytest.approx(1.0)
    assert settle.squash_z(0.0, 1.0, 0.3) == 1.0            # rigid subjects never squash


def test_suspension_class_params_and_settle_after_a_stop():
    assert suspension.ride_hz("sport") == 1.9 and suspension.ride_hz("unknown") == 1.3
    assert suspension.static_sag(0.35, 0.015) == pytest.approx(0.00525)
    p0 = suspension.pitch_after_stop(0.0, 6.0, 1.9, 0.4)
    assert p0 == pytest.approx(math.radians(6.0 / 9.81))
    assert abs(suspension.pitch_after_stop(1.5, 6.0, 1.9, 0.4)) < 0.01 * p0   # 1-2 bounces, then still
    assert suspension.heave_after_landing(0.0, 3.0, 1.9, 0.4, 0.05) == 0.0
    assert min(suspension.heave_after_landing(i / 100, 3.0, 1.9, 0.4, 0.05) for i in range(100)) >= -0.05


def test_wheel_angle_rolls_without_slip_about_the_axle():
    pos = [(0.0, i / 30, 0.0) for i in range(31)]            # 1 m along +y
    a = wheel_spin.wheel_angles(pos, [0.0] * 31, (1.0, 0.0, 0.0), 0.5)
    assert a[-1] == pytest.approx(-2.0)                      # right-hand rule about +x: rolling forward is negative
    side = [(i / 30, 0.0, 0.0) for i in range(31)]           # sliding along the axle: no roll
    assert wheel_spin.wheel_angles(side, [0.0] * 31, (1.0, 0.0, 0.0), 0.5)[-1] == pytest.approx(0.0)
    assert wheel_spin.slip(a, pos, 0.5) == pytest.approx(0.0, abs=1e-9)
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_physics_motion.py -q`.

- [ ] **Step 3: Implement.**

`engine/physics/events.py`:

```python
"""Stops and landings read from the subject's motion track (the valora_motion empty, one position per
frame, frame 1 first). Realism blocks attach settles to these events; the motion block never has to
announce them (phase-5 drive/drop/roll plug in unchanged)."""
import math

MOVE_FRAC = 0.02        # moving = faster than 2% of the subject's length per second (eng)
MIN_MOVE_S = 0.2        # a stop needs at least 0.2 s of movement before it (eng)
DECEL_WINDOW_S = 0.25   # deceleration measured over the last 0.25 s before the stop (eng)
REST_Z_FRAC = 0.01      # "on the ground" = within 1% of the longest side of z = 0


def speeds(pos, fps):
    return [0.0] + [math.dist(pos[i], pos[i - 1]) * fps for i in range(1, len(pos))]


def stops(pos, fps, longest):
    thr, v, out, run = MOVE_FRAC * longest, speeds(pos, fps), [], 0
    k = max(1, round(DECEL_WINDOW_S * fps))
    for i in range(1, len(v)):
        if v[i] > thr:
            run += 1
            continue
        if run >= MIN_MOVE_S * fps:
            j = max(0, i - k)
            decel = (max(v[j:i]) - v[i]) / ((i - j) / fps)
            dx, dy = pos[i - 1][0] - pos[i - 2][0], pos[i - 1][1] - pos[i - 2][1]
            n = math.hypot(dx, dy) or 1.0
            out.append({"frame": i + 1, "decelMs2": round(decel, 4), "dir": [round(dx / n, 6), round(dy / n, 6)]})
        run = 0
    return out


def landings(pos, fps, longest):
    """The first frame at rest after falling. The impact speed is the fastest descent over the 3 frames
    before it (the last step before rest is clamped at the ground and reads slow)."""
    thr, out = MOVE_FRAC * longest, []
    vz = [0.0] + [(pos[i][2] - pos[i - 1][2]) * fps for i in range(1, len(pos))]
    for i in range(2, len(pos)):
        if vz[i - 1] < -thr and abs(vz[i]) <= thr and pos[i][2] <= REST_Z_FRAC * longest:
            out.append({"frame": i + 1, "impactMs": round(-min(vz[max(1, i - 3):i]), 4)})
    return out
```

`engine/physics/settle.py`:

```python
"""Overshoot-and-settle after a stop, squash-and-recover after a landing (TAXONOMY SF-05, RB-01, CD-04;
products.md P-M01 "2 f damped landing shake"). A damped oscillator whose 2% settling time is settle_s."""
import math

ZETA = 0.5   # (eng) one visible overshoot, then still


def _w(settle_s, zeta):
    return 4.0 / (zeta * settle_s)


def _peak(zeta):
    """Peak of e^(-zeta w t) sin(w_d t) (independent of w)."""
    s = math.sqrt(1.0 - zeta * zeta)
    phase = math.atan2(s, zeta)
    return math.exp(-zeta * phase / s) * math.sin(phase)


def overshoot(t, amp, settle_s, zeta=ZETA):
    """Displacement past the rest pose after a stop: 0 at t = 0, one overshoot of `amp`, still by settle_s."""
    if t <= 0:
        return 0.0
    w = _w(settle_s, zeta)
    wd = w * math.sqrt(1.0 - zeta * zeta)
    return amp * math.exp(-zeta * w * t) * math.sin(wd * t) / _peak(zeta)


def squash_z(t, squash, settle_s, zeta=ZETA):
    """Scale along the contact normal after a landing: `squash` at impact, one small rebound, then 1."""
    if squash >= 1.0 or t < 0:
        return 1.0
    w = _w(settle_s, zeta)
    wd = w * math.sqrt(1.0 - zeta * zeta)
    return 1.0 - (1.0 - squash) * math.exp(-zeta * w * t) * math.cos(wd * t)


def squash_xy(sz):
    """Sideways scale that keeps the volume: sx * sy * sz = 1."""
    return 1.0 / math.sqrt(sz)
```

`engine/physics/suspension.py`:

```python
"""Body on springs (TAXONOMY VD-01; METHODS §2.2): a static sag, and after a stop or a landing one or
two damped bounces at the ride frequency. Ride frequency by class: 1.2-1.6 Hz passenger, 1.8-2.0 Hz
sporty, < 0.8 Hz luxury (METHODS VD-01)."""
import math

RIDE_HZ = {"sport": 1.9, "comfort": 1.3, "offroad": 1.1, "toy": 1.3}   # (eng) mid-band per class
PITCH_DEG_PER_G = 1.0   # (eng) METHODS VD-01: 0.5-1.5 deg of pitch per g of braking
G = 9.81


def ride_hz(vehicle_class):
    return RIDE_HZ.get(vehicle_class, RIDE_HZ["comfort"])


def static_sag(radius, sag_frac_r):
    return sag_frac_r * radius


def _wd(hz, zeta):
    w = 2.0 * math.pi * hz
    return w, w * math.sqrt(1.0 - zeta * zeta)


def pitch_after_stop(t, decel_ms2, hz, zeta):
    """Body pitch (radians, nose down positive) from the moment the car stops: the braking dive is
    released into damped bounces."""
    if t < 0:
        return 0.0
    w, wd = _wd(hz, zeta)
    return math.radians(PITCH_DEG_PER_G * decel_ms2 / G) * math.exp(-zeta * w * t) * math.cos(wd * t)


def heave_after_landing(t, impact_ms, hz, zeta, max_m):
    """Body heave (metres, down negative) after the wheels touch down, capped at max_m travel."""
    if t <= 0:
        return 0.0
    w, wd = _wd(hz, zeta)
    return -min(max_m, impact_ms / w) * math.exp(-zeta * w * t) * math.sin(wd * t)
```

`engine/physics/wheel_spin.py`:

```python
"""Wheel angle from the subject's path: rolling without slip (TAXONOMY VD-02). The angular velocity of
a wheel rolling with velocity v on a ground with normal z is omega = (z x v) / r; its component along
the axle is the spin. The Blender wheel_roll block rotates each spinning island about its axle by
this angle (right-hand rule), so the contact point stays still on the ground."""
import math


def wheel_angles(pos, yaws, axle, radius):
    """Cumulative angle (radians) per frame. pos: subject positions per frame (world); yaws: the motion
    empty's yaw per frame (radians); axle: the wheel's axle in placed space."""
    out = [0.0]
    for i in range(1, len(pos)):
        dx, dy = pos[i][0] - pos[i - 1][0], pos[i][1] - pos[i - 1][1]
        c, s = math.cos(yaws[i]), math.sin(yaws[i])
        ax, ay = c * axle[0] - s * axle[1], s * axle[0] + c * axle[1]
        out.append(out[-1] + (-dy * ax + dx * ay) / radius)
    return out


def slip(angles, pos, radius):
    """|rolled distance - travelled distance| / travelled (0 = no slip). Straight paths only."""
    path = sum(math.dist(pos[i], pos[i - 1]) for i in range(1, len(pos)))
    return abs(abs(angles[-1] - angles[0]) * radius - path) / path if path else 0.0
```

- [ ] **Step 4: Run, expect PASS**, then the fast loop.

- [ ] **Step 5: Commit**

```bash
git add engine/physics/events.py engine/physics/settle.py engine/physics/suspension.py engine/physics/wheel_spin.py engine/tests/test_physics_motion.py
git commit -m "feat(physics): stops and landings from the motion track, settle, squash, suspension, wheel angle"
```

---

### Task 10: Wind field and sway maths

**Files:**
- Create: `engine/physics/wind.py`, `engine/physics/sway.py`, `engine/tests/test_physics_wind.py`

- [ ] **Step 1: Write the failing tests** — `engine/tests/test_physics_wind.py`:

```python
import math

import pytest

from engine.physics import sway, wind


def test_direction_is_where_the_air_goes_world_azimuth_ccw_from_x():
    x, y, z = wind.vector(90.0, 4.0)
    assert (x, y, z) == pytest.approx((0.0, 4.0, 0.0), abs=1e-9)


@pytest.mark.parametrize("speed,force", [(0.0, 0), (0.8, 1), (3.0, 2), (7.0, 4), (13.0, 6), (20.0, 7)])
def test_beaufort(speed, force):
    assert wind.beaufort(speed) == force


def test_gust_envelope_and_calm():
    assert wind.envelope(4.0, 0.3) == pytest.approx((2.8, 5.2))
    assert wind.envelope(4.0, 1.0)[0] == 0.0
    assert wind.is_calm(0.2) and not wind.is_calm(0.8)


def test_bend_grows_with_speed_squared_and_is_capped():
    assert sway.bend_frac(0.0, 0.4) == 0.0
    assert sway.bend_frac(2.0, 0.4) == pytest.approx(0.02 * 4 * 0.68)
    assert sway.bend_frac(14.0, 0.0) == pytest.approx(math.tan(math.radians(25)))
    assert sway.tip_offset(0.5, 0.2, 2.0, 0.4) == pytest.approx(sway.bend_frac(2.0, 0.4) * 0.2 * 0.25)
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement.**

`engine/physics/wind.py`:

```python
"""One wind per clip (TAXONOMY WD-01; METHODS §2.9). Every wind-driven block reads the same field so
rain, smoke, leaves and foliage can never disagree. Direction: the world azimuth the air moves
TOWARD, degrees counter-clockwise from +x. Speed in m/s, Beaufort-anchored (0-14 m/s = force 0-6).

The Blender field (engine/blocks/field/wind/build.py) is mean * (1 + gustiness * g(p, t)) + turbulence
terms, with g a noise in [-1, 1] advected downwind; its speed stays inside envelope()."""
import math

BEAUFORT_UPPER = (0.5, 1.5, 3.3, 5.5, 7.9, 10.7, 13.8)   # upper speed of force 0..6 (m/s)
CALM_MS = 0.3            # below this nothing visibly moves (inside Beaufort 0) (eng)
GUST_WAVELENGTH_M = 12.0  # spatial size of a gust front (eng)
TURB_SCALE_M = 1.5       # spatial size of turbulent eddies (eng)


def vector(direction_deg, speed):
    a = math.radians(direction_deg)
    return (speed * math.cos(a), speed * math.sin(a), 0.0)


def beaufort(speed):
    return next((i for i, u in enumerate(BEAUFORT_UPPER) if speed <= u), len(BEAUFORT_UPPER))


def envelope(speed, gustiness):
    return max(0.0, speed * (1.0 - gustiness)), speed * (1.0 + gustiness)


def is_calm(speed):
    return speed < CALM_MS
```

`engine/physics/sway.py`:

```python
"""Wind bend of thin things: grass, stems, straps, cords (TAXONOMY HF-01..03, SC-08, SF-02/03;
METHODS §2.5, §2.11). Aerodynamic drag grows with v^2; a cantilever's tip moves most, its root not at
all (u^2 profile along the length). Stateless: the Blender deformer evaluates this per frame from the
wind field, so no frame depends on the one before."""
import math

MAX_BEND_DEG = 25.0   # nothing bends further than 25 deg in this phase (eng)
DRAG_K = 0.02         # tip displacement per metre of length per (m/s)^2 at stiffness 0 (eng)


def bend_frac(speed, stiffness):
    """Tip displacement / length for wind `speed` (m/s); stiffness 0 (thread) .. 1 (stiff stem)."""
    return min(math.tan(math.radians(MAX_BEND_DEG)), DRAG_K * speed * speed * (1.0 - 0.8 * stiffness))


def tip_offset(u, length, speed, stiffness):
    """Displacement (m) of a point at u in [0, 1] from root to tip."""
    return bend_frac(speed, stiffness) * length * u * u
```

- [ ] **Step 4: Run, expect PASS**, then the fast loop.

- [ ] **Step 5: Commit**

```bash
git add engine/physics/wind.py engine/physics/sway.py engine/tests/test_physics_wind.py
git commit -m "feat(physics): one wind field (vector, Beaufort, gust envelope) and wind bend"
```

---

### Task 11: The resolver — `appliesWhen`, confidence, auto params, the wind default; checker hook

The checker is the one place realism is decided. It overwrites `script["realism"]` and fills
`script["wind"]`, reporting each decision as an `info` issue. A hand-written or harness script may
**pin** realism params (for calibration); pins inside the declared range are kept, others ignored
with an `info` issue. The director never writes either field (phase-3 `OWNED` holds `realism`;
`wind` is not in its output schema).

**Files:**
- Create: `engine/physics/applies.py`, `engine/tests/test_physics_applies.py`
- Modify: `engine/checker.py` (two calls in `check`), `engine/script.py` (validate `wind`; realism
  entries of kind `realism` are shape-checked only), `engine/realism.py` (optional `script=`; realism
  entries carry `params: {}`), `engine/tests/test_realism.py` only if a Task 12a expectation names default
  params for a kind-`realism` fixture (its fixtures have `params: {}`, so none should)

- [ ] **Step 1: Write the failing tests** — `engine/tests/test_physics_applies.py`:

```python
import copy
import json
import shutil
from pathlib import Path

import pytest

from engine.catalog import BLOCKS_DIR, Catalog
from engine.checker import check
from engine.issues import errors
from engine.physics.applies import ORDER, facts, resolve_realism, resolve_wind
from engine.profile import SubjectProfile
from engine.realism import realism_defaults

FIX = Path(__file__).parent / "fixtures"


def _p(name):
    return SubjectProfile.from_dict(json.loads((FIX / "profiles" / f"{name}.json").read_text(encoding="utf-8")))


def _script():
    return json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))


def _manifest(bid, applies, params=None, auto=()):
    return {"id": bid, "kind": "realism", "description": "test", "alwaysOn": True, "directorSelectable": False,
            "appliesWhen": applies, "autoParams": list(auto), "params": params or {},
            "subjectSizeM": [0.01, 30.0], "aspects": ["9:16", "16:9", "1:1", "4:5"], "costWeight": 1.0,
            "tierMax": "T3", "tags": {"mood": [], "energy": [], "palette": []}}


def _cat(tmp_path, manifests):
    root = tmp_path / "blocks"
    shutil.copytree(BLOCKS_DIR, root, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.rmtree(root / "realism", ignore_errors=True)          # the test controls the realism set
    for m in manifests:
        d = root / "realism" / m["id"]
        d.mkdir(parents=True)
        (d / "block.json").write_text(json.dumps(m), encoding="utf-8")
    return Catalog.load(root)


SINK = {"sinkMm": {"type": "number", "min": 0, "max": 30, "default": 5}}
CONTACT = _manifest("contact_ground", {"placement": ["ground"]}, SINK, auto=["sinkMm"])
TYRE = _manifest("tyre_contact", {"placement": ["ground"], "profile": ["wheels", "tyreBand"]},
                 {"patchLenFrac": {"type": "number", "min": 0.3, "max": 0.6, "default": 0.45}})
ROLL = _manifest("wheel_roll", {"profile": ["wheelsSeparable"], "motion": ["translates"]})
DUST = _manifest("shaft_dust", {"effects": ["haze_volume"]})
GLASS = _manifest("glass_caustics", {"materials": {"glass": 0.05}})


def _ids(s):
    return [r["id"] for r in s.get("realism", [])]


def test_rules_pick_the_blocks_that_fit_each_subject(tmp_path):
    cat = _cat(tmp_path, [CONTACT, TYRE, ROLL, DUST, GLASS])
    car = check(_script(), _p("sports_car"), cat)
    watch = check(_script(), _p("pocket_watch"), cat)
    assert car.ok and watch.ok
    assert _ids(car.script) == ["contact_ground", "tyre_contact"]            # static: no roll; no haze; no glass
    assert _ids(watch.script) == ["contact_ground", "glass_caustics"]
    for r in (car, watch):
        assert all(i.severity == "info" for i in r.issues if i.code.startswith(("realism_", "wind_")))


def test_effects_gate(tmp_path):
    cat = _cat(tmp_path, [DUST])
    s = _script()
    s["effects"] = [{"id": "haze_volume", "params": {}}]
    assert _ids(check(s, _p("toycar"), cat).script) == ["shaft_dust"]


def test_low_confidence_wheels_are_skipped_with_an_info_issue(tmp_path):
    cat = _cat(tmp_path, [TYRE])
    p = copy.deepcopy(_p("sports_car"))
    for w in p.wheels:
        w["confidence"] = "low"
    assert facts(p)["wheels"] == (False, True)
    r = check(_script(), p, cat)
    assert _ids(r.script) == [] and [i.code for i in r.issues if i.path == "realism.tyre_contact"] == [
        "realism_skipped_low_confidence"]


def test_auto_params_and_pins(tmp_path):
    cat = _cat(tmp_path, [CONTACT])
    s = _script()
    r = check(s, _p("toycar"), cat)
    assert r.script["realism"][0]["params"] == {"sinkMm": 0.0}             # studio: no sink
    s["realism"] = [{"kind": "realism", "id": "contact_ground", "params": {"sinkMm": 9.0}}]
    assert check(s, _p("toycar"), cat).script["realism"][0]["params"] == {"sinkMm": 9.0}
    s["realism"] = [{"kind": "realism", "id": "contact_ground", "params": {"sinkMm": 999}}]
    r = check(s, _p("toycar"), cat)
    assert r.script["realism"][0]["params"] == {"sinkMm": 0.0}
    assert any(i.code == "realism_param_ignored" and i.severity == "info" for i in r.issues)


def test_order_is_the_build_order_and_unknown_given_entries_are_dropped(tmp_path):
    cat = _cat(tmp_path, [GLASS, CONTACT])
    s = _script()
    s["realism"] = [{"kind": "realism", "id": "wheel_roll", "params": {}}]
    r = check(s, _p("pocket_watch"), cat)
    assert _ids(r.script) == ["contact_ground", "glass_caustics"]
    assert ORDER.index("wheel_roll") < ORDER.index("tyre_contact")        # spin before flatten
    assert ORDER.index("suspension") < ORDER.index("wheel_roll")          # body motion first


def test_wind_defaults_from_the_world_and_a_script_wind_is_kept():
    cat = Catalog.load()
    if cat.get("field", "wind") is None:
        pytest.skip("the wind field block lands in Task 13")
    r = check(_script(), _p("toycar"), cat)
    w = r.script["wind"]
    assert w["id"] == "wind" and w["params"]["speedMs"] == 0.0 and 0 <= w["params"]["directionDeg"] < 360
    assert check(_script(), _p("toycar"), cat).script["wind"] == w          # seeded: deterministic
    s = _script()
    s["wind"] = {"id": "wind", "params": {"speedMs": 4.0}}
    assert check(s, _p("toycar"), cat).script["wind"]["params"]["speedMs"] == 4.0


def test_realism_defaults_with_a_script_equals_the_checker(tmp_path):
    cat = _cat(tmp_path, [CONTACT, TYRE])
    s = check(_script(), _p("sports_car"), cat).script
    assert realism_defaults(_p("sports_car"), cat, script=_script()) == s["realism"]


def test_resolution_is_pure_and_adds_no_errors(tmp_path):
    cat = _cat(tmp_path, [CONTACT, TYRE])
    s, issues = _script(), []
    resolve_wind(s, cat, issues)
    resolve_realism(s, _p("sports_car"), cat, issues)
    assert errors(issues) == [] and all(i.severity == "info" for i in issues)
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_physics_applies.py -q`.

- [ ] **Step 3: Implement.**

`engine/physics/applies.py`:

```python
"""Which realism blocks apply to a script, and with which params (research/physics/BLOCKS.md §1:
compiler-added, never chosen by the director). The checker calls resolve_wind and resolve_realism
after validation. Every decision is an `info` issue: nothing here is an error, so it costs the director
no repair round and needs no repair hint (phase-3 Task 24 drift test)."""
from engine.compiler.context import block_seed
from engine.issues import Issue
from engine.physics import contact, suspension

# Build order = modifier stack order: body motion, then wheel spin, then the tyre flatten (a spinning
# wheel keeps its patch at the bottom, METHODS CD-02); object-level settle after the deformers.
ORDER = ("contact_ground", "suspension", "wheel_roll", "tyre_contact", "soft_rest", "landing_settle",
         "dangling_sway", "foliage_sway", "ground_conform", "shaft_dust", "glass_caustics")


def facts(profile):
    """{fact: (present at high confidence, present only at low confidence)} for catalog.PROFILE_FACTS."""
    ws, soft, dang = profile.wheels or [], profile.softParts or [], profile.danglingParts or []
    wheels_high = bool(ws) and all(w.get("confidence") == "high" for w in ws)
    low_w = bool(ws) and not wheels_high
    soft_high = any(s.get("confidence") == "high" for s in soft)
    soft_ground = any(s.get("confidence") == "high" and s.get("touchesGround") for s in soft)
    dang_high = any(d.get("confidence") == "high" for d in dang)
    return {
        "wheels": (wheels_high, low_w),
        "wheelsSeparable": (wheels_high and all(w.get("separable") for w in ws), low_w),
        "tyreBand": (wheels_high and all(w.get("tyreBand") and w.get("width") for w in ws), low_w),
        "bodySeparable": (wheels_high and bool((profile.vehicle or {}).get("bodySeparable")), low_w),
        "softParts": (soft_high, bool(soft) and not soft_high),
        "softGround": (soft_ground, any(s.get("touchesGround") for s in soft) and not soft_ground),
        "danglingParts": (dang_high, bool(dang) and not dang_high),
    }


def match(m, s, profile, catalog):
    """(applies, reason, skipped_for_low_confidence)."""
    aw, fx, why = m.get("appliesWhen", {}), facts(profile), []
    pl = s["subject"].get("placement")
    if "placement" in aw:
        if pl not in aw["placement"]:
            return False, f"placement {pl}", False
        why.append(f"placement {pl}")
    for name in aw.get("profile", []):
        ok, low = fx[name]
        if not ok:
            return False, f"profile {name} {'is low confidence' if low else 'absent'}", low
        why.append(f"profile {name}")
    for name in aw.get("profileNot", []):
        if fx[name][0]:
            return False, f"profile has {name}", False
    world = catalog.get("world", s["world"]["id"]) or {}
    w, gt = aw.get("world", {}), world.get("groundType", "studio")
    if "groundType" in w:
        if gt not in w["groundType"]:
            return False, f"ground {gt}", False
        why.append(f"ground {gt}")
    if "hasFoliage" in w and bool(world.get("hasFoliage", False)) != w["hasFoliage"]:
        return False, "world foliage", False
    if aw.get("motion"):
        flags = (catalog.get("motion", s["subject"]["motion"]["id"]) or {}).get("subjectMotion") or {}
        hit = [k for k in aw["motion"] if flags.get(k)]
        if not hit:
            return False, "the subject never " + "/".join(aw["motion"]), False
        why.append("motion " + "/".join(hit))
    if aw.get("effects"):
        present = {fx_["id"] for fx_ in s.get("effects", []) if isinstance(fx_, dict)}
        hit = [e for e in aw["effects"] if e in present]
        if not hit:
            return False, "no " + "/".join(aw["effects"]), False
        why.append("effect " + "/".join(hit))
    shares = {x["class"]: x["share"] for x in profile.materials}
    for cls, lo in aw.get("materials", {}).items():
        if shares.get(cls, 0.0) < lo:
            return False, f"{cls} share {shares.get(cls, 0.0):.3f} < {lo}", False
        why.append(f"{cls} share {shares[cls]:.3f}")
    if "sizeM" in aw and not aw["sizeM"][0] <= profile.longest <= aw["sizeM"][1]:
        return False, f"size {profile.longest:.3f} m outside {aw['sizeM']}", False
    return True, "; ".join(why) or "always", False


def _auto_contact(profile, s, world):
    return {"sinkMm": 1000.0 * contact.sink_m(world.get("groundType", "studio"), profile.sizeM[2])}


def _auto_suspension(profile, s, world):
    return {"rideHz": suspension.ride_hz((profile.vehicle or {}).get("vehicleClass", "comfort"))}


AUTO = {"contact_ground": _auto_contact, "suspension": _auto_suspension}   # block id -> auto params


def _valid(spec, v):
    t = spec["type"]
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool) and spec["min"] <= v <= spec["max"]
    if t == "enum":
        return v in spec["values"]
    return isinstance(v, bool)


def resolve_realism(s, profile, catalog, issues):
    given = {r["id"]: r for r in s.get("realism", []) if isinstance(r, dict) and r.get("kind") == "realism"}
    other = [r for r in s.get("realism", []) if isinstance(r, dict) and r.get("kind") != "realism"]
    world = catalog.get("world", s["world"]["id"]) or {}
    ids = [b for b in ORDER if b in catalog.ids("realism")]
    ids += sorted(set(catalog.ids("realism")) - set(ORDER))
    out = []
    for bid in ids:
        m = catalog.get("realism", bid)
        ok, reason, low = match(m, s, profile, catalog)
        if not ok:
            if low:
                issues.append(Issue("realism_skipped_low_confidence", f"realism.{bid}", reason, "info"))
            if bid in given:
                issues.append(Issue("realism_not_applicable", f"realism.{bid}", reason, "info"))
            continue
        specs = m["params"]
        params = {k: sp["default"] for k, sp in specs.items()}
        auto = AUTO[bid](profile, s, world) if bid in AUTO else {}
        for k in m.get("autoParams", []):
            params[k] = float(min(max(auto[k], specs[k]["min"]), specs[k]["max"]))
        for k, v in (given.get(bid, {}).get("params") or {}).items():
            if k in specs and _valid(specs[k], v):
                params[k] = v
            else:
                issues.append(Issue("realism_param_ignored", f"realism.{bid}.params.{k}",
                                    f"{v!r} is not a valid {k}", "info"))
        out.append({"kind": "realism", "id": bid, "params": params, "reason": reason})
        issues.append(Issue("realism_applied", f"realism.{bid}", reason, "info"))
    res = other + out
    if res:
        s["realism"] = res
    else:
        s.pop("realism", None)


def resolve_wind(s, catalog, issues):
    """One wind per clip. A valid script wind is kept; otherwise the world's still-air default, with a
    seeded direction (calm unless the script asks)."""
    m = catalog.get("field", "wind")
    if m is None:
        return
    if isinstance(s.get("wind"), dict) and s["wind"].get("id") == "wind":
        issues.append(Issue("wind_from_script", "wind", f"{s['wind']['params'].get('speedMs')} m/s", "info"))
        return
    world = catalog.get("world", s["world"]["id"]) or {}
    params = {k: sp["default"] for k, sp in m["params"].items()}
    params["speedMs"] = float(world.get("windDefault", params["speedMs"]))
    params["directionDeg"] = float(block_seed(s["seed"], "field", "wind") % 360)
    s["wind"] = {"id": "wind", "params": params}
    issues.append(Issue("wind_defaulted", "wind", f"{params['speedMs']} m/s from world {s['world']['id']}", "info"))
```

`engine/script.py` — in `validate_and_repair`, after the effects loop (read the file first; Task 12a
added the `realism` loop there):

```python
    if s.get("wind") is not None:
        _block(s.get("wind"), "field", "wind", catalog, issues)   # system-owned; reuses existing codes
```

and in Task 12a's `realism` loop, entries of kind `realism` are **not** run through `_block` (that would
clamp pins and fill every default as `repaired` issues, and an unknown or non-applying id would be an
`unknown_block` error before the resolver can drop it with an `info`). Only their shape is checked:

```python
    for i, ref in enumerate(realism):
        kind = ref.get("kind") if isinstance(ref, dict) else None
        if kind == "realism":   # system-owned; engine/physics/applies.py resolves ids and pins (info only)
            if not isinstance(ref.get("id"), str) or not isinstance(ref.get("params", {}), dict):
                issues.append(Issue("bad_realism", f"realism[{i}]", "expected {kind, id, params}", "error"))
            continue
        ...  # Task 12a's existing body for other kinds, unchanged
```

If phase 3 added `"wind"` to `RESERVED` (PHASING §2 phase 3 reserves `wind`, `sims`, `realism`), remove
`"wind"` from `RESERVED` in this commit and say so in the message (`sims` stays reserved).

`engine/checker.py` — `from engine.physics.applies import resolve_realism, resolve_wind`, and in
`check()`, right after the `if errors(issues): return CheckResult(False, s, issues)` that follows
`_targets(...)`:

```python
    resolve_wind(s, catalog, issues)
    resolve_realism(s, profile, catalog, issues)
```

`engine/realism.py` — keep Task 12a's body; add the optional argument:

```python
def realism_defaults(profile, catalog, script=None):
    """Task 12a contract. With a checked-shape script, the exact list the checker will resolve
    (engine/physics/applies.py); without one, the profile-only rule below (phase-3 callers)."""
    if script is not None:
        import copy
        from engine.physics.applies import resolve_realism
        s = copy.deepcopy(script)
        resolve_realism(s, profile, catalog, [])
        return s.get("realism", [])
    out = []
    for kind, bid in catalog.always_on():
        m = catalog.get(kind, bid)
        if catalog.applies(m, profile):
            # kind realism: no params -> nothing pinned, so the checker's auto params (sink by ground,
            # ride frequency by class) are not overridden by defaults written by sanitize/fallback.
            params = {} if kind == "realism" else {k: sp["default"] for k, sp in m["params"].items()}
            out.append({"kind": kind, "id": bid, "params": params})
    return out
```

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests/test_physics_applies.py engine/tests/test_checker.py engine/tests/test_realism.py -q`, then the fast loop. The wind test skips until Task 13.

- [ ] **Step 5: Commit**

```bash
git add engine/physics/applies.py engine/checker.py engine/script.py engine/realism.py engine/tests/test_physics_applies.py engine/tests/test_realism.py
git commit -m "feat(checker): resolve realism defaults and the wind field (info only, never an error)"
```

---
## Chunk 3: Blender plumbing

**Node idnames and sockets probed in Blender 5.0.1 (2026-09-24), used below without a further probe:**
`GeometryNodeSetPosition` (Geometry, Selection, Position, Offset), `GeometryNodeInputNamedAttribute`
(`data_type` FLOAT/INT/FLOAT_VECTOR…; out Attribute, Exists), `GeometryNodeStoreNamedAttribute`
(Geometry, Selection, Name, Value; `data_type`, `domain`), `GeometryNodeObjectInfo` (Object, As Instance →
Transform, Location, Rotation, Scale, Geometry; `transform_space` ORIGINAL/RELATIVE),
`GeometryNodeSelfObject` (→ Self Object), `FunctionNodeInvertMatrix` (→ Matrix, Invertible),
`FunctionNodeMatrixMultiply` (Matrix, Matrix → Matrix), `FunctionNodeTransformPoint` (Vector,
Transform), `FunctionNodeTransformDirection` (Direction, Transform), `FunctionNodeSeparateTransform`
(→ Translation, Rotation, Scale), `FunctionNodeAxisAngleToRotation` (Axis, Angle), `FunctionNodeRotateVector`
(Vector, Rotation), `FunctionNodeCompare` (`data_type`, `operation` incl. EQUAL; input "Epsilon"),
`GeometryNodeSwitch` (`input_type` incl. VECTOR; Switch, False, True → Output), `ShaderNodeMapRange`
(`interpolation_type` SMOOTHSTEP), `ShaderNodeMath`, `ShaderNodeVectorMath` (out Vector / Value),
`ShaderNodeCombineXYZ`, `ShaderNodeSeparateXYZ`, `ShaderNodeTexNoise` (Vector… → Factor, Color),
`GeometryNodeInputSceneTime` (→ Seconds, Frame), `GeometryNodeInputMeshIsland` (→ Island Index),
`GeometryNodeAccumulateField`, `GeometryNodePoints` (Count, Position, Radius), `FunctionNodeRandomValue`,
`GeometryNodeInputIndex`, `GeometryNodeSetMaterial`, `GeometryNodeJoinGeometry`, `GeometryNodeGroup`;
shader `ShaderNodeAmbientOcclusion` (Color, Distance, Normal → Color, AO; props `samples`,
`only_local`, `inside`); `obj.modifiers.move`; `ob.cycles.is_caustics_caster/receiver`,
`light.cycles.is_caustics_light`, `world.cycles.is_caustics_light`,
`scene.cycles.caustics_refractive/reflective`. Not probed (the test is the arbiter): the operand order of
`FunctionNodeMatrixMultiply` (A @ B assumed) and that `Mesh.to_mesh()` keeps generic point attributes.

### Task 12: The subject rig, the Geometry Nodes builder, the build order and the compile probe

**Files:**
- Create: `engine/blender/gn.py`, `engine/blender/realism_rig.py`, `engine/blender/realism_probe.py`,
  `engine/physics/probes.py`, `engine/tests/realism_catalog.py`,
  `engine/tests/fixtures/blocks/motion/test_slide_stop/{block.json,build.py}`,
  `engine/tests/fixtures/blocks/motion/test_drop/{block.json,build.py}`,
  `engine/tests/fixtures/script_realism.json`, `engine/tests/test_realism_blender.py`,
  `engine/tests/test_physics_probes.py`
- Modify: `engine/compiler/blender_main.py`, `engine/compiler/run.py`,
  `engine/tests/test_compile_blender.py` (only if an assertion names the old object set)

- [ ] **Step 1: Write the pure failing test** — `engine/tests/test_physics_probes.py`:

```python
from engine.physics import probes


def test_grounded_and_patch_rules():
    assert probes.grounded_ok({"minZ": -0.0004}, 0.0) and not probes.grounded_ok({"minZ": 0.003}, 0.0)
    rec = {"minZ": -0.0002, "flatLenM": 0.16, "flatN": 9}
    assert probes.tyre_patch_ok(rec, 0.35, 0.45, 0.0)                 # want 0.1575 m
    assert not probes.tyre_patch_ok({**rec, "flatLenM": 0.05}, 0.35, 0.45, 0.0)
    assert not probes.tyre_patch_ok({**rec, "minZ": -0.01}, 0.35, 0.45, 0.0)
```

`engine/physics/probes.py`:

```python
"""Pass rules for the compile-probe records (research/physics/BLOCKS.md §5 [C]). Report-only until
calibrated on golden renders (spec §4.8: thresholds are calibrated before they gate anything)."""
from engine.physics import contact

PATCH_TOL = 0.2          # flat length at most +20% of patchLenFrac * r (BLOCKS §5, eng)
PATCH_MIN = 0.6          # and at least 60%: the vertex extent of a coarse tyre (64 segments) reads up to
                         # one segment chord short depending on the wheel's angle (eng; Task 15 measures)


def grounded_ok(rec, sink_m):
    return contact.grounded(rec["minZ"], sink_m)


def tyre_patch_ok(rec, radius, patch_len_frac, sink_m):
    want = patch_len_frac * radius
    return (PATCH_MIN * want <= rec["flatLenM"] <= (1 + PATCH_TOL) * want
            and rec["minZ"] >= -sink_m - contact.GROUND_TOL_M)
```

Run `py -m pytest engine/tests/test_physics_probes.py -q` → FAIL, add the file → PASS.

- [ ] **Step 2: Add the test-only fixtures.**

`engine/tests/fixtures/script_realism.json` (one 3 s orbit; far enough that a moving subject never
reaches the camera):

```json
{
  "schema": "valora.scene/1",
  "seed": 4242,
  "direction": {"id": "test/realism", "source": "dice"},
  "prompt": "",
  "assumptions": [],
  "format": {"aspect": "16:9", "durationS": 3, "fps": 30},
  "subject": {"placement": "ground", "motion": {"id": "static", "params": {}}, "finishOverrides": []},
  "world": {"id": "studio_cyc", "params": {"tone": "grey"}},
  "lighting": {"id": "softbox_three_point", "params": {}},
  "shots": [{"startS": 0, "endS": 3, "camera": {"id": "arc_orbit", "params": {"distance": 6.0, "elevationDeg": 8.0}}, "focus": "subject"}],
  "effects": [],
  "grade": {"id": "neutral_film", "params": {}}
}
```

`engine/tests/fixtures/blocks/motion/test_slide_stop/block.json`:

```json
{
  "id": "test_slide_stop",
  "kind": "motion",
  "description": "TEST ONLY. The subject slides along its long axis, easing out to a stop at 60% of the clip.",
  "directorSelectable": false,
  "capabilities": [],
  "subjectMotion": {"translates": true, "stops": true},
  "params": {"distanceFrac": {"type": "number", "min": 0.05, "max": 1.0, "default": 0.3}},
  "subjectSizeM": [0.02, 30.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "costWeight": 1.0,
  "tierMax": "T3",
  "tags": {"mood": [], "energy": [], "palette": []}
}
```

`engine/tests/fixtures/blocks/motion/test_slide_stop/build.py`:

```python
"""TEST ONLY: slide along the long axis (quadratic ease-out, so speed falls linearly to 0) and stop."""


def build(ctx):
    import bpy
    from engine.blender.realism_rig import MOTION, key_series
    prof, n = ctx.profile, ctx.scene.frame_end
    stop = max(3, round(0.6 * n))
    ax = 0 if prof.sizeM[0] >= prof.sizeM[1] else 1
    dist = ctx.params["distanceFrac"] * prof.longest
    frames = list(range(1, stop + 1))
    vals = [-dist / 2 + dist * (1 - (1 - (f - 1) / (stop - 1)) ** 2) for f in frames]
    key_series(bpy.data.objects[MOTION], "location", ax, frames, vals)
```

`engine/tests/fixtures/blocks/motion/test_drop/block.json` — as above with `"id": "test_drop"`,
description `"TEST ONLY. The subject falls from heightFrac x its height under true gravity and lands."`,
`"subjectMotion": {"lands": true}`, params
`{"heightFrac": {"type": "number", "min": 0.1, "max": 2.0, "default": 0.5}}`.

`engine/tests/fixtures/blocks/motion/test_drop/build.py`:

```python
"""TEST ONLY: free fall at g = 9.81 m/s^2 from heightFrac x the subject's height, then rest on z = 0."""


def build(ctx):
    import bpy
    from engine.blender.realism_rig import MOTION, key_series
    fps, n = ctx.script["format"]["fps"], ctx.scene.frame_end
    h = ctx.params["heightFrac"] * ctx.profile.sizeM[2]
    frames = list(range(1, n + 1))
    key_series(bpy.data.objects[MOTION], "location", 2, frames,
               [max(0.0, h - 0.5 * 9.81 * ((f - 1) / fps) ** 2) for f in frames])
```

`engine/tests/realism_catalog.py`:

```python
"""The shipped catalog plus the test-only fixture blocks (engine/tests/fixtures/blocks) in a temp root.
The shipped catalog never contains a fixture block."""
import shutil
from pathlib import Path

from engine.catalog import BLOCKS_DIR, Catalog

FIXTURE_BLOCKS = Path(__file__).parent / "fixtures" / "blocks"


def catalog_with_fixtures(tmp_path):
    root = Path(tmp_path) / "catalog"
    ign = shutil.ignore_patterns("__pycache__")
    shutil.copytree(BLOCKS_DIR, root, ignore=ign)
    for kind_dir in sorted(p for p in FIXTURE_BLOCKS.iterdir() if p.is_dir()):
        for b in sorted(p for p in kind_dir.iterdir() if p.is_dir()):
            shutil.copytree(b, root / kind_dir.name / b.name, ignore=ign)
    return Catalog.load(root)
```

- [ ] **Step 3: Write the failing Blender tests** — `engine/tests/test_realism_blender.py`:

```python
"""Realism defaults in Blender: compile probes at <= 3 frames, no renders unless a test says so."""
import json
import subprocess
from pathlib import Path

import pytest

from engine.compiler.run import compile_scene
from engine.ingest.run import BLENDER
from engine.profile import SubjectProfile
from engine.tests.conftest import requires_blender
from engine.tests.realism_catalog import catalog_with_fixtures

pytestmark = [pytest.mark.blender, requires_blender]
ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"
MODELS = ROOT / "assets-in" / "models"


def _profile(name):
    return SubjectProfile.from_dict(json.loads((FIX / "profiles" / f"{name}.json").read_text(encoding="utf-8")))


def _script(motion="static", **over):
    s = json.loads((FIX / "script_realism.json").read_text(encoding="utf-8"))
    s["subject"]["motion"] = {"id": motion, "params": {}}
    s.update(over)
    return s


def _glb(name):
    glb = MODELS / name / f"{name}.glb"
    if not glb.exists():
        pytest.skip(f"{name} model not present (local-only)")
    return glb


def _compile(name, tmp, script=None, catalog=None, frames=(1,), skip=("grade",), **kw):
    return compile_scene(script or _script(), _profile(name), _glb(name), tmp, render=False, skip_kinds=skip,
                         catalog=catalog, realism_probe=list(frames), **kw)


def _bl(body, tmp_path):
    """Run `body` in headless Blender with the repo importable; must print nothing special, just not fail."""
    script = tmp_path / "t.py"
    script.write_text("import sys\n" f"sys.path.insert(0, r'{ROOT}')\n"
                      "import bpy, numpy as np\nbpy.ops.wm.read_factory_settings(use_empty=True)\n"
                      + body + "\nprint('RB-OK')\n", encoding="utf-8")
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                           "--python", str(script)], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0 and "RB-OK" in proc.stdout, proc.stdout[-2000:] + proc.stderr[-2000:]
    return proc.stdout


def test_every_scene_has_the_subject_rig_and_a_motion_record(tmp_path):
    res = _compile("toycar", tmp_path)
    names = {o["name"] for o in res["objects"]}
    assert {"valora_motion", "valora_realism_offset", "valora_subject"} <= names
    assert res["built"][0] == "world:studio_cyc"
    assert res["motionEvents"] == {"stops": [], "landings": []}


def test_placed_space_round_trips_through_the_rig(tmp_path):
    _bl(
        "from engine.blender.realism_rig import build_rig, placed_points\n"
        "from engine.blender import gn\n"
        "root = bpy.data.objects.new('valora_subject', None); bpy.context.scene.collection.objects.link(root)\n"
        "motion, offset = build_rig(bpy.context.scene, root)\n"
        "motion.location = (1.0, -2.0, 0.3); motion.rotation_euler = (0, 0, 0.7)\n"
        "offset.location = (0.0, 0.0, -0.01); offset.scale = (1.02, 1.02, 0.95)\n"
        "root.scale = (0.5, 0.5, 0.5); root.location = (0.1, 0.2, 0.0)\n"
        "bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.3, 0.1, 0.5)); c = bpy.context.object\n"
        "c.rotation_euler = (0.2, 0.1, 0.3); c.parent = root\n"
        "bpy.context.view_layer.update()\n"
        "want = placed_points(c)\n"
        "t = gn.Tree('probe'); P, back = gn.placed(t, offset)\n"
        "t.store('p', P, 'FLOAT_VECTOR'); t.set_position(back(P)); gn.add_modifier(c, t.finish(), 'p')\n"
        "bpy.context.view_layer.update()\n"
        "ev = c.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh()\n"
        "got = np.empty(len(me.vertices) * 3); me.attributes['p'].data.foreach_get('vector', got)\n"
        "co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co)\n"
        "orig = np.empty(len(c.data.vertices) * 3); c.data.vertices.foreach_get('co', orig)\n"
        "assert np.allclose(got.reshape(-1, 3), want, atol=1e-5), (got[:6], want[:2])\n"
        "assert np.allclose(co, orig, atol=1e-5)  # back(P) is the identity\n", tmp_path)


def test_motion_events_come_from_the_motion_track(tmp_path):
    cat = catalog_with_fixtures(tmp_path)
    slide = _compile("toycar", tmp_path / "s", script=_script("test_slide_stop"), catalog=cat)
    assert len(slide["motionEvents"]["stops"]) == 1
    assert abs(slide["motionEvents"]["stops"][0]["frame"] - 54) <= 3          # 60% of 90 frames
    drop = _compile("toycar", tmp_path / "d", script=_script("test_drop"), catalog=cat)
    assert len(drop["motionEvents"]["landings"]) == 1
```

- [ ] **Step 4: Run, expect FAIL** — `py -m pytest engine/tests/test_realism_blender.py -q -m blender`.

- [ ] **Step 5: Implement.**

`engine/blender/gn.py`:

```python
"""A small builder for Geometry Nodes trees, so realism blocks read as the maths in engine/physics, not
as node plumbing. Runs inside Blender only (import it inside build(), never from host code)."""
import bpy


def _sock(v):
    return hasattr(v, "is_output")


class Tree:
    """A node group. Default: a deformer (Geometry in, Geometry out). Pass inputs/outputs for a function
    group, e.g. inputs=(("Position", "NodeSocketVector"),), outputs=(("Wind", "NodeSocketVector"),)."""

    def __init__(self, name, inputs=(("Geometry", "NodeSocketGeometry"),),
                 outputs=(("Geometry", "NodeSocketGeometry"),)):
        self.ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
        for n, t in inputs:
            self.ng.interface.new_socket(n, in_out="INPUT", socket_type=t)
        for n, t in outputs:
            self.ng.interface.new_socket(n, in_out="OUTPUT", socket_type=t)
        self._in = self.ng.nodes.new("NodeGroupInput")
        self._out = self.ng.nodes.new("NodeGroupOutput")
        self.geometry = self._in.outputs.get("Geometry")

    def input(self, name):
        return self._in.outputs[name]

    def node(self, idname, **props):
        n = self.ng.nodes.new(idname)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def feed(self, sock, v):
        if _sock(v):
            self.ng.links.new(v, sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=0.0, c=0.0):
        n = self.node("ShaderNodeMath", operation=op)
        for s, v in zip(n.inputs, (a, b, c)):
            self.feed(s, v)
        return n.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        n = self.node("ShaderNodeVectorMath", operation=op)
        self.feed(n.inputs[0], a)
        if b is not None:
            self.feed(n.inputs[1], b)
        if scale is not None:
            self.feed(n.inputs["Scale"], scale)
        return n.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else n.outputs["Vector"]

    def vec(self, x, y, z):
        n = self.node("ShaderNodeCombineXYZ")
        for s, v in zip(n.inputs, (x, y, z)):
            self.feed(s, v)
        return n.outputs[0]

    def xyz(self, v):
        n = self.node("ShaderNodeSeparateXYZ")
        self.feed(n.inputs[0], v)
        return n.outputs["X"], n.outputs["Y"], n.outputs["Z"]

    def position(self):
        return self.node("GeometryNodeInputPosition").outputs[0]

    def time(self):
        return self.node("GeometryNodeInputSceneTime").outputs["Seconds"]

    def attr(self, name, data_type="FLOAT"):
        n = self.node("GeometryNodeInputNamedAttribute", data_type=data_type)
        n.inputs["Name"].default_value = name
        return n.outputs["Attribute"]

    def equals(self, a, b):
        """Float compare with epsilon 0.5: reads INT tag attributes (wheel index + 1) exactly."""
        n = self.node("FunctionNodeCompare", data_type="FLOAT", operation="EQUAL")
        self.feed(n.inputs[0], a)
        self.feed(n.inputs[1], b)
        n.inputs["Epsilon"].default_value = 0.5
        return n.outputs[0]

    def self_object(self):
        return self.node("GeometryNodeSelfObject").outputs[0]

    def object_transform(self, obj, space="ORIGINAL"):
        n = self.node("GeometryNodeObjectInfo", transform_space=space)
        self.feed(n.inputs["Object"], obj)
        return n.outputs["Transform"]

    def object_location(self, obj):
        n = self.node("GeometryNodeObjectInfo", transform_space="ORIGINAL")
        self.feed(n.inputs["Object"], obj)
        return n.outputs["Location"]

    def invert(self, m):
        n = self.node("FunctionNodeInvertMatrix")
        self.feed(n.inputs[0], m)
        return n.outputs["Matrix"]

    def matmul(self, a, b):
        n = self.node("FunctionNodeMatrixMultiply")
        self.feed(n.inputs[0], a)
        self.feed(n.inputs[1], b)
        return n.outputs[0]

    def point(self, v, m):
        n = self.node("FunctionNodeTransformPoint")
        self.feed(n.inputs["Vector"], v)
        self.feed(n.inputs["Transform"], m)
        return n.outputs[0]

    def translation(self, m):
        n = self.node("FunctionNodeSeparateTransform")
        self.feed(n.inputs[0], m)
        return n.outputs["Translation"]

    def rotate(self, v, axis, angle):
        r = self.node("FunctionNodeAxisAngleToRotation")
        self.feed(r.inputs["Axis"], axis)
        self.feed(r.inputs["Angle"], angle)
        n = self.node("FunctionNodeRotateVector")
        self.feed(n.inputs["Vector"], v)
        self.feed(n.inputs["Rotation"], r.outputs[0])
        return n.outputs[0]

    def switch_vec(self, cond, if_false, if_true):
        n = self.node("GeometryNodeSwitch", input_type="VECTOR")
        self.feed(n.inputs["Switch"], cond)
        self.feed(n.inputs["False"], if_false)
        self.feed(n.inputs["True"], if_true)
        return n.outputs[0]

    def smoothstep(self, e0, e1, x):
        n = self.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        n.clamp = True
        self.feed(n.inputs["Value"], x)
        self.feed(n.inputs["From Min"], e0)
        self.feed(n.inputs["From Max"], e1)
        n.inputs["To Min"].default_value, n.inputs["To Max"].default_value = 0.0, 1.0
        return n.outputs["Result"]

    def noise(self, v, scale=1.0):
        n = self.node("ShaderNodeTexNoise")
        self.feed(n.inputs["Vector"], v)
        n.inputs["Scale"].default_value = scale
        return n.outputs["Factor"], n.outputs["Color"]

    def group(self, ng, **inputs):
        n = self.node("GeometryNodeGroup")
        n.node_tree = ng
        for k, v in inputs.items():
            self.feed(n.inputs[k], v)
        return n

    def store(self, name, value, data_type="FLOAT", domain="POINT"):
        n = self.node("GeometryNodeStoreNamedAttribute", data_type=data_type, domain=domain)
        self.feed(n.inputs["Geometry"], self.geometry)
        n.inputs["Name"].default_value = name
        self.feed(n.inputs["Value"], value)
        self.geometry = n.outputs["Geometry"]

    def set_position(self, pos, selection=None):
        n = self.node("GeometryNodeSetPosition")
        self.feed(n.inputs["Geometry"], self.geometry)
        if selection is not None:
            self.feed(n.inputs["Selection"], selection)
        self.feed(n.inputs["Position"], pos)
        self.geometry = n.outputs["Geometry"]

    def output(self, name, sock):
        self.ng.links.new(sock, self._out.inputs[name])

    def finish(self):
        if self.geometry is not None and "Geometry" in self._out.inputs:
            self.ng.links.new(self.geometry, self._out.inputs["Geometry"])
        return self.ng


def add_modifier(obj, ng, name):
    mod = obj.modifiers.new(name, "NODES")
    mod.node_group = ng
    return mod


def placed(t, offset):
    """(P, back): this vertex in placed space, and a function mapping a placed-space point back to the
    object's local space. rel = inverse(M_self) @ M_offset maps placed -> local."""
    rel = t.matmul(t.invert(t.object_transform(t.self_object())), t.object_transform(offset))
    return t.point(t.position(), t.invert(rel)), (lambda v: t.point(v, rel))


def ground_in_placed(t, offset, world_z):
    """Placed-space height of the world plane z = world_z under the realism offset (which translates and
    scales but never tilts)."""
    m = t.object_transform(offset)
    x, y, _ = t.xyz(t.translation(m))
    return t.xyz(t.point(t.vec(x, y, world_z), t.invert(m)))[2]
```

If the round-trip test fails with a transposed result, swap the two `matmul` operands (the operand
order is the one fact this plan could not probe); keep the test.

`engine/blender/realism_rig.py`:

```python
"""The subject hierarchy every realism block builds on, and the helpers they share (runs inside Blender).

    valora_motion             motion blocks keyframe this (translate / yaw)
     └ valora_realism_offset  realism keyframes this (ground sink, tyre deflection, landing settle, squash)
        └ valora_subject      the compiler's placement (static scale + location)
           └ the upload's own objects

Placed space P = the local space of valora_realism_offset: placed metres, before motion and realism.
SubjectProfile points (wheels, contacts, dangling parts) are in P. Drivers are empties whose keyed
location carries a value per frame; Geometry Nodes read them with Object Info, so every frame
evaluates on its own (METHODS R1)."""
import bpy
import numpy as np

MOTION, OFFSET = "valora_motion", "valora_realism_offset"
TYRE, SPIN, UNSPRUNG = "valora_tyre", "valora_spin", "valora_unsprung"
SWAY, SWAY_LEN = "valora_sway", "valora_sway_len"
GROUND_TAG, FOLIAGE_TAG = "valora_ground", "valora_foliage"


def build_rig(scene, root):
    motion = bpy.data.objects.new(MOTION, None)
    offset = bpy.data.objects.new(OFFSET, None)
    for o in (motion, offset):
        scene.collection.objects.link(o)
    offset.parent = motion
    root.parent = offset
    bpy.context.view_layer.update()
    return motion, offset


def rig():
    return bpy.data.objects[MOTION], bpy.data.objects[OFFSET]


def fcurves(action):
    """F-curves of an action, for Blender 5 layered actions and legacy ones (moved from blender_main)."""
    if hasattr(action, "layers"):
        return [c for layer in action.layers for strip in layer.strips for bag in strip.channelbags for c in bag.fcurves]
    return list(action.fcurves)


def driver(name):
    """An empty whose keyed location carries per-frame values for node trees; never rendered."""
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, None)
        bpy.context.scene.collection.objects.link(ob)
        ob.hide_render = True
    return ob


def key_series(obj, path, index, frames, values):
    """Keys obj.<path>[index] = values[i] at frames[i], linear between keys."""
    for f, v in zip(frames, values):
        getattr(obj, path)[index] = v
        obj.keyframe_insert(path, index=index, frame=f)
    for c in fcurves(obj.animation_data.action):
        if c.data_path == path and c.array_index == index:
            for kp in c.keyframe_points:
                kp.interpolation = "LINEAR"


def motion_track(scene):
    """(positions, yaws) of valora_motion for frames 1..frame_end, from its F-curves (no depsgraph)."""
    motion, _ = rig()
    ad = motion.animation_data
    curves = {(c.data_path, c.array_index): c for c in fcurves(ad.action)} if ad and ad.action else {}

    def ev(path, i, f, default):
        c = curves.get((path, i))
        return float(c.evaluate(f)) if c else float(default)

    frames = range(1, scene.frame_end + 1)
    pos = [tuple(ev("location", k, f, motion.location[k]) for k in range(3)) for f in frames]
    yaw = [ev("rotation_euler", 2, f, motion.rotation_euler[2]) for f in frames]
    return pos, yaw


def placed_points(obj):
    """(n, 3) vertices of obj's own mesh in placed space at the current frame."""
    _, offset = rig()
    m = np.array(offset.matrix_world.inverted() @ obj.matrix_world)
    co = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]


def write_attr(obj, name, values, kind="INT"):
    """A per-vertex attribute on obj's own mesh (a mesh shared with another object is copied first)."""
    if obj.data.users > 1:
        obj.data = obj.data.copy()
    a = obj.data.attributes.get(name) or obj.data.attributes.new(name, kind, "POINT")
    a.data.foreach_set("value", values.astype(np.int32 if kind == "INT" else np.float32))


def tag_wheels(meshes, wheels):
    """Once per scene: valora_tyre / valora_spin / valora_unsprung per vertex = wheel index + 1 (0 none).
    Uses engine/physics/wheel_mask.py, the same rule ingest used for `separable`."""
    scene = bpy.context.scene
    if scene.get("valora_wheel_tags") is not None:
        return dict(scene["valora_wheel_tags"])
    from engine.blender.islands import summaries, vertex_islands
    from engine.physics.wheel_mask import in_wheel_box, island_spins, tyre_mask
    counts = {"objects": 0, "tyre": 0, "spin": 0, "unsprung": 0}
    for o in meshes:
        if not len(o.data.vertices):
            continue
        P = placed_points(o)
        isl = vertex_islands(o)
        pieces = summaries(P, isl, 0, min_n=1) if isl is not None else []
        tyre, spin, unsprung = (np.zeros(len(P), np.int32) for _ in range(3))
        for i, w in enumerate(wheels):
            tyre[(tyre == 0) & tyre_mask(P, w)] = i + 1
            for s in pieces:
                if in_wheel_box(s["lo"], s["hi"], w):
                    sel = isl == s["id"]
                    unsprung[sel] = i + 1
                    if island_spins(s["lo"], s["hi"], s["centroid"], w):
                        spin[sel] = i + 1
        if tyre.any() or unsprung.any():
            for name, arr in ((TYRE, tyre), (SPIN, spin), (UNSPRUNG, unsprung)):
                write_attr(o, name, arr)
            counts["objects"] += 1
            counts["tyre"] += int((tyre > 0).sum())
            counts["spin"] += int((spin > 0).sum())
            counts["unsprung"] += int((unsprung > 0).sum())
    scene["valora_wheel_tags"] = counts
    return counts


def ground_objects():
    return [o for o in bpy.context.scene.objects if o.get(GROUND_TAG)]


def record(key, value):
    """A fact a realism block wants in compile.json (plain numbers, bools, strings, lists)."""
    bpy.context.scene[f"valora_rz_{key}"] = value


def records(scene):
    return {k[len("valora_rz_"):]: (scene[k].to_list() if hasattr(scene[k], "to_list") else scene[k])
            for k in scene.keys() if k.startswith("valora_rz_")}
```

`engine/blender/realism_probe.py`:

```python
"""Compile-probe measurements (research/physics/BLOCKS.md §5 [C]): evaluated geometry at <= 3 frames,
no rendering. Pass/fail lives in engine/physics/probes.py (report-only until calibrated)."""
import bpy
import numpy as np
from mathutils import Vector

from engine.blender.realism_rig import TYRE, rig

FLAT_TOL_M = 0.0005   # a tyre vertex within 0.5 mm of the tyre's lowest point is on the patch


def _world(ev, me):
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    m = np.array(ev.matrix_world)
    return co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]


def realism_probe(scene, meshes, profile, frames):
    out, f0 = {}, scene.frame_current
    motion, _ = rig()
    for f in list(frames)[:3]:
        scene.frame_set(f)
        deps = bpy.context.evaluated_depsgraph_get()
        zmin, tyres = np.inf, {}
        for o in meshes:
            ev = o.evaluated_get(deps)
            me = ev.to_mesh()
            try:
                if not len(me.vertices):
                    continue
                co = _world(ev, me)
                zmin = min(zmin, float(co[:, 2].min()))
                a = me.attributes.get(TYRE)
                if a is not None and profile.wheels:
                    t = np.empty(len(me.vertices), np.int32)
                    a.data.foreach_get("value", t)
                    for i in np.unique(t[t > 0]):
                        tyres.setdefault(int(i) - 1, []).append(co[t == i])
            finally:
                ev.to_mesh_clear()
        fwd = motion.matrix_world.to_3x3() @ Vector((profile.vehicle or {}).get("forwardAxis", [0.0, 1.0, 0.0]))
        rec = {"minZ": zmin, "tyres": {}}
        for i, pts in sorted(tyres.items()):
            p = np.vstack(pts)
            lo = float(p[:, 2].min())
            flat = p[p[:, 2] <= lo + FLAT_TOL_M]
            along = flat @ np.array(fwd)
            rec["tyres"][str(i)] = {"minZ": lo, "flatN": int(len(flat)),
                                    "flatLenM": float(along.max() - along.min()) if len(flat) else 0.0}
        out[str(f)] = rec
    scene.frame_set(f0)
    return out
```

`engine/compiler/blender_main.py` — read it first (Tasks 12a and 29 changed it):

1. Imports: `from engine.blender.realism_rig import build_rig, fcurves as _fcurves, motion_track, records` and
   `from engine.physics import events`; delete the local `_fcurves` definition (the import keeps the
   name for `build_camera`).
2. In `main()`, right after `root = place_subject(objs, profile)` and the `assert_placement` line:
   `build_rig(bpy.context.scene, root)`.
3. `_refs(script)` already yields `script["realism"]` after effects (Task 12a). Add the field after the
   world, so it becomes:

```python
def _refs(script):
    yield "world", script["world"]
    if script.get("wind"):
        yield "field", script["wind"]     # before every consumer (METHODS §2.9)
    yield "motion", script["subject"]["motion"]
    yield "lighting", script["lighting"]
    for fx in script.get("effects", []):
        yield "effect", fx
    for ref in script.get("realism", []):  # after effects, in the resolver's ORDER (Task 12a contract)
        yield ref["kind"], ref
```
4. After `build_all(...)` (still before the camera):

```python
    pos, _yaw = motion_track(scene)
    result["motionEvents"] = {"stops": events.stops(pos, script["format"]["fps"], profile.longest),
                              "landings": events.landings(pos, script["format"]["fps"], profile.longest)}
    result["realism"] = [r["id"] for r in script.get("realism", [])]
    result["realismScene"] = records(scene)   # facts each realism block recorded (realism_rig.record)
    if scene.get("valora_wind") is not None:
        result["wind"] = {k: float(v) for k, v in scene["valora_wind"].items()}
```
   (with `buildBlocks` false, `motionEvents` is still recorded: an unmoved rig gives empty lists.)
5. After the grade block and before `result["shutter"]`: 

```python
    if job.get("realismProbe"):
        from engine.blender.realism_probe import realism_probe
        result["realismProbe"] = realism_probe(scene, meshes, profile, job["realismProbe"])
```

`engine/compiler/run.py` — `compile_scene(..., realism_probe=None, ...)` and add
`"realismProbe": list(realism_probe or [])` to `job`.

- [ ] **Step 6: Run, expect PASS** — `py -m pytest engine/tests/test_realism_blender.py engine/tests/test_compile_blender.py -q -m blender`, then the fast loop.
If `test_compile_blender.py` asserts an exact object list or `built` list, update only the new rig
names / order and say so in the commit.

- [ ] **Step 7: Commit**

```bash
git add engine/blender/gn.py engine/blender/realism_rig.py engine/blender/realism_probe.py engine/physics/probes.py engine/compiler/blender_main.py engine/compiler/run.py engine/tests/realism_catalog.py engine/tests/fixtures/blocks engine/tests/fixtures/script_realism.json engine/tests/test_realism_blender.py engine/tests/test_physics_probes.py engine/tests/test_compile_blender.py
git commit -m "feat(compiler): subject rig, placed-space node helpers, field-first build order, motion events and realism probe"
```

---

### Task 13: The wind field block, and haze that drifts with it

The field exists in every checked script (Task 11 fills it). Consumers: `haze_volume` now (so the field
has a user from day one, PHASING §2 item 5), `foliage_sway`, `dangling_sway` and `shaft_dust` in
Chunk 4. The Blender WIND force field for legacy particles and cloth is **not** built yet: nothing in
this phase uses it (hand-off H4 names the per-consumer calibration it needs).

**Files:**
- Create: `engine/blocks/field/wind/block.json`, `engine/blocks/field/wind/build.py`
- Modify: `engine/blocks/effect/haze_volume/build.py`, `engine/blender/realism_probe.py` (`sample_wind`),
  `engine/compiler/blender_main.py` (`hazeDrift` flag), `engine/tests/test_realism_blender.py`,
  `engine/tests/test_compile_blender.py` (`built` list gains `field:wind`)

- [ ] **Step 1: Write the failing tests** — append to `engine/tests/test_realism_blender.py`:

```python
def test_the_wind_field_stays_in_its_envelope_and_blows_its_way(tmp_path):
    out = _bl(
        "from types import SimpleNamespace as NS\n"
        "from engine.catalog import Catalog\n"
        "from engine.blender.realism_probe import sample_wind\n"
        "b = Catalog.load().load_builder('field', 'wind')\n"
        "b(NS(scene=bpy.context.scene, seed=7, params={'directionDeg': 90.0, 'speedMs': 4.0, 'gustiness': 0.3, 'turbulence': 0.2}))\n"
        "pts = [(x * 0.7, y * 0.7, z * 0.3) for x in range(-4, 5) for y in range(-4, 5) for z in range(3)]\n"
        "for f in (1, 30, 90):\n"
        "    w = np.array(sample_wind(pts, f))\n"
        "    sp = np.linalg.norm(w, axis=1)\n"
        "    assert sp.min() >= 4.0 * (1 - 0.3) - 4.0 * 0.2 - 1e-3 and sp.max() <= 4.0 * (1 + 0.3) + 4.0 * 0.2 + 1e-3, (sp.min(), sp.max())\n"
        "    m = w.mean(axis=0); ang = np.degrees(np.arctan2(m[1], m[0]))\n"
        "    assert abs(ang - 90.0) <= 20.0, ang\n"
        "    assert np.std(sp) > 0.05  # gusts vary in space\n"
        "a, b2 = np.array(sample_wind(pts, 1)), np.array(sample_wind(pts, 30))\n"
        "assert not np.allclose(a, b2)  # and in time\n", tmp_path)


def test_calm_wind_leaves_the_haze_alone_and_a_breeze_makes_it_drift(tmp_path):
    s = _script(effects=[{"id": "haze_volume", "params": {"density": 0.3}}])
    calm = _compile("toycar", tmp_path / "calm", script=s)
    assert calm["wind"]["speedMs"] == 0.0 and calm["hazeDrift"] is False
    s["wind"] = {"id": "wind", "params": {"speedMs": 4.0}}
    windy = _compile("toycar", tmp_path / "windy", script=s)
    assert windy["hazeDrift"] is True and windy["built"][1] == "field:wind"
```

In `engine/tests/test_compile_blender.py::test_studio_scene_has_cyc_and_three_softboxes`, the expected
`built` list gains `"field:wind"` after the world (Task 14 will add the realism entry).

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement.**

`engine/blocks/field/wind/block.json`:

```json
{
  "id": "wind",
  "kind": "field",
  "description": "One shared wind for the whole clip: the direction the air moves toward, its mean speed, and how gusty and turbulent it is. Every wind-driven effect reads this one field. Still air unless the script asks for wind.",
  "directorSelectable": false,
  "capabilities": [],
  "params": {
    "directionDeg": {"type": "number", "min": 0.0, "max": 360.0, "default": 0.0},
    "speedMs": {"type": "number", "min": 0.0, "max": 14.0, "default": 0.8},
    "gustiness": {"type": "number", "min": 0.0, "max": 1.0, "default": 0.3},
    "turbulence": {"type": "number", "min": 0.0, "max": 1.0, "default": 0.2}
  },
  "physics": {"taxonomy": ["WD-01"], "state": "stateless", "touchesSubject": false, "windDriven": false},
  "subjectSizeM": [0.01, 30.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "costWeight": 1.0,
  "tierMax": "T3",
  "tags": {"mood": [], "energy": [], "palette": []}
}
```

`engine/blocks/field/wind/build.py`:

```python
"""The wind field (TAXONOMY WD-01; METHODS §2.9). Builds the shared node group `valora_wind`
(Position -> Wind, m/s) and records the params on the scene for Python consumers.

wind(p, t) = d * s * (1 + gustiness * g) + turbulence * s * h, where d is the unit direction, s the mean
speed, g in [-1, 1] a noise advected downwind at the mean speed (gust fronts travel with the air), and h a
horizontal turbulence vector in [-0.5, 0.5]^2. Its speed stays inside engine/physics/wind.envelope()
widened by turbulence * s. Time is Scene Time: no frame depends on the one before."""
from engine.physics import wind as W


def build(ctx):
    from engine.blender.gn import Tree
    p = ctx.params
    s, g, tb = p["speedMs"], p["gustiness"], p["turbulence"]
    dx, dy, _ = W.vector(p["directionDeg"], 1.0)
    ctx.scene["valora_wind"] = {"directionDeg": p["directionDeg"], "speedMs": s, "gustiness": g, "turbulence": tb}
    t = Tree("valora_wind", inputs=(("Position", "NodeSocketVector"),), outputs=(("Wind", "NodeSocketVector"),))
    pos, sec = t.input("Position"), t.time()
    d = t.vec(dx, dy, 0.0)
    offs = float(ctx.seed % 997)                                   # per-clip noise offset (METHODS R3)
    drift = t.vmath("SCALE", d, scale=t.math("MULTIPLY", sec, s))  # how far the air moved since t = 0
    q = t.vmath("SCALE", t.vmath("SUBTRACT", pos, drift), scale=1.0 / W.GUST_WAVELENGTH_M)
    fac, _ = t.noise(t.vmath("ADD", q, t.vec(offs, offs, 0.0)))
    gust = t.math("SUBTRACT", t.math("MULTIPLY", fac, 2.0), 1.0)               # [-1, 1]
    mean = t.vmath("SCALE", d, scale=t.math("MULTIPLY", s, t.math("ADD", 1.0, t.math("MULTIPLY", gust, g))))
    tq = t.vmath("SCALE", t.vmath("SUBTRACT", pos, drift), scale=1.0 / W.TURB_SCALE_M)
    _, col = t.noise(t.vmath("ADD", tq, t.vec(-offs, offs, 0.5)))
    hx, hy, _ = t.xyz(t.vmath("SUBTRACT", col, t.vec(0.5, 0.5, 0.5)))
    turb = t.vmath("SCALE", t.vec(hx, hy, 0.0), scale=tb * s)
    t.output("Wind", t.vmath("ADD", mean, turb))
    t.finish()
```

The noise Factor of Blender's Perlin noise is not exactly [0, 1]; the envelope test is the arbiter. If it
fails on the low side, clamp `gust` with `t.math("MINIMUM", t.math("MAXIMUM", gust, -1.0), 1.0)`.

`engine/blender/realism_probe.py` — add:

```python
def sample_wind(points, frame):
    """Wind vectors (m/s) of the scene's valora_wind group at points, at one frame (tests and wind_coherent)."""
    from engine.blender.gn import Tree, add_modifier
    scene = bpy.context.scene
    me = bpy.data.meshes.new("valora_wind_probe")
    me.from_pydata([tuple(p) for p in points], [], [])
    ob = bpy.data.objects.new("valora_wind_probe", me)
    scene.collection.objects.link(ob)
    t = Tree("valora_wind_probe")
    t.store("w", t.group(bpy.data.node_groups["valora_wind"], Position=t.position()).outputs["Wind"], "FLOAT_VECTOR")
    add_modifier(ob, t.finish(), "probe")
    f0 = scene.frame_current
    scene.frame_set(frame)
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    m = ev.to_mesh()
    w = np.empty(len(m.vertices) * 3)
    m.attributes["w"].data.foreach_get("vector", w)
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob, do_unlink=True)
    scene.frame_set(f0)
    return w.reshape(-1, 3).tolist()
```

`engine/blocks/effect/haze_volume/build.py` — add a drift that only exists when the wind is not calm, so
the calibrated studio look (HAZE_K, windDefault 0) is unchanged:

```python
DRIFT_DEPTH = 0.35   # density varies +/-35% in drifting wisps when there is wind (eng)
DRIFT_SCALE = 1.5    # wisp size, x the subject radius (eng)


def _drift(ctx, nt, density, centre_ob):
    """Multiply density by a noise advected downwind. Shaders have no clock, so the noise mapping's
    Location is keyed linearly over the clip (stateless per frame)."""
    import bpy
    from engine.physics import wind as W
    w = ctx.scene.get("valora_wind")
    if w is None or W.is_calm(w["speedMs"]):
        return density
    r = ctx.profile.radius
    fps, n = ctx.script["format"]["fps"], ctx.scene.frame_end
    dx, dy, _ = W.vector(w["directionDeg"], w["speedMs"])
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.object = centre_ob
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.name = "valora_haze_drift"
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    for f, k in ((1, 0.0), (n, (n - 1) / fps)):
        mp.inputs["Location"].default_value = (-dx * k, -dy * k, 0.0)
        mp.inputs["Location"].keyframe_insert("default_value", frame=f)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.0 / (DRIFT_SCALE * r)
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    mod = nt.nodes.new("ShaderNodeMapRange")
    mod.inputs["To Min"].default_value, mod.inputs["To Max"].default_value = 1.0 - DRIFT_DEPTH, 1.0 + DRIFT_DEPTH
    nt.links.new(noise.outputs["Factor"], mod.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nt.links.new(density, mul.inputs[0])
    nt.links.new(mod.outputs["Result"], mul.inputs[1])
    ctx.scene["valora_haze_drift"] = True
    from engine.blender.realism_rig import fcurves
    for c in fcurves(nt.animation_data.action):     # constant drift speed: linear keys
        for kp in c.keyframe_points:
            kp.interpolation = "LINEAR"
    return mul.outputs[0]
```

and in `build()`, just before `nt.links.new(density, vol.inputs["Density"])`:
`density = _drift(ctx, nt, density, centre_ob)`.

`engine/compiler/blender_main.py` — next to `result["wind"]`: `result["hazeDrift"] = bool(scene.get("valora_haze_drift"))`.

- [ ] **Step 4: Run, expect PASS** — the two new tests, `test_physics_applies.py` (its wind test now runs),
`test_compile_blender.py -k "studio_scene or haze"` (the calibrated haze-lift test must still pass: studio
wind is calm), then the fast loop.

- [ ] **Step 5: Commit**

```bash
git add engine/blocks/field/wind engine/blocks/effect/haze_volume/build.py engine/blender/realism_probe.py engine/compiler/blender_main.py engine/tests/test_realism_blender.py engine/tests/test_compile_blender.py
git commit -m "feat(field): one shared wind (calm by default); haze drifts with it"
```

---
## Chunk 4: The realism blocks

Every block below follows one pattern: a manifest (`kind: realism`, `alwaysOn: true`,
`directorSelectable: false`, `appliesWhen`, params with (eng) ranges, `physics` metadata), a `build.py`
that imports `bpy` inside `build()` and uses `engine/physics` for every number, a compile-probe record,
and Blender tests at ≤ 3 probed frames (no render). Every manifest ends with the same four keys, written
out in full in each file:

```json
  "subjectSizeM": [0.01, 30.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "tierMax": "T3",
  "tags": {"mood": [], "energy": [], "palette": []}
```

(`tyre_contact` and `suspension` use `"subjectSizeM": [0.1, 30.0]`.) The table is the whole set; the
resolver's `ORDER` (Task 11) is the build order.

| Block | Taxonomy | appliesWhen | Params (range, **default**) | Probe / harness |
|---|---|---|---|---|
| `contact_ground` | CD-01, CD-10 | placement ground | `occlusion` 0.5–1 **0.8**; `sinkMm` 0–30 **auto by groundType** | `grounded` · PH-02 |
| `suspension` | VD-01 | ground; wheels + bodySeparable; size 1.5–30 m | `rideHz` 0.7–2.2 **auto by class**; `damping` 0.2–0.6 **0.4**; `sagFracR` 0–0.03 **0.015** | body sag, `settle_bounded` · PH-10 (V, later) |
| `wheel_roll` | VD-02 | ground; wheelsSeparable; motion translates | none | `wheel_roll_no_slip` · PH-09 (V, later) |
| `tyre_contact` | CD-02 | ground; wheels + tyreBand | `patchLenFrac` 0.3–0.6 **0.45**; `bulgeFrac` 0.1–0.4 **0.25** | `tyre_patch_present` · PH-01 |
| `soft_rest` | CD-03 | ground; softGround | `sinkFrac` 0.02–0.15 **0.06**; `bulgeFrac` 0–0.4 **0.2** | `grounded`, footprint · PH-02 |
| `landing_settle` | SF-05, RB-01, CD-04 | ground; motion stops/lands; not wheels | `overshootFrac` 0.02–0.10 **0.05**; `settleS` 0.15–0.6 **0.3**; `squash` 0.8–1 **auto: 0.92 soft / 1.0 rigid** | `settle_bounded` · PH-09 (V, later) |
| `dangling_sway` | SC-08, SF-02, SF-03 | danglingParts | `stiffness` 0–1 **0.4**; `flutter` 0–1 **0.3** | `wind_coherent` · PH-06 (dense frames, later) |
| `foliage_sway` | HF-01..03 | world hasFoliage | `stiffness` 0–1 **0.5**; `flutter` 0–1 **0.5** | `wind_coherent` · PH-06 (later) |
| `ground_conform` | CD-07, HF-06 (static) | ground; world hasFoliage | `leanFrac` 0–1 **0.5** | foliage never inside the subject |
| `shaft_dust` | PT-01, LM-03 | effect haze_volume | `density` 0–1 **0.2** | `no_particles_in_subject` · PH-03 [C] |
| `glass_caustics` | LM-01 | ground; glass share ≥ 0.05 | none | flags set · PH-11 cost |

`rollDegPerG` (VD-04/05 body roll) and the spoke-strobe guard (VD-02, vehicles.md V-M01) need a
driven path with curvature and a spoke count: they land with phase-5 `drive` (Deferred).

### Task 14: `contact_ground` — contact occlusion and ground sink (+ the test lawn world)

**Files:**
- Create: `engine/blocks/realism/contact_ground/{block.json,build.py}`,
  `engine/tests/fixtures/blocks/world/test_lawn/{block.json,build.py}`
- Modify: `engine/blocks/world/studio_cyc/build.py` (tag the floor), `engine/tests/test_realism_blender.py`,
  `engine/tests/test_compile_blender.py` (`built` gains `realism:contact_ground`),
  `engine/tests/test_realism.py` (Task 12a's tests assumed no shipped always-on block)

- [ ] **Step 1: Write the failing tests** — append to `engine/tests/test_realism_blender.py`:

```python
from engine.physics import probes


def test_contact_ground_grounds_the_subject_and_darkens_the_floor(tmp_path):
    res = _compile("toycar", tmp_path)
    assert "contact_ground" in res["realism"] and "realism:contact_ground" in res["built"]
    assert res["realismScene"]["contact_ao_materials"] >= 1 and res["realismScene"]["sink_m"] == 0.0
    assert res["realismScene"]["contact_ao_links_ok"]              # every AO link valid (Mix colour sockets)
    assert probes.grounded_ok(res["realismProbe"]["1"], 0.0)


def test_soft_ground_sinks_the_subject(tmp_path):
    cat = catalog_with_fixtures(tmp_path)
    s = _script(world={"id": "test_lawn", "params": {}})
    res = _compile("toycar", tmp_path / "c", script=s, catalog=cat)
    sink = res["realismScene"]["sink_m"]
    assert sink == pytest.approx(min(0.012, 0.1 * _profile("toycar").sizeM[2]), rel=1e-4)
    rec = res["realismProbe"]["1"]
    assert probes.grounded_ok(rec, sink) and rec["minZ"] < -0.5 * sink
```

Append to `engine/tests/test_physics_applies.py` (shipped catalog now):

```python
def test_every_ground_subject_gets_contact_ground():
    cat = Catalog.load()
    for name in ("toycar", "pocket_watch", "sports_car"):
        r = check(_script(), _p(name), cat)
        assert r.ok and _ids(r.script)[0] == "contact_ground"


def test_auto_params_cover_every_manifest():
    from engine.physics.applies import AUTO
    cat = Catalog.load()
    for bid in cat.ids("realism"):
        if cat.get("realism", bid).get("autoParams"):
            assert bid in AUTO, bid
    assert set(cat.ids("realism")) <= set(ORDER)
```

In `engine/tests/test_realism.py` (Task 12a), the shipped catalog now has always-on blocks, and Task 15
will ship `realism/tyre_contact`, which collides with the fixture folder `_catalog_with_contact` creates:
- in `_catalog_with_contact`, rename the fixture block to `test_tyre_contact` (folder and `id`), and in
  every test compare only that entry, e.g.
  `assert [r for r in realism_defaults(_p("sports_car"), cat) if r["id"] == "test_tyre_contact"] == [{"kind": "effect", "id": "test_tyre_contact", "params": {}}]`
  (the kind-`realism` variant expects `{"kind": "realism", "id": "test_tyre_contact", "params": {}}`), the
  same filter for `pocket_watch` (`== []`), and `"test_tyre_contact" not in cat.selectable_ids("effect")`;
- replace `test_the_shipped_catalog_has_no_always_on_block_yet` with

```python
def test_every_shipped_always_on_block_is_a_realism_block():
    assert {k for k, _ in Catalog.load().always_on()} <= {"realism"}
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement.**

`engine/blocks/world/studio_cyc/build.py` — in `build()`, after the cyc object is created:
`ob["valora_ground"] = True  # realism: contact occlusion and caustics receive on this floor`.

`engine/blocks/realism/contact_ground/block.json`:

```json
{
  "id": "contact_ground",
  "kind": "realism",
  "alwaysOn": true,
  "directorSelectable": false,
  "description": "Grounds the subject: a tight contact-occlusion seam where it meets the floor, and a small settle into soft ground (grass, sand, snow, rug). Added to every subject standing on the ground.",
  "capabilities": ["contact.ground"],
  "appliesWhen": {"placement": ["ground"]},
  "autoParams": ["sinkMm"],
  "params": {
    "occlusion": {"type": "number", "min": 0.5, "max": 1.0, "default": 0.8},
    "sinkMm": {"type": "number", "min": 0.0, "max": 30.0, "default": 0.0}
  },
  "physics": {"taxonomy": ["CD-01", "CD-10"], "state": "stateless", "touchesSubject": true, "windDriven": false},
  "costWeight": 1.05,
  "subjectSizeM": [0.01, 30.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "tierMax": "T3",
  "tags": {"mood": [], "energy": [], "palette": []}
}
```

`engine/blocks/realism/contact_ground/build.py`:

```python
"""Contact shadow + occlusion and ground sink (TAXONOMY CD-01, CD-10; METHODS §2.1 CD-01).

Cycles already casts the subject's shadow on the floor. This adds ray-traced contact occlusion to every
ground material (valora_ground): the Ambient Occlusion shader node darkens the floor where the subject is
within ao_distance (5% of its height), giving the tight dark seam that separates grounded from pasted
(TIERS T1-X2). It also lowers the subject into soft ground by sinkMm through the realism offset.
No decal: a decal is only for worlds without a floor (METHODS CD-01)."""
from engine.physics import contact


def build(ctx):
    import bpy
    from engine.blender.realism_rig import ground_objects, record, rig
    p = ctx.params
    _, offset = rig()
    sink = p["sinkMm"] / 1000.0
    offset.location.z -= sink
    dist = contact.ao_distance(ctx.profile.sizeM[2])
    done = set()
    for ob in ground_objects():
        for slot in ob.material_slots:
            mat = slot.material
            if mat is None or mat.name in done or not mat.use_nodes:
                continue
            nt = mat.node_tree
            bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if bsdf is None:
                continue
            done.add(mat.name)
            base = bsdf.inputs["Base Color"]
            ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
            ao.name, ao.only_local, ao.samples = "valora_contact_ao", False, 16
            ao.inputs["Distance"].default_value = dist
            mix = nt.nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            # ShaderNodeMix has float, vector and colour sockets with the same names; name lookup returns
            # the (hidden) float ones, so pick the colour sockets by identifier.
            sock = lambda coll, ident: next(x for x in coll if x.identifier == ident)
            fac, a, b = sock(mix.inputs, "Factor_Float"), sock(mix.inputs, "A_Color"), sock(mix.inputs, "B_Color")
            fac.default_value = p["occlusion"]
            if base.is_linked:
                src = base.links[0].from_socket
                nt.links.new(src, ao.inputs["Color"])
                nt.links.new(src, a)
            else:
                ao.inputs["Color"].default_value = base.default_value
                a.default_value = base.default_value
            nt.links.new(ao.outputs["Color"], b)                      # AO-modulated colour
            nt.links.new(sock(mix.outputs, "Result_Color"), base)
    record("sink_m", sink)
    record("contact_ao_materials", len(done))
    record("contact_ao_links_ok", all(l.is_valid for n in done for l in bpy.data.materials[n].node_tree.links))
    record("contact_ao_distance_m", dist)
```

`engine/tests/fixtures/blocks/world/test_lawn/block.json`:

```json
{
  "id": "test_lawn",
  "kind": "world",
  "description": "TEST ONLY. A flat lawn: a ground plane tagged valora_ground and a ring of grass blades tagged valora_foliage with valora_sway (0 root .. 1 tip) and valora_sway_len (metres). A light breeze by default.",
  "directorSelectable": false,
  "capabilities": [],
  "hasGround": true,
  "groundType": "grass",
  "hasFoliage": true,
  "windDefault": 2.0,
  "params": {},
  "subjectSizeM": [0.02, 30.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "costWeight": 1.0,
  "tierMax": "T3",
  "tags": {"mood": [], "energy": [], "palette": []}
}
```

`engine/tests/fixtures/blocks/world/test_lawn/build.py`:

```python
"""TEST ONLY: ground plane + 400 real-size grass blades in a ring around the subject (never inside its
bounds + 20%). Blades are separate triangles (islands) carrying the foliage contract attributes."""
import math

BLADE_H, BLADE_W = 0.12, 0.012   # real grass: 12 cm tall, 1.2 cm wide at the root (scale cue, never scaled)


def build(ctx):
    import bpy
    import numpy as np
    from engine.blender.realism_rig import FOLIAGE_TAG, GROUND_TAG, SWAY, SWAY_LEN, write_attr
    prof, rng = ctx.profile, ctx.rng
    size = 40.0 * prof.longest
    me = bpy.data.meshes.new("test_lawn_ground")
    me.from_pydata([(-size, -size, 0), (size, -size, 0), (size, size, 0), (-size, size, 0)], [], [(0, 1, 2, 3)])
    ground = bpy.data.objects.new("test_lawn_ground", me)
    ctx.scene.collection.objects.link(ground)
    ground[GROUND_TAG] = True
    gm = bpy.data.materials.new("test_lawn_soil")
    gm.use_nodes = True
    ground.data.materials.append(gm)
    r_in = 1.2 * max(prof.half[0], prof.half[1])
    verts, faces, sway, length = [], [], [], []
    for i in range(400):
        a, rr = rng.uniform(0, 2 * math.pi), rng.uniform(r_in, r_in + 2.0 * prof.longest + 0.5)
        x, y = rr * math.cos(a), rr * math.sin(a)
        k = len(verts)
        verts += [(x - BLADE_W / 2, y, 0.0), (x + BLADE_W / 2, y, 0.0), (x, y, BLADE_H)]
        faces.append((k, k + 1, k + 2))
        sway += [0.0, 0.0, 1.0]
        length += [BLADE_H] * 3
    bm = bpy.data.meshes.new("test_lawn_grass")
    bm.from_pydata(verts, [], faces)
    grass = bpy.data.objects.new("test_lawn_grass", bm)
    ctx.scene.collection.objects.link(grass)
    grass[FOLIAGE_TAG] = True
    write_attr(grass, SWAY, np.array(sway), "FLOAT")
    write_attr(grass, SWAY_LEN, np.array(length), "FLOAT")
    world = bpy.data.worlds.new("test_lawn_sky")
    world.use_nodes = True
    ctx.scene.world = world
```

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests/test_realism_blender.py -q -m blender -k "contact or soft_ground or rig"`,
`py -m pytest engine/tests/test_compile_blender.py -q -m blender -k studio_scene`, and the fast loop
(`test_physics_applies.py`, `test_realism.py`, `test_blocks_complete.py`).

- [ ] **Step 5: Commit**

```bash
git add engine/blocks/realism/contact_ground engine/blocks/world/studio_cyc/build.py engine/tests/fixtures/blocks/world/test_lawn engine/tests/test_realism_blender.py engine/tests/test_physics_applies.py engine/tests/test_compile_blender.py engine/tests/test_realism.py
git commit -m "feat(realism): contact_ground - contact occlusion on every ground and sink into soft ground"
```

---

### Task 15: `tyre_contact` — the loaded-tyre patch (sports_car is the test subject)

**Files:**
- Create: `engine/blocks/realism/tyre_contact/{block.json,build.py}`
- Modify: `engine/tests/test_realism_blender.py`, `engine/tests/test_physics_applies.py`

- [ ] **Step 1: Write the failing tests** — append to `engine/tests/test_realism_blender.py`:

```python
from engine.ingest.run import ingest
from engine.tests.blender_fixtures import make_glb


def _wheeled(tmp_path):
    glb = make_glb("wheeled", tmp_path / "wheeled.glb")
    return glb, ingest(glb, workdir=tmp_path / "ingest")


def _patches_ok(res, prof, frame="1", patch=0.45):
    rec = res["realismProbe"][frame]
    assert len(rec["tyres"]) == len(prof.wheels), rec
    for i, w in enumerate(prof.wheels):
        t = rec["tyres"][str(i)]
        assert probes.tyre_patch_ok(t, w["radius"], patch, 0.0), (i, t, patch * w["radius"])
    assert probes.grounded_ok(rec, 0.0)


def test_tyres_on_the_wheeled_fixture_have_flat_patches(tmp_path):
    glb, prof = _wheeled(tmp_path)
    res = compile_scene(_script(), prof, glb, tmp_path / "c", render=False, skip_kinds=("grade",),
                        realism_probe=[1])
    assert "tyre_contact" in res["realism"] and res["realismScene"]["tyre_objects"] >= 4
    assert res["realismScene"]["tyre_d_m"] == pytest.approx(0.45 ** 2 * 0.35 / 8, rel=0.1)
    _patches_ok(res, prof)


def test_sports_car_tyres_have_flat_patches(tmp_path):
    res = _compile("sports_car", tmp_path, frames=(1,))
    assert "tyre_contact" in res["realism"]
    _patches_ok(res, _profile("sports_car"))
```

Append to `engine/tests/test_physics_applies.py`:

```python
def test_only_the_wheeled_subject_gets_tyre_contact():
    cat = Catalog.load()
    assert "tyre_contact" in _ids(check(_script(), _p("sports_car"), cat).script)
    for name in ("toycar", "pocket_watch", "sneaker", "camera_01"):
        assert "tyre_contact" not in _ids(check(_script(), _p(name), cat).script), name
    assert "sim.tyre_contact" in cat.capabilities(_p("sports_car"))          # phase-3 contract: delivered
    assert "sim.tyre_contact" not in cat.capabilities(_p("pocket_watch"))
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement.**

`engine/blocks/realism/tyre_contact/block.json`:

```json
{
  "id": "tyre_contact",
  "kind": "realism",
  "alwaysOn": true,
  "directorSelectable": false,
  "description": "Loaded tyres: a flat contact patch where each tyre meets the ground and a slight sidewall bulge; the vehicle sits down by the tyre deflection. Added to every wheeled subject on the ground.",
  "capabilities": ["sim.tyre_contact", "contact.tyre"],
  "requiresProfile": "wheels",
  "appliesWhen": {"placement": ["ground"], "profile": ["wheels", "tyreBand"]},
  "params": {
    "patchLenFrac": {"type": "number", "min": 0.3, "max": 0.6, "default": 0.45},
    "bulgeFrac": {"type": "number", "min": 0.1, "max": 0.4, "default": 0.25}
  },
  "physics": {"taxonomy": ["CD-02"], "state": "stateless", "touchesSubject": true, "windDriven": false},
  "costWeight": 1.0,
  "subjectSizeM": [0.1, 30.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "tierMax": "T3",
  "tags": {"mood": [], "energy": [], "palette": []}
}
```

`engine/blocks/realism/tyre_contact/build.py`:

```python
"""Loaded tyres (TAXONOMY CD-02; METHODS §2.1 M-GND). The whole vehicle drops by the tyre deflection d
(realism offset); every tyre-band vertex below the ground is clamped onto it (the flat patch) and the low
sidewall bulges along the axle: engine/physics/tyre.deform, written in nodes. The modifier is stacked after
wheel_roll's, so a rolling wheel keeps its patch at the bottom (METHODS CD-02)."""
from engine.physics import tyre as T
from engine.physics.wheel_mask import half_width


def _axis(w):
    ai = max(range(3), key=lambda k: abs(w["axis"][k]))
    return ai, tuple(1.0 if k == ai else 0.0 for k in range(3))


def build(ctx):
    from engine.blender import gn
    from engine.blender.realism_rig import TYRE, record, rig, tag_wheels
    p, prof = ctx.params, ctx.profile
    _, offset = rig()
    counts = tag_wheels(ctx.meshes, prof.wheels)
    r_med = sorted(w["radius"] for w in prof.wheels)[len(prof.wheels) // 2]
    d = T.deflection(r_med, p["patchLenFrac"])     # one drop for the car (per-axle loads: later, eng)
    offset.location.z -= d
    sink = float(ctx.scene.get("valora_rz_sink_m", 0.0))
    t = gn.Tree("valora_rz_tyre_contact")
    P, back = gn.placed(t, offset)
    ground = gn.ground_in_placed(t, offset, -sink)   # tyres flatten on the hard layer under soft cover
    tag = t.attr(TYRE)
    new = P
    for i, w in enumerate(prof.wheels):
        ai, axis = _axis(w)
        comps = t.xyz(new)
        z2 = t.math("MAXIMUM", comps[2], ground)
        h = t.math("SUBTRACT", z2, ground)
        k = t.math("MULTIPLY", p["bulgeFrac"] * T.deflection(w["radius"], p["patchLenFrac"]),
                   t.math("SUBTRACT", 1.0, t.smoothstep(0.0, T.BULGE_FALLOFF * w["radius"], h)))
        axial = t.math("SUBTRACT", comps[ai], w["center"][ai])
        side = t.math("MINIMUM", 1.0, t.math("DIVIDE", t.math("ABSOLUTE", axial), half_width(w)))
        push = t.math("MULTIPLY", t.math("MULTIPLY", k, side), t.math("SIGN", axial))
        moved = t.vmath("ADD", t.vec(comps[0], comps[1], z2), t.vmath("SCALE", t.vec(*axis), scale=push))
        new = t.switch_vec(t.equals(tag, i + 1), new, moved)
    t.set_position(back(new))
    ng = t.finish()
    n = 0
    for o in ctx.meshes:
        if o.data.attributes.get(TYRE) is not None:
            gn.add_modifier(o, ng, "valora_rz_tyre_contact")
            n += 1
    record("tyre_d_m", d)
    record("tyre_objects", n)
    record("tyre_tagged_verts", counts["tyre"])
```

- [ ] **Step 4: Run, expect PASS** — the two new Blender tests and the fast loop. If a patch is short on
the fixture, check the tyre tessellation first (64 × 16 segments: a 0.157 m patch spans ~4.5 segments of
3.4 cm, so the vertex-extent reads up to one segment short); widen `PATCH_TOL` only with the measured
numbers written into the calibration register, never silently. If `sports_car` fails, print
`res["realismProbe"]` and `res["realismScene"]` and compare `tyre_tagged_verts` to the tyre vertex count
you expect before touching any constant.

- [ ] **Step 5: Commit**

```bash
git add engine/blocks/realism/tyre_contact engine/tests/test_realism_blender.py engine/tests/test_physics_applies.py
git commit -m "feat(realism): tyre_contact - flat contact patch and sidewall bulge on every grounded wheel"
```

---

### Task 16: `suspension` — static sag and settle after a stop or landing

**Files:**
- Create: `engine/blocks/realism/suspension/{block.json,build.py}`
- Modify: `engine/blender/realism_probe.py` (body/unsprung heights, drivers, offset), `engine/tests/test_realism_blender.py`

- [ ] **Step 1: Write the failing tests** — append to `engine/tests/test_realism_blender.py`:

```python
def _pin(script, bid, **params):
    s = json.loads(json.dumps(script))
    s["realism"] = [{"kind": "realism", "id": bid, "params": params}]
    return s


def test_the_body_sits_on_its_springs(tmp_path):
    glb, prof = _wheeled(tmp_path)
    a = compile_scene(_pin(_script(), "suspension", sagFracR=0.0), prof, glb, tmp_path / "a", render=False,
                      skip_kinds=("grade",), realism_probe=[1])
    b = compile_scene(_script(), prof, glb, tmp_path / "b", render=False, skip_kinds=("grade",), realism_probe=[1])
    gap = lambda r: r["realismProbe"]["1"]["bodyMeanZ"] - r["realismProbe"]["1"]["unsprungMeanZ"]
    assert gap(a) - gap(b) == pytest.approx(0.015 * 0.35, rel=0.15)     # sagFracR x r
    assert probes.grounded_ok(b["realismProbe"]["1"], 0.0)                # the wheels never leave the ground


def test_the_body_pitches_and_settles_after_a_stop(tmp_path):
    glb, prof = _wheeled(tmp_path)
    cat = catalog_with_fixtures(tmp_path)
    s = _script("test_slide_stop")
    res = compile_scene(s, prof, glb, tmp_path / "c", render=False, skip_kinds=("grade",), catalog=cat,
                        realism_probe=[1])
    stop = res["motionEvents"]["stops"][0]["frame"]
    res = compile_scene(s, prof, glb, tmp_path / "d", render=False, skip_kinds=("grade",), catalog=cat,
                        realism_probe=[stop, stop + 4, 90])
    body = lambda f: res["realismProbe"][str(f)]["drivers"]["valora_rz_body"][0]
    assert abs(body(stop)) > 0.0 and abs(body(stop + 4)) > 0.0
    assert abs(body(90)) < 0.05 * abs(body(stop))                         # settled by the end
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement.**

`engine/blocks/realism/suspension/block.json`:

```json
{
  "id": "suspension",
  "kind": "realism",
  "alwaysOn": true,
  "directorSelectable": false,
  "description": "A car body sits slightly down on its springs, and after it stops or lands it dips and settles with one or two damped bounces at its ride frequency. The wheels stay planted. Added to real-size vehicles whose body and wheels are separate pieces.",
  "capabilities": ["vehicle.suspension"],
  "requiresProfile": "wheels",
  "appliesWhen": {"placement": ["ground"], "profile": ["wheels", "bodySeparable"], "sizeM": [1.5, 30.0]},
  "autoParams": ["rideHz"],
  "params": {
    "rideHz": {"type": "number", "min": 0.7, "max": 2.2, "default": 1.3},
    "damping": {"type": "number", "min": 0.2, "max": 0.6, "default": 0.4},
    "sagFracR": {"type": "number", "min": 0.0, "max": 0.03, "default": 0.015}
  },
  "physics": {"taxonomy": ["VD-01"], "state": "stateless", "touchesSubject": true, "windDriven": false},
  "costWeight": 1.0,
  "subjectSizeM": [0.1, 30.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "tierMax": "T3",
  "tags": {"mood": [], "energy": [], "palette": []}
}
```

The wheeled fixture is 4.0 m long, so it passes the 1.5 m size gate; the `toycar` never does.

`engine/blocks/realism/suspension/build.py`:

```python
"""Body on springs (TAXONOMY VD-01; METHODS §2.2 M-KIN). Every vertex outside the wheel boxes
(valora_unsprung == 0) is the body: it sits sagFracR x r lower, and after each stop it pitches (the braking
dive released into damped bounces), after each landing it heaves (engine/physics/suspension). Per-frame
values are keyed on the valora_rz_body driver (location.x = pitch in radians, location.z = heave in metres);
the node tree rotates the body about the wheelbase centre at axle height, about the axis across the car."""
import math

from engine.physics import events, suspension as S

SETTLE_WINDOW_S = 2.0   # keys after each event (1-2 bounces at >= 0.7 Hz fit; eng)


def build(ctx):
    from engine.blender import gn
    from engine.blender.realism_rig import UNSPRUNG, driver, key_series, motion_track, record, rig, tag_wheels
    p, prof, scene = ctx.params, ctx.profile, ctx.scene
    fps, n = ctx.script["format"]["fps"], scene.frame_end
    _, offset = rig()
    tag_wheels(ctx.meshes, prof.wheels)
    r = sorted(w["radius"] for w in prof.wheels)[len(prof.wheels) // 2]
    sag = S.static_sag(r, p["sagFracR"])
    fwd = (prof.vehicle or {}).get("forwardAxis", [0.0, 1.0, 0.0])
    pos, yaw = motion_track(scene)
    pitch, heave = [0.0] * n, [-sag] * n
    for e in events.stops(pos, fps, prof.longest):
        c, s = math.cos(yaw[e["frame"] - 1]), math.sin(yaw[e["frame"] - 1])
        ahead = 1.0 if e["dir"][0] * (c * fwd[0] - s * fwd[1]) + e["dir"][1] * (s * fwd[0] + c * fwd[1]) >= 0 else -1.0
        for f in range(e["frame"], min(n, e["frame"] + int(SETTLE_WINDOW_S * fps)) + 1):
            pitch[f - 1] += ahead * S.pitch_after_stop((f - e["frame"]) / fps, e["decelMs2"], p["rideHz"], p["damping"])
    for e in events.landings(pos, fps, prof.longest):
        for f in range(e["frame"], min(n, e["frame"] + int(SETTLE_WINDOW_S * fps)) + 1):
            heave[f - 1] += S.heave_after_landing((f - e["frame"]) / fps, e["impactMs"], p["rideHz"], p["damping"], 0.3 * r)
    drv = driver("valora_rz_body")
    frames = list(range(1, n + 1))
    key_series(drv, "location", 0, frames, pitch)
    key_series(drv, "location", 2, frames, heave)
    cs = [w["center"] for w in prof.wheels]
    pivot = [sum(c[k] for c in cs) / len(cs) for k in range(3)]
    across = (fwd[1], -fwd[0], 0.0)                 # forward x up: nose-down pitch is a negative turn about it
    t = gn.Tree("valora_rz_suspension")
    P, back = gn.placed(t, offset)
    lx, _, lz = t.xyz(t.object_location(drv))
    piv = t.vec(*pivot)
    turned = t.vmath("ADD", t.rotate(t.vmath("SUBTRACT", P, piv), t.vec(*across), t.math("MULTIPLY", lx, -1.0)), piv)
    body = t.vmath("ADD", turned, t.vec(0.0, 0.0, lz))
    t.set_position(back(body), selection=t.equals(t.attr(UNSPRUNG), 0.0))
    ng = t.finish()
    for o in ctx.meshes:
        gn.add_modifier(o, ng, "valora_rz_suspension")
    record("suspension_sag_m", sag)
    record("suspension_peak_pitch_rad", max((abs(v) for v in pitch), default=0.0))
```

`engine/blender/realism_probe.py` — inside the per-frame mesh loop, also accumulate body and unsprung
heights (a mesh without the attribute is all body):

```python
                u = me.attributes.get(UNSPRUNG)
                un = np.zeros(len(me.vertices), np.int32)
                if u is not None:
                    u.data.foreach_get("value", un)
                acc["body"] += co[un == 0, 2].sum(); acc["nb"] += int((un == 0).sum())
                acc["uns"] += co[un > 0, 2].sum(); acc["nu"] += int((un > 0).sum())
```
(initialise `acc = {"body": 0.0, "nb": 0, "uns": 0.0, "nu": 0}` per frame, import `UNSPRUNG`), and add to
`rec`:

```python
        rec["bodyMeanZ"] = acc["body"] / acc["nb"] if acc["nb"] else None
        rec["unsprungMeanZ"] = acc["uns"] / acc["nu"] if acc["nu"] else None
        rec["drivers"] = {o.name: list(o.location) for o in scene.objects if o.name.startswith("valora_rz_")}
        _, offset = rig()
        rec["offset"] = {"loc": list(offset.location), "scale": list(offset.scale)}
```

- [ ] **Step 4: Run, expect PASS** — the two new tests, then the fast loop.

- [ ] **Step 5: Commit**

```bash
git add engine/blocks/realism/suspension engine/blender/realism_probe.py engine/tests/test_realism_blender.py
git commit -m "feat(realism): suspension - static sag and damped settle after stops and landings"
```

---

### Task 17: `wheel_roll` — wheel spin matched to the subject's speed (ready for phase-5 drive)

Nothing that ships in this phase moves the subject, so the block qualifies only with the test
`test_slide_stop` motion; phase 5's `drive` sets `subjectMotion.translates` and gets it for free.

**Files:**
- Create: `engine/blocks/realism/wheel_roll/{block.json,build.py}`
- Modify: `engine/tests/test_realism_blender.py`, `engine/tests/test_physics_applies.py`

- [ ] **Step 1: Write the failing tests.**

`engine/tests/test_realism_blender.py`:

```python
def test_wheels_roll_without_slipping_and_keep_their_patch(tmp_path):
    glb, prof = _wheeled(tmp_path)
    cat = catalog_with_fixtures(tmp_path)
    s = _script("test_slide_stop")
    res = compile_scene(s, prof, glb, tmp_path / "c", render=False, skip_kinds=("grade",), catalog=cat,
                        realism_probe=[1, 30, 90])
    assert "wheel_roll" in res["realism"] and res["realismScene"]["wheel_slip"] < 0.02
    ang = lambda f, i: res["realismProbe"][str(f)]["drivers"][f"valora_rz_wheel_{i}"][0]
    travelled = 0.3 * prof.longest                                # test_slide_stop distanceFrac default
    assert abs(ang(90, 0) - ang(1, 0)) * prof.wheels[0]["radius"] == pytest.approx(travelled, rel=0.03)
    _patches_ok(res, prof, frame="30")                            # mid-roll: the patch is still at the bottom
```

`engine/tests/test_physics_applies.py`:

```python
def test_wheel_roll_needs_a_moving_subject():
    cat = Catalog.load()
    assert "wheel_roll" not in _ids(check(_script(), _p("sports_car"), cat).script)   # static
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement.**

`engine/blocks/realism/wheel_roll/block.json` — keys as the pattern, with:
`"id": "wheel_roll"`, description `"Wheels turn exactly as fast as the subject travels (no sliding, no wagon-wheel spin). Added whenever a wheeled subject with separate wheels moves."`,
`"capabilities": []`, `"requiresProfile": "wheels"`,
`"appliesWhen": {"placement": ["ground"], "profile": ["wheelsSeparable"], "motion": ["translates"]}`,
`"params": {}`, `"physics": {"taxonomy": ["VD-02"], "state": "stateless", "touchesSubject": true, "windDriven": false}`,
`"costWeight": 1.0`, `"subjectSizeM": [0.1, 30.0]`.

`engine/blocks/realism/wheel_roll/build.py`:

```python
"""Wheel spin from the path (TAXONOMY VD-02; METHODS §2.2 M-KIN): omega = (z x v) / r about each axle
(engine/physics/wheel_spin). The angle per frame is keyed on valora_rz_wheel_<i> (location.x, radians);
the node tree turns every spin-safe island (valora_spin, round and on the axle) about its axle.
Calipers and anything off-axis never spin. Stacked before tyre_contact (resolver ORDER)."""
from engine.physics import wheel_spin as WS


def build(ctx):
    from engine.blender import gn
    from engine.blender.realism_rig import SPIN, driver, key_series, motion_track, record, rig, tag_wheels
    prof, scene = ctx.profile, ctx.scene
    _, offset = rig()
    tag_wheels(ctx.meshes, prof.wheels)
    pos, yaw = motion_track(scene)
    frames = list(range(1, scene.frame_end + 1))
    t = gn.Tree("valora_rz_wheel_roll")
    P, back = gn.placed(t, offset)
    tag, new, slips = t.attr(SPIN), P, []
    for i, w in enumerate(prof.wheels):
        ang = WS.wheel_angles(pos, yaw, w["axis"], w["radius"])
        slips.append(WS.slip(ang, pos, w["radius"]))
        drv = driver(f"valora_rz_wheel_{i}")
        key_series(drv, "location", 0, frames, ang)
        c = t.vec(*w["center"])
        turn = t.xyz(t.object_location(drv))[0]
        spun = t.vmath("ADD", t.rotate(t.vmath("SUBTRACT", P, c), t.vec(*w["axis"]), turn), c)
        new = t.switch_vec(t.equals(tag, i + 1), new, spun)
    t.set_position(back(new))
    ng = t.finish()
    for o in ctx.meshes:
        a = o.data.attributes.get(SPIN)
        if a is not None:
            gn.add_modifier(o, ng, "valora_rz_wheel_roll")
    record("wheel_slip", max(slips, default=0.0))
```

`slip()` compares rolled distance with the straight-line path; `test_slide_stop` is straight, so
`wheel_slip` stays ~0. Curved phase-5 paths need a curvature-aware slip (hand-off H5).

- [ ] **Step 4: Run, expect PASS** — the new tests, then the fast loop.

- [ ] **Step 5: Commit**

```bash
git add engine/blocks/realism/wheel_roll engine/tests/test_realism_blender.py engine/tests/test_physics_applies.py
git commit -m "feat(realism): wheel_roll - wheels turn at the subject's speed, patch stays planted"
```

---

### Task 18: `landing_settle` — overshoot after a stop, squash after a landing (soft goods squash)

**Files:**
- Create: `engine/blocks/realism/landing_settle/{block.json,build.py}`
- Modify: `engine/physics/applies.py` (`AUTO["landing_settle"]`), `engine/tests/test_realism_blender.py`,
  `engine/tests/test_physics_applies.py`

- [ ] **Step 1: Write the failing tests.**

`engine/tests/test_physics_applies.py`:

```python
def test_landing_settle_squashes_only_soft_subjects_and_never_vehicles(tmp_path):
    cat = catalog_with_fixtures(tmp_path)
    s = _script()
    s["subject"]["motion"] = {"id": "test_drop", "params": {}}
    soft = check(s, _p("sneaker"), cat).script["realism"]
    rigid = check(s, _p("pocket_watch"), cat).script["realism"]
    car = check(s, _p("sports_car"), cat).script.get("realism", [])
    get = lambda rs: next(r for r in rs if r["id"] == "landing_settle")["params"]["squash"]
    assert get(soft) == 0.92 and get(rigid) == 1.0
    assert "landing_settle" not in [r["id"] for r in car]
```

(import `catalog_with_fixtures` from `engine.tests.realism_catalog`; this assumes Task 7 pinned
`sneaker` as the high-confidence soft subject — if it pinned another, use that one.)

`engine/tests/test_realism_blender.py`:

```python
def test_a_stop_overshoots_once_and_settles(tmp_path):
    cat = catalog_with_fixtures(tmp_path)
    s = _script("test_slide_stop")
    first = _compile("toycar", tmp_path / "a", script=s, catalog=cat)
    stop = first["motionEvents"]["stops"][0]["frame"]
    res = _compile("toycar", tmp_path / "b", script=s, catalog=cat, frames=(stop, stop + 3, 90))
    off = lambda f: res["realismProbe"][str(f)]["offset"]["loc"]
    ax = 0 if _profile("toycar").sizeM[0] >= _profile("toycar").sizeM[1] else 1
    assert abs(off(stop + 3)[ax]) > 0.0 and abs(off(90)[ax]) < 1e-4


def test_a_soft_subject_squashes_on_landing(tmp_path):
    glb = make_glb("plush", tmp_path / "plush.glb")
    prof = ingest(glb, workdir=tmp_path / "i")
    cat = catalog_with_fixtures(tmp_path)
    s = _script("test_drop")
    first = compile_scene(s, prof, glb, tmp_path / "a", render=False, skip_kinds=("grade",), catalog=cat)
    land = first["motionEvents"]["landings"][0]["frame"]
    res = compile_scene(s, prof, glb, tmp_path / "b", render=False, skip_kinds=("grade",), catalog=cat,
                        realism_probe=[land, 90])
    sc = lambda f: res["realismProbe"][str(f)]["offset"]["scale"]
    assert sc(land)[2] == pytest.approx(0.92, abs=0.01) and sc(land)[0] > 1.0
    assert sc(90)[2] == pytest.approx(1.0, abs=1e-3)
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement.**

`engine/physics/applies.py` — add to `AUTO`:

```python
def _auto_landing(profile, s, world):
    return {"squash": 0.92 if facts(profile)["softParts"][0] else 1.0}   # CD-04: soft goods squash 5-15%


AUTO["landing_settle"] = _auto_landing
```

`engine/blocks/realism/landing_settle/block.json` — the pattern keys with `"id": "landing_settle"`,
description `"When the subject stops it overshoots a touch and settles; when it lands it gives a little and recovers (soft goods squash, rigid ones do not). Added to every subject motion that stops or lands, except vehicles (their suspension does this)."`,
`"capabilities": ["secondary.follow_through"]`,
`"appliesWhen": {"placement": ["ground"], "motion": ["stops", "lands"], "profileNot": ["wheels"]}`,
`"autoParams": ["squash"]`, params
`{"overshootFrac": {"type": "number", "min": 0.02, "max": 0.1, "default": 0.05}, "settleS": {"type": "number", "min": 0.15, "max": 0.6, "default": 0.3}, "squash": {"type": "number", "min": 0.8, "max": 1.0, "default": 1.0}}`,
`"physics": {"taxonomy": ["SF-05", "RB-01", "CD-04"], "state": "stateless", "touchesSubject": true, "windDriven": false}`,
`"costWeight": 1.0`.

`engine/blocks/realism/landing_settle/build.py`:

```python
"""Overshoot-and-settle after a stop, squash-and-recover after a landing (TAXONOMY SF-05, RB-01, CD-04;
products.md P-M01). Keyed on the realism offset, so it adds to whatever the motion block does. The
subject is centred on the offset's origin in x/y and stands on z = 0, so scaling the offset squashes
it about its own footprint."""
import math

from engine.physics import events, settle


def build(ctx):
    from engine.blender.realism_rig import key_series, motion_track, record, rig
    p, prof, scene = ctx.params, ctx.profile, ctx.scene
    fps, n = ctx.script["format"]["fps"], scene.frame_end
    _, offset = rig()
    pos, _ = motion_track(scene)
    x0, y0 = offset.location.x, offset.location.y
    ox, oy, sz = [x0] * n, [y0] * n, [1.0] * n
    window = int(1.5 * p["settleS"] * fps) + 1
    v = events.speeds(pos, fps)
    thr = events.MOVE_FRAC * prof.longest
    stops = events.stops(pos, fps, prof.longest)
    for e in stops:
        i = e["frame"] - 1
        j = i - 1
        while j > 0 and v[j] > thr:
            j -= 1
        amp = p["overshootFrac"] * math.dist(pos[j], pos[i])
        for f in range(e["frame"], min(n, e["frame"] + window) + 1):
            d = settle.overshoot((f - e["frame"]) / fps, amp, p["settleS"])
            ox[f - 1] += e["dir"][0] * d
            oy[f - 1] += e["dir"][1] * d
    lands = events.landings(pos, fps, prof.longest)
    for e in lands:
        for f in range(e["frame"], min(n, e["frame"] + window) + 1):
            sz[f - 1] = settle.squash_z((f - e["frame"]) / fps, p["squash"], p["settleS"])
    frames = list(range(1, n + 1))
    if stops:
        key_series(offset, "location", 0, frames, ox)
        key_series(offset, "location", 1, frames, oy)
    if lands and p["squash"] < 1.0:
        sxy = [settle.squash_xy(z) for z in sz]
        key_series(offset, "scale", 0, frames, sxy)
        key_series(offset, "scale", 1, frames, sxy)
        key_series(offset, "scale", 2, frames, sz)
    record("settle_stops", len(stops))
    record("settle_landings", len(lands))
```

- [ ] **Step 4: Run, expect PASS**, then the fast loop.

- [ ] **Step 5: Commit**

```bash
git add engine/blocks/realism/landing_settle engine/physics/applies.py engine/tests/test_realism_blender.py engine/tests/test_physics_applies.py
git commit -m "feat(realism): landing_settle - overshoot after stops, squash on landing for soft goods"
```

---

### Task 19: `soft_rest` — a soft subject dips where it rests (the cushion dip)

A soft subject (plush, pillow, soft bag) resting on the ground flattens a little into its footprint and
bulges out around it. The other half of CD-03 — a cushion dipping under an object placed **on** it — needs
a second object (a prop or a character) and waits for multi-object scenes (Deferred).

**Files:**
- Create: `engine/blocks/realism/soft_rest/{block.json,build.py}`
- Modify: `engine/physics/contact.py` (+ `soft_deform`), `engine/tests/test_physics_contact_tyre.py`,
  `engine/tests/test_realism_blender.py`

- [ ] **Step 1: Write the failing tests.**

`engine/tests/test_physics_contact_tyre.py`:

```python
def test_soft_deform_flattens_the_footprint_and_bulges_around_it():
    z, rho = contact.soft_deform(-0.01, 0.05, ground=0.0, dip=0.018, height=0.3, bulge_frac=0.2)
    assert z == 0.0 and rho == pytest.approx(0.05 + 0.2 * 0.018)
    assert contact.soft_deform(0.2, 0.05, 0.0, 0.018, 0.3, 0.2) == (0.2, 0.05)   # above the falloff: untouched
```

`engine/tests/test_realism_blender.py`:

```python
def test_a_soft_subject_dips_into_its_footprint(tmp_path):
    glb = make_glb("plush", tmp_path / "plush.glb")
    prof = ingest(glb, workdir=tmp_path / "i")
    res = compile_scene(_script(), prof, glb, tmp_path / "c", render=False, skip_kinds=("grade",), realism_probe=[1])
    assert "soft_rest" in res["realism"]
    rec, dip = res["realismProbe"]["1"], res["realismScene"]["soft_dip_m"]
    assert dip == pytest.approx(0.06 * prof.sizeM[2], rel=1e-3) and probes.grounded_ok(rec, 0.0)
    want = 2 * (2 * 0.15 * dip - dip * dip) ** 0.5                    # sphere chord at depth dip
    assert rec["footprintM"] == pytest.approx(want, rel=0.3)
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement.**

`engine/physics/contact.py`:

```python
SOFT_FALLOFF = 0.25   # the soft bulge fades 0.25 x the subject height above the floor (eng)


def soft_deform(z, rho, ground, dip, height, bulge_frac):
    """(z', rho') of a point of a soft subject: clamp onto the floor, push out radially from the footprint
    centre near the floor (CD-03 rest dip; METHODS §2.1 M-GND)."""
    from engine.physics.tyre import smoothstep
    z2 = max(z, ground)
    k = bulge_frac * dip * (1.0 - smoothstep(0.0, SOFT_FALLOFF * height, z2 - ground))
    return z2, rho + k
```

`engine/blocks/realism/soft_rest/block.json` — pattern keys with `"id": "soft_rest"`, description
`"A soft subject (plush, pillow, soft bag) settles into its footprint where it rests: a flat base and a slight bulge around it. Added when the subject is soft and stands on the ground."`,
`"capabilities": ["contact.soft"]`, `"requiresProfile": "softParts"`,
`"appliesWhen": {"placement": ["ground"], "profile": ["softGround"]}`, params
`{"sinkFrac": {"type": "number", "min": 0.02, "max": 0.15, "default": 0.06}, "bulgeFrac": {"type": "number", "min": 0.0, "max": 0.4, "default": 0.2}}`,
`"physics": {"taxonomy": ["CD-03"], "state": "stateless", "touchesSubject": true, "windDriven": false}`,
`"costWeight": 1.0`.

`engine/blocks/realism/soft_rest/build.py`:

```python
"""Soft rest dip (TAXONOMY CD-03 static; METHODS §2.1 M-GND): the subject drops by dip = sinkFrac x height
(realism offset); every vertex below the floor is clamped onto it (flat footprint) and the low surface
bulges out from the footprint centre (engine/physics/contact.soft_deform, in nodes)."""
from engine.physics import contact as C


def build(ctx):
    from engine.blender import gn
    from engine.blender.realism_rig import record, rig
    p, prof = ctx.params, ctx.profile
    _, offset = rig()
    H = prof.sizeM[2]
    dip = p["sinkFrac"] * H
    offset.location.z -= dip
    gc = prof.groundContacts or [{"center": [0.0, 0.0, 0.0], "share": 1.0}]
    cx = sum(g["center"][0] * g["share"] for g in gc) / sum(g["share"] for g in gc)
    cy = sum(g["center"][1] * g["share"] for g in gc) / sum(g["share"] for g in gc)
    sink = float(ctx.scene.get("valora_rz_sink_m", 0.0))
    t = gn.Tree("valora_rz_soft_rest")
    P, back = gn.placed(t, offset)
    ground = gn.ground_in_placed(t, offset, -sink)
    px, py, pz = t.xyz(P)
    z2 = t.math("MAXIMUM", pz, ground)
    k = t.math("MULTIPLY", p["bulgeFrac"] * dip,
               t.math("SUBTRACT", 1.0, t.smoothstep(0.0, C.SOFT_FALLOFF * H, t.math("SUBTRACT", z2, ground))))
    radial = t.vmath("NORMALIZE", t.vec(t.math("SUBTRACT", px, cx), t.math("SUBTRACT", py, cy), 0.0))
    t.set_position(back(t.vmath("ADD", t.vec(px, py, z2), t.vmath("SCALE", radial, scale=k))))
    ng = t.finish()
    for o in ctx.meshes:
        gn.add_modifier(o, ng, "valora_rz_soft_rest")
    record("soft_dip_m", dip)
```

`engine/blender/realism_probe.py` — per frame, the flat footprint of the whole subject: keep each
object's world array in a list `cos` inside the mesh loop (`cos.append(co)`), then after the loop:

```python
        low = np.vstack([c[c[:, 2] <= zmin + FLAT_TOL_M] for c in cos]) if cos else np.empty((0, 3))
        rec["footprintM"] = float(max(np.ptp(low[:, 0]), np.ptp(low[:, 1]))) if len(low) >= 3 else 0.0
```

- [ ] **Step 4: Run, expect PASS**, then the fast loop.

- [ ] **Step 5: Commit**

```bash
git add engine/blocks/realism/soft_rest engine/physics/contact.py engine/blender/realism_probe.py engine/tests/test_physics_contact_tyre.py engine/tests/test_realism_blender.py
git commit -m "feat(realism): soft_rest - soft subjects dip into their footprint"
```

---

### Task 20: `foliage_sway` and `ground_conform` — grass moves with the wind and gives way under the subject

**World contract** (for phase-5 `golden_field` and every later outdoor world, stated in
`engine/blender/realism_rig.py`'s docstring): a world with `hasFoliage: true` tags its foliage mesh
objects `valora_foliage` and writes two point attributes: `valora_sway` (0 at the root … 1 at the tip)
and `valora_sway_len` (the stem length in metres). No world may animate its own foliage.

**Files:**
- Create: `engine/blender/sway_nodes.py`, `engine/blocks/realism/foliage_sway/{block.json,build.py}`,
  `engine/blocks/realism/ground_conform/{block.json,build.py}`
- Modify: `engine/blender/realism_probe.py` (sway and foliage-in-subject records),
  `engine/tests/fixtures/blocks/world/test_lawn/build.py` (+ 20 blades under the subject),
  `engine/tests/test_realism_blender.py`

- [ ] **Step 1: Write the failing test.**

```python
def _angle(a, b):
    import math
    return math.degrees(math.acos(max(-1.0, min(1.0, (a[0] * b[0] + a[1] * b[1]) /
                                             ((math.hypot(*a[:2]) * math.hypot(*b[:2])) or 1.0)))))


def test_grass_bends_downwind_and_is_still_in_calm_air(tmp_path):
    cat = catalog_with_fixtures(tmp_path)
    s = _script(world={"id": "test_lawn", "params": {}})
    s["wind"] = {"id": "wind", "params": {"speedMs": 4.0, "directionDeg": 30.0}}
    s["realism"] = [{"kind": "realism", "id": "ground_conform", "params": {"leanFrac": 0.0}}]  # sway only
    res = _compile("toycar", tmp_path / "w", script=s, catalog=cat, frames=(1, 45))
    assert "foliage_sway" in res["realism"]
    for f in ("1", "45"):
        sw = res["realismProbe"][f]["sway"]
        assert sw["n"] > 0 and _angle(sw["meanDisp"], (0.866, 0.5)) <= 45.0     # wind_coherent (BLOCKS §5)
    s["wind"]["params"]["speedMs"] = 0.0
    calm = _compile("toycar", tmp_path / "c", script=s, catalog=cat, frames=(1,))
    assert abs(calm["realismProbe"]["1"]["sway"]["meanDisp"][0]) < 1e-4


def test_grass_under_the_subject_is_pressed_flat_and_nearby_blades_lean_away(tmp_path):
    cat = catalog_with_fixtures(tmp_path)
    s = _script(world={"id": "test_lawn", "params": {}})
    res = _compile("toycar", tmp_path, script=s, catalog=cat, frames=(1,))
    sc = res["realismScene"]
    assert "ground_conform" in res["realism"]
    assert sc["conform_pressed_blades"] >= 20 and sc["conform_leaning_blades"] > 0
    assert res["realismProbe"]["1"]["foliageInSubject"] == 0     # no blade pokes through the subject
```

In `engine/tests/fixtures/blocks/world/test_lawn/build.py`, after the ring loop, add 20 blades whose roots
lie inside the subject's footprint (they pierce the subject until `ground_conform` presses them):

```python
    for i in range(20):
        x = rng.uniform(prof.boundsMin[0] * 0.8, prof.boundsMax[0] * 0.8)
        y = rng.uniform(prof.boundsMin[1] * 0.8, prof.boundsMax[1] * 0.8)
        k = len(verts)
        verts += [(x - BLADE_W / 2, y, 0.0), (x + BLADE_W / 2, y, 0.0), (x, y, BLADE_H)]
        faces.append((k, k + 1, k + 2))
        sway += [0.0, 0.0, 1.0]
        length += [BLADE_H] * 3
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement.**

`engine/blender/sway_nodes.py`:

```python
"""The one wind-bend deformer (engine/physics/sway in nodes) for foliage and dangling parts. Works in world
space (Object Info of the object itself), reads the shared valora_wind group, and bends each vertex by
bend_frac(|w|) * len * u^2 along the horizontal wind, plus a small perpendicular flutter. Stateless."""
import math

from engine.physics import sway as SW


def sway_tree(name, stiffness, flutter):
    import bpy
    from engine.blender import gn
    from engine.blender.realism_rig import SWAY, SWAY_LEN
    t = gn.Tree(name)
    m = t.object_transform(t.self_object())
    wp = t.point(t.position(), m)                                                  # world position
    wind = t.group(bpy.data.node_groups["valora_wind"], Position=wp).outputs["Wind"]
    wx, wy, _ = t.xyz(wind)
    v2 = t.math("ADD", t.math("MULTIPLY", wx, wx), t.math("MULTIPLY", wy, wy))
    bend = t.math("MINIMUM", math.tan(math.radians(SW.MAX_BEND_DEG)),
                  t.math("MULTIPLY", v2, SW.DRAG_K * (1.0 - 0.8 * stiffness)))
    u = t.attr(SWAY)
    reach = t.math("MULTIPLY", t.math("MULTIPLY", bend, t.attr(SWAY_LEN)), t.math("MULTIPLY", u, u))
    dirn = t.vmath("NORMALIZE", t.vec(wx, wy, 0.0))
    fac, _ = t.noise(t.vmath("ADD", t.vmath("SCALE", wp, scale=20.0), t.vec(0.0, 0.0, t.math("MULTIPLY", t.time(), 6.0))))
    jitter = t.math("MULTIPLY", t.math("MULTIPLY", reach, 0.2 * flutter), t.math("SUBTRACT", t.math("MULTIPLY", fac, 2.0), 1.0))
    dx, dy, _ = t.xyz(dirn)
    perp = t.vec(t.math("MULTIPLY", dy, -1.0), dx, 0.0)
    disp = t.vmath("ADD", t.vmath("SCALE", dirn, scale=reach), t.vmath("SCALE", perp, scale=jitter))
    t.set_position(t.point(t.vmath("ADD", wp, disp), t.invert(m)))
    return t.finish()
```

`engine/blocks/realism/foliage_sway/block.json` — pattern keys with `"id": "foliage_sway"`, description
`"Grass, flowers and plants in the world bend and flutter with the clip's one wind (still in calm air). Added to every world with foliage."`,
`"capabilities": ["foliage.sway"]`, `"appliesWhen": {"world": {"hasFoliage": true}}`, params
`{"stiffness": {"type": "number", "min": 0.0, "max": 1.0, "default": 0.5}, "flutter": {"type": "number", "min": 0.0, "max": 1.0, "default": 0.5}}`,
`"physics": {"taxonomy": ["HF-01", "HF-02", "HF-03"], "state": "stateless", "touchesSubject": false, "windDriven": true}`,
`"costWeight": 1.05`.

`engine/blocks/realism/foliage_sway/build.py`:

```python
"""Foliage sway (TAXONOMY HF-01..03; METHODS §2.5 M-GNT): the world's foliage (valora_foliage objects with
valora_sway / valora_sway_len) bends with the shared wind. No wind field -> nothing moves."""


def build(ctx):
    import bpy
    from engine.blender import gn
    from engine.blender.realism_rig import FOLIAGE_TAG, record
    from engine.blender.sway_nodes import sway_tree
    objs = [o for o in ctx.scene.objects if o.get(FOLIAGE_TAG) and o.type == "MESH"]
    if bpy.data.node_groups.get("valora_wind") is None or not objs:
        record("foliage_objects", 0)
        return
    ng = sway_tree("valora_rz_foliage_sway", ctx.params["stiffness"], ctx.params["flutter"])
    for o in objs:
        gn.add_modifier(o, ng, "valora_rz_foliage_sway")
    record("foliage_objects", len(objs))
```

`engine/blocks/realism/ground_conform/block.json` — pattern keys with `"id": "ground_conform"`,
description `"Grass and ground cover give way under the subject: blades beneath it are pressed flat and blades close to it lean away, so nothing pokes through. Added to grounded subjects in worlds with foliage."`,
`"capabilities": []`, `"appliesWhen": {"placement": ["ground"], "world": {"hasFoliage": true}}`, params
`{"leanFrac": {"type": "number", "min": 0.0, "max": 1.0, "default": 0.5}}`,
`"physics": {"taxonomy": ["CD-07", "HF-06"], "state": "stateless", "touchesSubject": true, "windDriven": false}`,
`"costWeight": 1.0`.

`engine/blocks/realism/ground_conform/build.py`:

```python
"""Ground-cover conformity (TAXONOMY CD-07, HF-06 static; METHODS §2.1 CD-07). Foliage vertices inside the
subject's footprint (its placed bounds in x/y, through the rig at frame 1) are pressed to 2 mm; those within
a ring of MARGIN_FRAC x longest lean away from the footprint, strongest at its edge. Stacked after
foliage_sway (resolver ORDER), so pressed blades stay pressed in any wind. The subject's sink into the
cover is contact_ground's sinkMm. Parting grass behind a moving subject (HF-06 dynamic) waits for phase-5
drive."""
MARGIN_FRAC = 0.15    # lean-away ring width, x the subject's longest side (eng)
PRESSED_Z = 0.002     # a pressed blade lies 2 mm high (eng)


def build(ctx):
    import numpy as np
    from engine.blender import gn
    from engine.blender.realism_rig import FOLIAGE_TAG, SWAY, SWAY_LEN, record, rig
    prof, scene = ctx.profile, ctx.scene
    objs = [o for o in scene.objects if o.get(FOLIAGE_TAG) and o.type == "MESH"]
    _, offset = rig()
    scene.frame_set(1)
    m = np.array(offset.matrix_world)
    corners = np.array([[x, y, 0.0, 1.0] for x in (prof.boundsMin[0], prof.boundsMax[0])
                        for y in (prof.boundsMin[1], prof.boundsMax[1])]) @ m.T
    lo, hi = corners[:, :2].min(axis=0), corners[:, :2].max(axis=0)
    margin = MARGIN_FRAC * prof.longest
    t = gn.Tree("valora_rz_ground_conform")
    mw = t.object_transform(t.self_object())
    wp = t.point(t.position(), mw)
    x, y, z = t.xyz(wp)
    dx = t.math("MAXIMUM", t.math("MAXIMUM", t.math("SUBTRACT", float(lo[0]), x), t.math("SUBTRACT", x, float(hi[0]))), 0.0)
    dy = t.math("MAXIMUM", t.math("MAXIMUM", t.math("SUBTRACT", float(lo[1]), y), t.math("SUBTRACT", y, float(hi[1]))), 0.0)
    dist = t.math("SQRT", t.math("ADD", t.math("MULTIPLY", dx, dx), t.math("MULTIPLY", dy, dy)))
    inside = t.math("LESS_THAN", dist, 1e-6)
    cx, cy = float(0.5 * (lo[0] + hi[0])), float(0.5 * (lo[1] + hi[1]))
    out = t.vmath("NORMALIZE", t.vec(t.math("SUBTRACT", x, cx), t.math("SUBTRACT", y, cy), 0.0))
    near = t.math("SUBTRACT", 1.0, t.smoothstep(0.0, margin, dist))
    u = t.attr(SWAY)
    lean = t.math("MULTIPLY", t.math("MULTIPLY", near, ctx.params["leanFrac"]),
                  t.math("MULTIPLY", t.attr(SWAY_LEN), t.math("MULTIPLY", u, u)))
    leaned = t.vmath("ADD", wp, t.vmath("SCALE", out, scale=lean))
    pressed = t.vec(x, y, t.math("MINIMUM", z, PRESSED_Z))
    t.set_position(t.point(t.switch_vec(inside, leaned, pressed), t.invert(mw)))
    ng = t.finish()
    n_in = n_ring = 0
    for o in objs:
        gn.add_modifier(o, ng, "valora_rz_ground_conform")
        co = np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", co)
        mo = np.array(o.matrix_world)
        roots = (co.reshape(-1, 3) @ mo[:3, :3].T + mo[:3, 3])[::3]   # lawn contract: root vertex first
        d = np.hypot(np.maximum(np.maximum(lo[0] - roots[:, 0], roots[:, 0] - hi[0]), 0),
                     np.maximum(np.maximum(lo[1] - roots[:, 1], roots[:, 1] - hi[1]), 0))
        n_in += int((d == 0).sum())
        n_ring += int(((d > 0) & (d < margin)).sum())
    record("conform_pressed_blades", n_in)
    record("conform_leaning_blades", n_ring)
```

The blade counts assume the lawn's three-vertex blades; a real world (phase 5) counts root vertices
(`valora_sway == 0`) instead (hand-off H6).

`engine/blender/realism_probe.py` — per frame, `rec["foliageInSubject"]`: the number of evaluated foliage
vertices (objects tagged `valora_foliage`) whose **world** z is above 3 mm and whose position, brought into
placed space with `np.array(offset.matrix_world.inverted())`, falls inside the subject's placed bounds
(`engine.geometry.point_in_box(p, profile.boundsMin, profile.boundsMax, 0.0)`). The height test is in
world z: the sink lifts pressed blades to a few mm in placed space.

`engine/blender/realism_probe.py` — per frame, for every scene mesh object with a `valora_sway` point
attribute (foliage, and after Task 21 the subject's dangling parts), compare rest and evaluated world
positions of the tip vertices (sway ≥ 0.9; GN keeps the attribute and the vertex order):

```python
        disp, cnt = np.zeros(3), 0
        for o in [o for o in scene.objects if o.type == "MESH" and o.data.attributes.get(SWAY) is not None]:
            sw = np.empty(len(o.data.vertices), np.float32)
            o.data.attributes[SWAY].data.foreach_get("value", sw)
            rest = np.empty(len(o.data.vertices) * 3)
            o.data.vertices.foreach_get("co", rest)
            m = np.array(o.matrix_world)
            rest = rest.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
            ev = o.evaluated_get(deps)
            me = ev.to_mesh()
            try:
                cur = _world(ev, me)
            finally:
                ev.to_mesh_clear()
            tip = sw >= 0.9
            disp += (cur[tip] - rest[tip]).sum(axis=0)
            cnt += int(tip.sum())
        rec["sway"] = {"n": cnt, "meanDisp": (disp / cnt).tolist() if cnt else [0.0, 0.0, 0.0]}
```
(import `SWAY` from `engine.blender.realism_rig`).

- [ ] **Step 4: Run, expect PASS**, then the fast loop.

- [ ] **Step 5: Commit**

```bash
git add engine/blender/sway_nodes.py engine/blocks/realism/foliage_sway engine/blocks/realism/ground_conform engine/blender/realism_probe.py engine/tests/fixtures/blocks/world/test_lawn/build.py engine/tests/test_realism_blender.py
git commit -m "feat(realism): foliage_sway and ground_conform - grass moves with the wind and gives way under the subject"
```

---

### Task 21: `dangling_sway` — straps, cords and tags hang and move with the wind

**Files:**
- Create: `engine/blocks/realism/dangling_sway/{block.json,build.py}`
- Modify: `engine/blender/realism_rig.py` (+ `tag_dangling`), `engine/tests/test_realism_blender.py`

- [ ] **Step 1: Write the failing test.**

```python
def test_a_hanging_strap_swings_downwind_and_the_body_does_not_move(tmp_path):
    glb = make_glb("strap", tmp_path / "strap.glb")
    prof = ingest(glb, workdir=tmp_path / "i")
    s = _script()
    s["wind"] = {"id": "wind", "params": {"speedMs": 5.0, "directionDeg": 0.0}}
    res = compile_scene(s, prof, glb, tmp_path / "c", render=False, skip_kinds=("grade",), realism_probe=[1, 60])
    assert "dangling_sway" in res["realism"]
    tagged = res["realismScene"]["dangling_verts"]
    assert 0 < tagged < res["realismScene"]["dangling_total_verts"] / 2      # only the strap
    for f in ("1", "60"):
        sw = res["realismProbe"][f]["sway"]
        assert sw["n"] > 0 and _angle(sw["meanDisp"], (1.0, 0.0)) <= 45.0
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement.**

`engine/blender/realism_rig.py`:

```python
def tag_dangling(meshes, parts):
    """valora_sway (0 at the pivot .. 1 at the tip) and valora_sway_len on every island that lies wholly
    inside a high-confidence dangling part's capsule (pivot -> tip, radius x 1.5 + 2 mm). Islands that
    only touch the capsule (the body the strap hangs from) stay rigid."""
    from engine.blender.islands import summaries, vertex_islands
    tagged = total = 0
    for o in meshes:
        P = placed_points(o)
        total += len(P)
        isl = vertex_islands(o)
        if isl is None or not len(P):
            continue
        u = np.zeros(len(P), np.float32)
        ln = np.zeros(len(P), np.float32)
        for d in (d for d in parts if d["confidence"] == "high"):
            a, b = np.array(d["pivot"]), np.array(d["tip"])
            ab = b - a
            L = float(np.linalg.norm(ab)) or 1e-9
            s = np.clip((P - a) @ ab / (L * L), 0.0, 1.0)
            dist = np.linalg.norm(P - (a + s[:, None] * ab), axis=1)
            inside = dist <= 1.5 * d["radius"] + 0.002
            for piece in summaries(P, isl, 0, min_n=1):
                sel = isl == piece["id"]
                if inside[sel].all():
                    u[sel], ln[sel] = s[sel], L
        if (u > 0).any():
            write_attr(o, SWAY, u, "FLOAT")
            write_attr(o, SWAY_LEN, ln, "FLOAT")
            tagged += int((ln > 0).sum())
    return tagged, total
```

`engine/blocks/realism/dangling_sway/block.json` — pattern keys with `"id": "dangling_sway"`, description
`"Straps, cords, tags and laces that hang from the subject swing gently with the clip's one wind. Added when ingest found a hanging part with high confidence."`,
`"capabilities": ["secondary.follow_through"]`, `"requiresProfile": "danglingParts"`,
`"appliesWhen": {"profile": ["danglingParts"]}`, params
`{"stiffness": {"type": "number", "min": 0.0, "max": 1.0, "default": 0.4}, "flutter": {"type": "number", "min": 0.0, "max": 1.0, "default": 0.3}}`,
`"physics": {"taxonomy": ["SC-08", "SF-02", "SF-03"], "state": "stateless", "touchesSubject": true, "windDriven": true}`,
`"costWeight": 1.0`.

`engine/blocks/realism/dangling_sway/build.py`:

```python
"""Dangling sway (TAXONOMY SC-08, SF-02, SF-03; METHODS §2.11 M-KIN): the hanging part bends from its pivot
with the shared wind (engine/blender/sway_nodes). Swing from the subject's own acceleration (a strap
swinging after a stop) needs moving subjects and lands with phase 5 (Deferred)."""


def build(ctx):
    import bpy
    from engine.blender import gn
    from engine.blender.realism_rig import SWAY, record, tag_dangling
    from engine.blender.sway_nodes import sway_tree
    tagged, total = tag_dangling(ctx.meshes, ctx.profile.danglingParts)
    record("dangling_verts", tagged)
    record("dangling_total_verts", total)
    if not tagged or bpy.data.node_groups.get("valora_wind") is None:
        return
    ng = sway_tree("valora_rz_dangling_sway", ctx.params["stiffness"], ctx.params["flutter"])
    for o in ctx.meshes:
        if o.data.attributes.get(SWAY) is not None:
            gn.add_modifier(o, ng, "valora_rz_dangling_sway")
```

Wind in placed vs world: the sway tree works in world space; the subject's own motion does not change the
bend direction (the wind is world-fixed), which is what real straps do.

- [ ] **Step 4: Run, expect PASS**, then the fast loop.

- [ ] **Step 5: Commit**

```bash
git add engine/blocks/realism/dangling_sway engine/blender/realism_rig.py engine/tests/test_realism_blender.py
git commit -m "feat(realism): dangling_sway - hanging straps and cords move with the wind"
```

---

### Task 22: `shaft_dust` — dust you only see in light shafts

**Files:**
- Create: `engine/blocks/realism/shaft_dust/{block.json,build.py}`
- Modify: `engine/blender/realism_probe.py` (dust record), `engine/tests/test_realism_blender.py`,
  `engine/tests/test_physics_applies.py`

- [ ] **Step 1: Write the failing tests.**

`engine/tests/test_physics_applies.py`:

```python
def test_dust_only_with_haze():
    cat = Catalog.load()
    s = _script()
    assert "shaft_dust" not in _ids(check(s, _p("toycar"), cat).script)
    s["effects"] = [{"id": "haze_volume", "params": {}}]
    assert "shaft_dust" in _ids(check(s, _p("toycar"), cat).script)
```

`engine/tests/test_realism_blender.py`:

```python
def test_dust_motes_stay_outside_the_subject_and_never_glow(tmp_path):
    s = _script(effects=[{"id": "haze_volume", "params": {"density": 0.3}}])
    res = _compile("toycar", tmp_path, script=s, frames=(1, 45, 90))
    sc = res["realismScene"]
    assert sc["dust_points"] == int(4000 * 0.2) and not sc["dust_emissive"]
    for f in ("1", "45", "90"):
        d = res["realismProbe"][f]["dust"]
        assert d["visible"] > 0 and d["visibleInSubject"] == 0               # PH-03 [C]
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement.**

`engine/blocks/realism/shaft_dust/block.json` — pattern keys with `"id": "shaft_dust"`, description
`"Fine dust motes drifting slowly in the air, visible only where a light beam crosses them. Added whenever the scene has haze."`,
`"capabilities": []`, `"appliesWhen": {"effects": ["haze_volume"]}`, params
`{"density": {"type": "number", "min": 0.0, "max": 1.0, "default": 0.2}}`,
`"physics": {"taxonomy": ["PT-01", "LM-03"], "state": "stateless", "touchesSubject": false, "windDriven": true}`,
`"costWeight": 1.05`.

`engine/blocks/realism/shaft_dust/build.py`:

```python
"""Dust in light shafts (TAXONOMY PT-01, LM-03; METHODS §2.6 PT-01). Up to N_MAX tiny points in the haze
shell around the subject (between the clear pocket's outer radius and the haze's full-density radius),
drifting with the mean wind plus a slow wander, wrapped inside the shell's box. Not emissive and not
shadow-casting: a mote reads only where a light beam crosses it, i.e. in the shafts the haze shows.
Motes are rendered at ~MOTE_PX pixels (real dust is 20-100 um; METHODS PT-01's deliberate cheat). A mote
whose wrapped position falls inside the clear pocket gets radius 0 (never seen, never inside the subject).
Stateless: position = base + drift(t), no frame depends on the one before."""
import math

N_MAX = 4000        # motes at density 1 (eng)
MOTE_PX = 1.5       # rendered diameter in pixels at the median camera distance, 1080 short side (eng)
WANDER_FRAC = 0.05  # wander amplitude, x subject radius (eng; METHODS 1-3 cm/s brownian at car scale)
POCKET_OUT = 2.0    # matches haze_volume POCKET[1]: no mote inside 2 r


def build(ctx):
    import bpy
    from engine.blender import gn
    from engine.blender.realism_rig import record
    scene, prof = ctx.scene, ctx.profile
    fade = scene.get("valora_haze_fade")
    n = int(N_MAX * ctx.params["density"])
    if fade is None or n == 0:          # haze skipped (skip_kinds) or density 0
        record("dust_points", 0)
        record("dust_emissive", False)
        return
    cx, cy, cz, r_full, _ = [float(v) for v in fade]
    r = prof.radius
    inner, outer = POCKET_OUT * r, max(POCKET_OUT * r * 1.5, min(r_full, 4.0 * r))
    lo = (cx - outer, cy - outer, max(0.0, cz - outer))
    span = (2 * outer, 2 * outer, cz + outer - lo[2])
    base = []
    while len(base) < n:
        p = (lo[0] + ctx.rng.random() * span[0], lo[1] + ctx.rng.random() * span[1], lo[2] + ctx.rng.random() * span[2])
        if inner <= math.dist(p, (cx, cy, cz)) <= outer:
            base.append(p)
    me = bpy.data.meshes.new("valora_rz_dust")
    me.from_pydata(base, [], [])
    ob = bpy.data.objects.new("valora_rz_dust", me)
    scene.collection.objects.link(ob)
    ob.visible_shadow = False
    w = scene.get("valora_wind") or {"directionDeg": 0.0, "speedMs": 0.0}
    from engine.physics import wind as W
    vx, vy, _ = W.vector(float(w["directionDeg"]), float(w["speedMs"]))
    cams = sorted(math.dist(c, prof.center) for c in ctx.camera_positions) or [4.0 * r]
    radius = 0.5 * MOTE_PX * cams[len(cams) // 2] * (36.0 / 50.0) / 1080.0
    t = gn.Tree("valora_rz_dust")
    sec = t.time()
    pos = t.position()
    fac, col = t.noise(t.vmath("ADD", t.vmath("SCALE", pos, scale=1.0 / r), t.vec(0.0, 0.0, t.math("MULTIPLY", sec, 0.3))))
    wander = t.vmath("SCALE", t.vmath("SUBTRACT", col, t.vec(0.5, 0.5, 0.5)), scale=2.0 * WANDER_FRAC * r)
    moved = t.vmath("ADD", t.vmath("ADD", pos, t.vmath("SCALE", t.vec(vx, vy, 0.0), scale=sec)), wander)
    mx, my, mz = t.xyz(moved)
    wrap = [t.math("WRAP", c, lo[k] + span[k], lo[k]) for k, c in enumerate((mx, my, mz))]   # sockets: Value, Max, Min
    p2 = t.vec(*wrap)
    d = t.vmath("DISTANCE", p2, t.vec(cx, cy, cz))
    rad = t.math("MULTIPLY", radius, t.math("GREATER_THAN", d, inner))
    t.set_position(p2)
    t.store("valora_dust_r", rad, "FLOAT")
    gn.add_modifier(ob, t.finish(), "valora_rz_dust_move")
    t2 = gn.Tree("valora_rz_dust_points")
    pts = t2.node("GeometryNodeMeshToPoints")
    t2.feed(pts.inputs["Mesh"], t2.geometry)
    t2.feed(pts.inputs["Radius"], t2.attr("valora_dust_r"))
    mat = bpy.data.materials.new("valora_rz_dust")
    mat.use_nodes = True
    bsdf = next(nd for nd in mat.node_tree.nodes if nd.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.8, 0.8, 0.78, 1.0)
    bsdf.inputs["Roughness"].default_value = 1.0
    bsdf.inputs["Emission Strength"].default_value = 0.0
    sm = t2.node("GeometryNodeSetMaterial")
    t2.feed(sm.inputs["Geometry"], pts.outputs["Points"])
    sm.inputs["Material"].default_value = mat
    t2.geometry = sm.outputs["Geometry"]
    gn.add_modifier(ob, t2.finish(), "valora_rz_dust_points")
    record("dust_points", n)
    record("dust_emissive", False)
    record("dust_radius_m", radius)
```

`ShaderNodeMath` `WRAP` sockets are **Value, Max, Min** (the builder feeds them in order). If the probe
shows motes collapsing onto one plane, the order is the other way round: swap the two bounds.

`engine/blender/realism_probe.py` — per frame, if the dust object exists (the points modifier is switched
off for the read, so the evaluated mesh still has vertices and the radius attribute):

```python
        dust = bpy.data.objects.get("valora_rz_dust")
        if dust is not None:
            from engine.geometry import point_in_box
            mod = dust.modifiers["valora_rz_dust_points"]
            mod.show_viewport = False
            ev = dust.evaluated_get(bpy.context.evaluated_depsgraph_get())
            me = ev.to_mesh()
            try:
                pts = _world(ev, me)
                rad = np.empty(len(me.vertices), np.float32)
                me.attributes["valora_dust_r"].data.foreach_get("value", rad)
            finally:
                ev.to_mesh_clear()
                mod.show_viewport = True
            vis = pts[rad > 0]
            rec["dust"] = {"visible": int(len(vis)), "visibleInSubject": int(sum(
                point_in_box(tuple(p), profile.boundsMin, profile.boundsMax, 0.10) for p in vis))}
```

- [ ] **Step 4: Run, expect PASS** — the new tests and `test_compile_blender.py -k haze` (the calibrated
haze-lift test renders frame 256 with haze on and with `skip_kinds=("effect",)`: with the effect skipped
the dust block records 0 points, so the haze-off frame is unchanged; if the haze-on lift leaves its
2–13 band because of the motes, record the new lift in that test's docstring with the measurement, do not
widen the band blindly).

- [ ] **Step 5: Commit**

```bash
git add engine/blocks/realism/shaft_dust engine/blender/realism_probe.py engine/tests/test_realism_blender.py engine/tests/test_physics_applies.py
git commit -m "feat(realism): shaft_dust - non-emissive motes that read only in light shafts"
```

---

### Task 23: `glass_caustics` — shadow caustics under glass subjects (keep only if cheap)

**Files:**
- Create: `engine/blocks/realism/glass_caustics/{block.json,build.py}`
- Modify: `engine/tests/test_realism_blender.py`, `engine/tests/test_physics_applies.py`

- [ ] **Step 1: Write the failing tests.**

`engine/tests/test_physics_applies.py`:

```python
def test_caustics_only_for_glassy_subjects():
    cat = Catalog.load()
    assert "glass_caustics" in _ids(check(_script(), _p("pocket_watch"), cat).script)   # 22.8% glass
    assert "glass_caustics" in _ids(check(_script(), _p("camera_01"), cat).script)      # 11.8%
    for name in ("flighthelmet", "toycar", "sports_car"):                                 # 1.2%, 1.8%, 0%
        assert "glass_caustics" not in _ids(check(_script(), _p(name), cat).script), name
```

`engine/tests/test_realism_blender.py`:

```python
def test_caustic_flags_are_set_on_glass_floor_and_lights(tmp_path):
    res = _compile("pocket_watch", tmp_path, skip=())
    sc = res["realismScene"]
    assert sc["caustic_casters"] >= 1 and sc["caustic_receivers"] >= 1 and sc["caustic_lights"] >= 1
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement.**

`engine/blocks/realism/glass_caustics/block.json` — pattern keys with `"id": "glass_caustics"`,
description `"Light focused through a glass subject lands on the floor as bright shadow caustics instead of a flat grey shadow. Added to subjects with enough glass."`,
`"capabilities": []`, `"appliesWhen": {"placement": ["ground"], "materials": {"glass": 0.05}}`,
`"params": {}`, `"physics": {"taxonomy": ["LM-01"], "state": "stateless", "touchesSubject": true, "windDriven": false}`,
`"costWeight": 1.3`.

`engine/blocks/realism/glass_caustics/build.py`:

```python
"""Shadow caustics (TAXONOMY LM-01; METHODS §2.10 M-MNEE): Cycles' manifold next-event estimation, enabled
on the glass objects (casters), the floor (receivers) and every light. Refractive only, only inside
shadows, <= 4 refractive bounces, and it needs smooth normals: faceted glass gives noisy caustics
(materials are left alone, spec §4.5, so a faceted upload keeps its noise; noted, not fixed)."""
GLASS_TRANSMISSION = 0.5   # engine/ingest/measure.material_class: transmission > 0.5 is glass


def _is_glass(mat):
    if mat is None or not mat.use_nodes:
        return False
    n = next((x for x in mat.node_tree.nodes if x.type == "BSDF_PRINCIPLED"), None)
    s = n.inputs.get("Transmission Weight") if n is not None else None
    return s is not None and (s.is_linked or s.default_value > GLASS_TRANSMISSION)


def build(ctx):
    from engine.blender.realism_rig import ground_objects, record
    casters = [o for o in ctx.meshes if any(_is_glass(s.material) for s in o.material_slots)]
    for o in casters:
        o.cycles.is_caustics_caster = True
    receivers = ground_objects()
    for o in receivers:
        o.cycles.is_caustics_receiver = True
    lights = [o for o in ctx.scene.objects if o.type == "LIGHT"]
    for o in lights:
        o.data.cycles.is_caustics_light = True
    record("caustic_casters", len(casters))
    record("caustic_receivers", len(receivers))
    record("caustic_lights", len(lights))
```

A linked Transmission Weight (a texture) counts as glass here (ingest resolved it to a mean > 0.5 or it
would not have reached the 5% share); a false positive only costs render time on that object.

- [ ] **Step 4: Run, expect PASS**, then the fast loop. The **cost** check (is it cheap?) is Task 25.

- [ ] **Step 5: Commit**

```bash
git add engine/blocks/realism/glass_caustics engine/tests/test_realism_blender.py engine/tests/test_physics_applies.py
git commit -m "feat(realism): glass_caustics - shadow caustics under glass subjects"
```

---
## Chunk 5: Harness, smoke renders, finish

### Task 24: Harness items PH-01 and PH-02

Report-only, like every harness item (spec §4.8, §9). They live in their own `physics` section of the
report so the TIERS tier ladder (`harness/items.py`) is untouched.

- **PH-01 tyre contact** — [C] every tyre on every probed frame passes `probes.tyre_patch_ok`;
  [M] **unmeasured in v0**: a flat of 2–3% of r is below one pixel at the keyframes/preview resolutions
  (a 0.35 m tyre's 8 mm deflection is < 1 px at 540 px short side on a full car frame), so a silhouette
  test cannot see it; [V] "Do the tyres look weighed down by the car?" waits for the vision judge (phase 6).
- **PH-02 grounded subject** — [C] `probes.grounded_ok` on every probed frame; [M] on full-framing frames,
  the floor strip just under the subject's mask reads darker than the floor beside it:
  `mean(beside) / mean(strip) >= seamRatio` (1.3, eng; the same strip geometry as `metrics.t1x2`).

**Files:**
- Create: `harness/physics.py`, `harness/tests/test_physics.py`
- Modify: `harness/score.py` (`score_case` adds `physics`; `write_report` appends its table),
  `harness/run.py` (pass `realism_probe` = the rendered key frames, at most 3), `harness/thresholds.json`

Re-read `harness/score.py`, `harness/run.py` and `harness/metrics.py` first: a parallel agent edits them.

- [ ] **Step 1: Write the failing tests** — `harness/tests/test_physics.py`:

```python
import numpy as np

from harness.metrics import Frame
from harness.physics import ph01_c, ph02_c, seam_ratio


def _frame(strip_dark):
    rgb = np.full((100, 60, 3), 0.5, np.float32)
    mask = np.zeros((100, 60), bool)
    mask[30:70, 20:40] = True
    rgb[70:75, 20:40] = 0.5 / strip_dark
    return Frame(frame=1, t=0.0, shot=0, lens=50.0, fstop=4.0, rgb=rgb, mask=mask, gloss=mask & False, mist=None)


def test_seam_ratio_reads_the_contact_shadow():
    assert abs(seam_ratio(_frame(2.0)) - 2.0) < 1e-3       # the strip under the subject is half as bright
    assert abs(seam_ratio(_frame(1.0)) - 1.0) < 1e-3       # no seam


def test_c_halves_read_the_realism_probe():
    realism = [{"id": "contact_ground", "params": {"sinkMm": 0.0}},
               {"id": "tyre_contact", "params": {"patchLenFrac": 0.45}}]
    wheels = [{"radius": 0.35}]
    good = {"1": {"minZ": 0.0, "tyres": {"0": {"minZ": 0.0, "flatLenM": 0.157, "flatN": 5}}}}   # want 0.1575
    bad = {"1": {"minZ": 0.004, "tyres": {"0": {"minZ": 0.0, "flatLenM": 0.02, "flatN": 1}}}}
    assert ph01_c(good, realism, wheels) == ("pass", None) and ph01_c(bad, realism, wheels)[0] == "fail"
    assert ph02_c(good, realism)[0] == "pass" and ph02_c(bad, realism)[0] == "fail"
    assert ph01_c({}, realism, wheels)[0] == "unmeasured"
    assert ph01_c(good, realism[:1], wheels)[0] == "na"
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest harness/tests/test_physics.py -q`.

- [ ] **Step 3: Implement** — `harness/physics.py`:

```python
"""Physics items for our own renders (research/physics/BLOCKS.md §6). Report-only.

PH-01 tyre contact  [C] probes.tyre_patch_ok on every probed frame; [M] unmeasured in v0 (a 2-3% of r
                    flat is sub-pixel at keyframes/preview); [V] vision judge, phase 6.
PH-02 grounded      [C] probes.grounded_ok on every probed frame; [M] floor strip under the subject reads
                    darker than the floor beside it by seamRatio on full-framing frames."""
import json
from pathlib import Path

import numpy as np

from engine.craft_rules import ItemResult
from engine.physics import probes
from harness.metrics import lum

PH_ITEMS = [{"id": "PH-01", "method": "C+M+V", "text": "Tyre contact patch present (C); visible (M, V: later)"},
            {"id": "PH-02", "method": "C+M", "text": "Subject grounded: no gap; contact seam darker than the floor beside it"}]


def seam_ratio(fd):
    """mean(floor beside) / mean(floor strip just under the mask), same rows as t1x2; None if unreadable."""
    L = lum(fd.rgb)
    if not fd.mask.any():
        return None
    ys, xs = np.nonzero(fd.mask)
    h, w = L.shape
    y0, y1 = ys.max() + 1, min(h, ys.max() + 1 + max(1, int(round(0.05 * h))))
    x0, x1 = xs.min(), xs.max() + 1
    pad = max(1, (x1 - x0) // 2)
    rows = np.zeros_like(fd.mask)
    rows[y0:y1] = True
    strip = rows.copy()
    strip[:, :x0] = strip[:, x1:] = False
    beside = rows & ~strip
    beside[:, :max(0, x0 - pad)] = beside[:, min(w, x1 + pad):] = False
    strip, beside = strip & ~fd.mask, beside & ~fd.mask
    if not strip.any() or not beside.any() or L[strip].mean() <= 0:
        return None
    return float(L[beside].mean() / L[strip].mean())


def _realism(realism):
    return {r["id"]: r.get("params", {}) for r in realism}


def ph01_c(probe, realism, wheels):
    rz = _realism(realism)
    if "tyre_contact" not in rz:
        return "na", "no tyre_contact in this script"
    if not probe:
        return "unmeasured", "no realism probe frames"
    sink = rz.get("contact_ground", {}).get("sinkMm", 0.0) / 1000.0
    ok = all(probes.tyre_patch_ok(t, wheels[int(i)]["radius"], rz["tyre_contact"]["patchLenFrac"], sink)
             for rec in probe.values() for i, t in rec["tyres"].items())
    return ("pass", None) if ok else ("fail", "a tyre patch is missing or outside +/-20% of patchLenFrac x r")


def ph02_c(probe, realism):
    rz = _realism(realism)
    if "contact_ground" not in rz:
        return "na", "not a ground placement"
    if not probe:
        return "unmeasured", "no realism probe frames"
    sink = rz["contact_ground"].get("sinkMm", 0.0) / 1000.0
    ok = all(probes.grounded_ok(rec, sink) for rec in probe.values())
    return ("pass", None) if ok else ("fail", "the subject floats or sinks too deep on a probed frame")


def evaluate_physics(case_dir, frames, script, profile, catalog, th):
    cj = Path(case_dir) / "compile.json"
    probe = json.loads(cj.read_text(encoding="utf-8")).get("realismProbe", {}) if cj.exists() else {}
    realism = script.get("realism", [])
    out = {}
    s01, d01 = ph01_c(probe, realism, profile.wheels or [])
    out["PH-01"] = ItemResult("PH-01", s01, None, (d01 or "") + " | [M] unmeasured in v0 (sub-pixel)")
    s02, d02 = ph02_c(probe, realism)
    full = [fd for fd in frames
            if catalog.get("camera", script["shots"][fd.shot]["camera"]["id"])["framing"] == "full"]
    ratios = [r for r in (seam_ratio(fd) for fd in full) if r is not None]
    m_ok = None if not ratios else all(r >= th["PH-02"]["seamRatio"] for r in ratios)
    status = s02
    if s02 == "pass" and m_ok is False:
        status = "fail"
    elif s02 == "pass" and m_ok is None:
        status = "unmeasured" if full else "pass"
    out["PH-02"] = ItemResult("PH-02", status, [round(r, 3) for r in ratios], d02 or "")
    return out
```

`harness/thresholds.json` — add:

```json
  "PH-01": {"primary": "patchTol", "op": "<=", "patchTol": 0.2, "calibrated": false, "source": "research/physics/BLOCKS.md §5 tyre_patch_present (eng)"},
  "PH-02": {"primary": "seamRatio", "op": ">=", "seamRatio": 1.3, "calibrated": false, "source": "research/physics/BLOCKS.md §6 PH-02 (eng)"}
```

`harness/score.py` — in `score_case`, after `items = merge(...)`:

```python
    from harness.physics import evaluate_physics
    physics = evaluate_physics(case_dir, frames, script, profile, catalog, th)
```
and add `"physics": {k: {"status": v.status, "value": v.value, "detail": v.detail} for k, v in physics.items()}`
to the returned dict. In `write_report`, after the items table, when `score.get("physics")`, append a
`## Physics (research/physics/BLOCKS.md §6)` table with the same columns (item, method from
`harness.physics.PH_ITEMS`, status, value, threshold, calibrated). The `write_report` item loop must not
iterate `physics` (it is not in `harness/items.py`).

`harness/run.py` — where it calls `compile_scene(...)`, add
`realism_probe=key_frames(check(script, profile, catalog).script, limit=key_limit, catalog=catalog)[:3]`
(`frames` there is the string `"key"` or `"all"`, not a list; import `key_frames` from
`engine.compiler.timeline` and `check` from `engine.checker` if they are not imported yet).

- [ ] **Step 4: Run, expect PASS** — `py -m pytest harness/tests -q -m "not blender"` (the existing
score/report tests must still pass; if one compares the whole report dict, add the `physics` key to its
expectation), then the fast loop.

- [ ] **Step 5: Commit**

```bash
git add harness/physics.py harness/tests/test_physics.py harness/score.py harness/run.py harness/thresholds.json
git commit -m "feat(harness): PH-01 tyre patch and PH-02 grounded (report-only physics section)"
```

---

### Task 25: Three-frame smoke renders and the cost check (owner OK first)

**Owner OK first:** 4 short compiles at the `keyframes` tier (144 px short side, 4 samples), at most 3
frames each: `sports_car` with and without realism, `pocket_watch` with and without caustics. About
2–5 minutes of GPU. Ask, wait for "ok".

**Files:**
- Modify: `engine/tests/test_realism_blender.py`

- [ ] **Step 1: Write the tests** (they render; each ≤ 3 frames):

```python
import time


def _timed(name, tmp, skip, frames):
    t0 = time.perf_counter()
    res = compile_scene(_script(), _profile(name), _glb(name), tmp, tier="keyframes", frames=list(frames),
                        skip_kinds=skip, realism_probe=list(frames))
    return res, time.perf_counter() - t0


def test_smoke_sports_car_realism_three_frames(tmp_path):
    on, t_on = _timed("sports_car", tmp_path / "on", (), (1, 45, 90))
    off, t_off = _timed("sports_car", tmp_path / "off", ("realism",), (1, 45, 90))
    assert all((tmp_path / "on" / "beauty" / f"{f:04d}.png").exists() for f in (1, 45, 90))
    for f in ("1", "45", "90"):
        assert probes.grounded_ok(on["realismProbe"][f], 0.0)
    print(f"REALISM-COST sports_car on {t_on:.1f}s off {t_off:.1f}s ratio {t_on / t_off:.3f}")


def test_smoke_pocket_watch_caustics_cost(tmp_path):
    on, t_on = _timed("pocket_watch", tmp_path / "on", (), (45,))
    assert "glass_caustics" in on["realism"]
    off, t_off = _timed("pocket_watch", tmp_path / "off", ("realism",), (45,))
    print(f"CAUSTICS-COST pocket_watch on {t_on:.1f}s off {t_off:.1f}s ratio {t_on / t_off:.3f}")
```

(`skip_kinds=("realism",)` removes every realism block, so the pocket-watch ratio is "all realism on
this subject" = contact_ground + glass_caustics; contact_ground's AO is the smaller term. If the ratio is
above the cheap band, rerun once with only caustics removed — temporarily delete `glass_caustics` from a
`catalog_with_fixtures` copy of the catalog — to split the two.)

- [ ] **Step 2: Run** — `py -m pytest engine/tests/test_realism_blender.py -q -m blender -k smoke -s`.
Copy the two `*-COST` lines and the render-log seconds per frame into the Task 26 handoff and into the
calibration register rows "contact AO cost" and "caustics cost". Look at the three `sports_car` beauty
frames yourself (Read the PNGs): tyres touch the floor, a dark seam under the sills, no floating, no
visible faceting on the patch. Screenshots are the proof (owner rule): anything wrong is a bug to fix
now, with the frame named in the commit.

- [ ] **Step 3: Apply the cost rule for `glass_caustics`** (METHODS §0.1 cost classes, measured on the
keyframes tier):
  - render-time ratio ≤ 1.15 → cheap: keep, `costWeight` 1.0;
  - 1.15–1.6 → medium: keep, set `costWeight` to the measured ratio (rounded to 0.05);
  - > 1.6 → heavy: **remove the block from the shipped catalog** (move `engine/blocks/realism/glass_caustics`
    out, keep it in git history, drop its tests to `xfail(reason="deferred: measured cost X")`), add it to
    Deferred, and tell the owner in one plain sentence.
  Apply the same bands to the `sports_car` realism ratio; if it is above 1.15, find which block costs
  (skip one kind at a time is not possible inside `realism`, so bisect with pinned catalogs) and record it.

- [ ] **Step 4: Commit**

```bash
git add engine/tests/test_realism_blender.py engine/blocks/realism
git commit -m "test(realism): three-frame smoke renders and measured cost of contact AO and caustics"
```

---

### Task 26: Finish

- [ ] **Step 1: Full loops.** `py -m pytest engine/tests harness/tests corpus/tests -q -m "not live"` (the
Blender tests included; this is the one long run, ask the owner first if they are playing) — all pass.
- [ ] **Step 2: Scope check.** `git diff --name-only <Task 2's parent commit>..HEAD -- engine/director` prints
nothing (this plan never edits a director file). `git status` shows no stray fixture GLBs or `harness/out`
files staged.
- [ ] **Step 3: Hand-offs.** Send the phase-3 coordinator hand-offs H1–H3 below (one message, plain words).
- [ ] **Step 4: Handoff doc.** Invoke `session-handoff` (track `realism-defaults`): what landed per task,
the measured numbers (Task 7 soft/dangling sets, Task 15 patch lengths, Task 25 costs), what is left.
- [ ] **Step 5: Commit** the calibration-register updates (this plan file's register, with measured values
filled in) — `git add docs/superpowers/plans/2026-09-25-phase3-5-realism-defaults.md`, message
`docs(plan): phase 3.5 realism defaults - measured calibration values`.

---

## Calibration register — every (eng) number this plan introduces

None may be quoted as a quality fact until measured; each row says how (spec §4.8: calibrate before
gating; memory: calibrate before you model).

| Number(s) | Where | Calibrated through |
|---|---|---|
| `SINK_MM` per ground type, `MAX_SINK_FRAC` 0.1 | `physics/contact.py` | Golden renders of each ground world (phase 5 worlds); owner grade |
| `AO_DIST_FRAC` 0.05, AO samples 16, `occlusion` 0.8 | `contact.py`, `contact_ground` | PH-02 [M] seam ratio on goldens. **Task 25 measured (preview tier, sports_car, 3 frames, RTX 5080 OptiX):** AO samples 4 / 8 / 16 cost the same within noise (steady 0.935 / 1.011 / 0.965 s a frame) and denoise to the same image (mean abs diff 0.003 / 0.002 of 255 vs 16): kept 16. The whole-image effect of the seam is small (camera_01 all-realism vs none: mean abs diff 0.007 / 255) - strength judged at grading |
| `patchLenFrac` 0.45, `bulgeFrac` 0.25, `BULGE_FALLOFF` 0.3 | `tyre_contact`, `physics/tyre.py` | sports_car close tyre frames at final tier (owner grade); METHODS 60–200 mm patch |
| `PATCH_TOL` 0.2, `PATCH_MIN` 0.6, `FLAT_TOL_M` 0.5 mm, `GROUND_TOL_M` 1 mm | `physics/probes.py`, `realism_probe.py` | Task 15 measured patches on the fixture and sports_car |
| Wheel mask: `RADIAL_MAX` 1.05, `AXIAL_MARGIN` 0.05, `SPIN_AXIS_TOL` 0.05, `BAND_SLACK` 0.02, `DEFAULT_BAND` 0.62, `DEFAULT_HALF_WIDTH` 0.3 | `physics/wheel_mask.py` | Task 7 wheel extras on sports_car; any new vehicle upload. Review fixes 1/3 (Tasks 12-19 review): the compiler tests an island's radial reach against `RADIAL_MAX` r (the square box reached 1.48 r; sports_car reach 1.27 r -> 0.998 r) and tags tyre band only on the same wheel's parts (0 off-part tyre vertices on sports_car). Ingest keeps the square box |
| `RUBBER` classes, width p5–p95, band p5 | `measure.wheel_extras` | sports_car (GT3 RS: 275/335 mm tyres, 20/21 in rims) |
| `VEHICLE_TOY_M` 1.0, `OFFROAD_CLEARANCE` 0.9, `SPORT_RIDE_R` 0.35 (ride height / wheel radius; replaced `SPORT_HEIGHT_RATIO` 0.32, which read sedans as sport — review fix 9) | `measure.vehicle_facts` | More vehicle uploads (sports ~0.2-0.3 r, sedans ~0.4 r; sports_car 0.2 r); class is a hint only |
| `SNAP_OFF_FRAC` 0.15, `TREAD_SEARCH_HALF` 0.6 (tyre width = the tread island's axial box extent, review fix 11) | `measure._snap_center`, `measure.wheel_extras` | sports_car widths 0.256-0.266 m (2026-09-25 regen); a model with a known tyre size |
| `FLEX_CLASSES` fabric/skin (matte dropped, review fix 10), `FLEX_MIN_SHARE` 0.5 | `measure.dangling_parts` | Strap-bearing uploads; a painted rod must stay rigid |
| Soft cue: sheen > 0, subsurface > 0.2 or a normal map (roughness alone = low confidence, review fix 3) | `measure.soft_cue`, `measure.soft_parts` | Task 7 set (sneaker only high); rough stone/wood/cardboard uploads must read low. Ingest still counts a normal map (profiles not regenerated); `soft_rest` no longer does (next row) |
| Review item 6: `soft_rest` soft material = sheen > 0, subsurface > 0.2 or a soft word in the material name (`SOFT_WORDS` fabric/foam/plush/knit/felt/velvet...), vetoed by `HARD_WORDS` (rubber/(out)sole/plastic/metal/wood...); no cue = hard; a normal map is no cue | `soft_rest.soft_material` | **Measured 2026-09-25:** sneaker contact share 1.0 -> 0.0, dip 4.0 mm -> 0 on studio (was 9.2 mm before the cap); plush fixture (felt, sheen 1) unchanged: share 1.0, 4 mm on studio, 0.06 H on grass. `HARD_DIP_MAX_M` 4 mm kept: with the cue fixed it no longer carries the sneaker, it only limits genuinely soft goods on hard floors (plush 18 -> 4 mm); strength judged at the grading session |
| `WELD_DIST` 1e-6 (object units; glTF split copies are bit-identical) | `blender/islands.py` | Any upload whose islands split at hard edges; relative-to-bbox variant is optional (review low 19) |
| `RIDE_REACH` 1.5 (vehicle AO reach = max(5% H, 1.5 x ride height), review fix 7), `GAP_TOL_FRAC` 0.005 (gap tol = min(1 mm, 0.5% H)) | `physics/contact.py` | PH-02 seam ratio on car goldens; small-subject goldens |
| `MAX_DECEL_G` 1.2, `DIVE_RAMP_S` 0.25, `MAX_ZETA` 0.95 (review fix 4) | `physics/suspension.py` | Drive/stop goldens (phase 5) |
| `MIN_SQUASH` 0.5 (guard) | `physics/settle.py` | Guard only; the block range is 0.8-1 |
| `PREFLAT_FRAC` 0.6, `PREFLAT_TOL_M` 0.5 mm, `MAX_WHEEL_DROP_FRAC` 0.1 (sports_car rears modelled 15 mm up) | `physics/tyre.py`, `tyre_contact` | Uploads with scanned/loaded tyres; uploads with raked or lifted wheels |
| Review fix 4: `axle_plan` - a floating axle tilts the car about the grounded axle (sports_car 0.0061 rad); lone-wheel drop cap `MAX_SINGLE_DROP_M` 20 mm / `MAX_SINGLE_DROP_FRAC` 0.05 r; `AXLE_GAP_FRAC` 0.5 r; `DROP_EPS_M` 0.1 mm (sports_car's 3e-8 m residual). Review item 8: every wheel up (any axle count) first drops the whole vehicle rigidly by the smallest shared lift (`rigidDrop`, sports_car 0) | `physics/tyre.py`, `tyre_contact` | Raked uploads; hovering / 3-axle uploads; owner grade of the sports_car stance |
| `sinkFrac` 0.06, `bulgeFrac` 0.2, `SOFT_FALLOFF` 0.25 | `soft_rest`, `physics/contact.py` | Plush/pillow goldens (phase 5); owner grade |
| Review fix 6: `HARD_DIP_MAX_M` 4 mm on hard floors, `SOFT_CONTACT_MIN` 0.5 of the contact vertices on soft-cued materials, `CONTACT_BAND_FRAC` 0.02 H | `physics/contact.soft_dip_m`, `soft_rest` | **Owner grade flagged:** sneaker on studio 9.2 mm -> 4.0 mm (its one material carries a normal map, so its rubber sole reads soft: contact share 1.0); plush on studio 18 mm -> 4 mm, on grass the full 0.06 H |
| Static sag meaning: `sagFracR` x median wheel radius is how far the body sits below its modelled pose relative to the wheels (the model is assumed unloaded) (review low 17) | `suspension` | Owner grade of a static car; a model already modelled at ride height wants `sagFracR` 0 |
| `SOFT_MIN_SHARE` 0.5, `SOFT_HIGH_SHARE` 0.8, eligibility (hand/furniture, unrigged, wheel-less) | `measure.soft_parts` | Task 7 observed sets; false positives are bugs |
| `DANGLE_MIN_FRAC` 0.08, `DANGLE_ASPECT` 4, `ATTACH_FRAC` 0.02, hang/ground rules | `measure.dangling_parts` | Task 7 (expect none on the nine); strap-bearing uploads |
| `MOVE_FRAC` 0.02, `MIN_MOVE_S` 0.2, `DECEL_WINDOW_S` 0.25, `REST_Z_FRAC` 0.01 | `physics/events.py` | Phase-5 drive/drop golden clips |
| `ZETA` 0.5, `overshootFrac` 0.05, `settleS` 0.3, `squash` 0.92 | `physics/settle.py`, `landing_settle` | P-M01 "2 f landing shake"; owner grade of drop clips (phase 5) |
| `RIDE_HZ` per class, `PITCH_DEG_PER_G` 1.0, `damping` 0.4, `sagFracR` 0.015; `SETTLE_WINDOW_S` 2.0 replaced by `settle_window_s` = ln(`SETTLE_DECAY` 1000) / (zeta w) (review fix 5: 0.7 Hz at zeta 0.2 needs 7.9 s) | `physics/suspension.py`, `suspension` | METHODS VD-01 bands; drive/stop goldens (phase 5); PH-10 [V]. **Cost note (review item 14):** a car that stops or lands keys `valora_rz_body` on every frame 1..n (not only the event windows), so every frame re-evaluates all of the car's modifiers and Cycles re-syncs its mesh: the Task 25 still-car case measured that at 8x (keyframes 12.0 s vs 1.7 s on sports_car). Keying only the windows would not help (an action anywhere animates the driver); measure on a phase-5 drive clip before optimising |
| `BEAUFORT_UPPER`, `CALM_MS` 0.3, `GUST_WAVELENGTH_M` 12, `TURB_SCALE_M` 1.5, wind default 0.8 m/s | `physics/wind.py`, `field/wind` | Beaufort visual cues (flags extend F3, leaves F4–5) once flags/leaves exist (phase 5) |
| `DRIFT_DEPTH` 0.35, `DRIFT_SCALE` 1.5 | `haze_volume` | A windy haze golden (phase 5 worlds) |
| `MAX_BEND_DEG` 25, `DRAG_K` 0.02, stiffness/flutter defaults | `physics/sway.py`, sway blocks | golden_field grass (phase 5); strap uploads. Dangling parts turn rigidly about the pivot by atan(bend) (review fix, Task 21): strap fixture stretch <= 2e-7 of length, swing 18.3 deg at 5 m/s, 25.0 deg at 15 m/s (flutter clamped under the cap). Foliage (review item 4): the u^2 shear keeps each point u x len from its root (`sway.bend_point`, lowered by uL - sqrt(uL^2 - d^2)); test lawn stretch 6e-8 of blade length (was up to 39%) |
| Review item 1: `VISIBLE_DEG` 0.5 at the gust peak `peak_speed` = s (1 + gustiness + turbulence): below it (and in still air) neither sway block installs a deformer | `physics/sway.moves`, `dangling_sway`, `foliage_sway` | **Measured 2026-09-25 (no render, depsgraph frame_set, 10 frames):** a Scene-Time pivot tree on every sports_car mesh (1.94 M vertices, 369 objects) costs 34.9 ms a frame vs 0.2 ms without; strap fixture 0.4 ms vs 0.03 ms. On top: Cycles re-syncs every re-evaluated mesh each frame (Task 25's analogue: 8x at keyframes). Studio clips (0 m/s) now install nothing; the outdoor 0.8 m/s default still sways (1.1 deg at the gust peak) |
| `MARGIN_FRAC` 0.15, `leanFrac` 0.5; review items 2/3/5: `PRESSED_Z` 2 mm and the box test replaced by an underside heightfield (`GRID_N` 96 cells on the longest side, every subject vertex lowers its 4 grid points, holes filled, grown `GROW_FRAC` 0.02 x longest, 3x3 min floor; `contact.underside_fill` / `underside_floor`) parented to the realism offset (follows motion), ray-cast from below; a blade (mesh island, roots = `valora_sway` 0) with any point under it lies wholly `CLEAR_M` 1 mm under the lowest underside it meets. Probe: `UNDER_TOL_M` 0.5 mm, `COVER_Z` 0.5 mm, `CLEAR_OF_BOX` 0.05, `EDGE_SAMPLES` 9 | `ground_conform`, `realism_probe` | golden_field with a car and a product (phase 5). Test lawn: 42 blade points inside toycar with realism off, 0 with ground_conform. **Measured 2026-09-25:** toycar 20 pressed / 4 ring blades, ring tips 27 mm outward, 0 points above the underside; toycar sliding 1.0 x longest: 0 at frames 1/30/90 (the frame-1 footprint gave 11 at frame 30); sports_car: 0, blades under its floor stand to a median tip height of 93 mm (were 2 mm). Per-point clamping alone left 48 (blades straddling the silhouette, see-through gaps, grid steps). **Independent review P1 (2026-09-25):** the heightfield is baked once at frame 1 and follows only the rigid offset, so ground_conform is gated off for rigged subjects and played clips (`profileNot` rigged, `motionNot` playsClip, as dangling_sway). Suspension travel (static sag `sagFracR` 0.015 r, dive/squat under `PITCH_DEG_PER_G` 1 deg/g: a few mm on a car) also moves the underside after the bake: **accepted**, not re-baked; revisit if a phase-5 drive golden shows a blade tip through the floor |
| `N_MAX` 4000, `MOTE_PX` 1.5, `WANDER_FRAC` 0.05, `density` 0.2; review item 10: `FADE_FRAC` 0.1 (motes shrink to 0 near a wrap face), size from the median metres-per-pixel over camera keys with each key's own lens (was a fixed 50 mm) and the frame's long side (`SHORT_PX` 1080 x long/short: the 36 mm sensor spans the long side; a 16:9 mote was 2.67 px, now 1.5 px, independent-review P2), pocket radius imported from haze_volume `POCKET` | `shaft_dust` | Backlit haze goldens. The calibrated haze-lift test still passes with the motes; toycar probe: radius near a wrap face < 10% of full at frames 1/45/90; projected diameter 1.5 px at 28 mm 16:9 and 85 mm 1:1 |
| Review item 9: `CAUSTIC_MIN` 0.2 caster weight = transmission x Base Color luminance; no light objects -> no MNEE flags | `glass_caustics` | pocket_watch weight 1.0, camera_01 0.8 (both still cast); a smoked-glass upload |
| Caustics cost bands 1.15 / 1.6 | Task 25 | METHODS §0.1 classes. **Measured (preview, steady frames 2-3):** camera_01 1.28x, pocket_watch 0.99x (its glass is inside the closed case: no caustic reaches the floor) -> medium band, kept, `costWeight` 1.3 (= the worst measured, rounded). No see-through glass subject exists to show a caustic; judge again on one |
| Realism render cost (Task 25) | all realism blocks | sports_car preview steady 0.968 s vs 0.928 s a frame (1.04x, cheap) after the still-car suspension fix; before it, keyframes tier 12.0 s vs 1.7 s (8x: one key on the body driver re-synced the car every frame) |
| `seamRatio` 1.3 | `harness/thresholds.json` PH-02 | Known-good studio renders (harness calibrate flow) |

## Deferred (and why)

- **Body roll and steering (VD-03..05), spoke-strobe guard (VD-02, V-M01), road micro-vibration (VD-06):**
  need a driven path with curvature and a spoke count — phase 5 `drive`.
- **Tyre patch while airborne; tracks behind moving wheels (CD-05); grass parting behind a moving subject
  (HF-06 dynamic); dust kick and spray (VD-11/12):** need moving subjects on soft/wet worlds — phase 5.
- **Straps swinging from the subject's own acceleration:** wind-only sway in this phase; the
  acceleration-driven swing needs moving subjects — phase 5.
- **A cushion dipping under another object (CD-03 loaded):** needs multi-object scenes (props, characters).
- **Blender WIND force field for particles and cloth, and its per-consumer calibration (METHODS §2.9):**
  nothing uses it until phase 5 weather / phase 6 sims.
- **PH-01 [M]/[V], PH-06, PH-09, PH-10:** need higher resolution, dense frames or the vision judge (phase 6 QC).
- **Owner grading of realism** — after all phases (owner rule 2026-09-24); golden renders then.
- **`sim` kind, `sim_hygiene`, bake stage, collision proxies:** phase 6 (PHASING §2).

## Hand-offs to other lanes

- **H1 (phase 3, now):** vocabulary block-only tags listed in Task 1 Step 2 (if not already there).
- **H2 (phase 3, when convenient):** `Catalog.capabilities(profile)` counts an always-on block as delivering
  its tags from `requiresProfile` alone. Realism uses the richer `appliesWhen`; a "make the tyres squish" ask on a
  floating subject is reported delivered though `tyre_contact` will not apply. Suggest
  `capabilities(profile, script=None)` calling `engine.physics.applies.match` when a script is given.
- **H3 (phase 3/4):** director support for wind — add `field/wind` to the menu and output schema, flip
  `directorSelectable` to true, give the block `capabilities: ["wind.breeze", "wind.strong"]`, add a taste
  rule; phase 4 adds the wind-strength dice axis (PHASING §2 phase 4). Until then "windy" stays honestly
  unsupported and every clip is still air unless a hand-written script sets wind.
- **H4 (phase 5/6):** Blender WIND force field + per-consumer strength calibration (METHODS §2.9).
- **H5 (phase 5 `drive`):** set `subjectMotion: {"translates": true, "stops": ...}`, derive heading from its
  own path (ingest's `forwardAxis` has no trustworthy sign), make `wheel_spin.slip` curvature-aware, add
  `rollDegPerG` and the strobe guard.
- **H6 (phase 5 worlds):** outdoor worlds follow the foliage contract (Task 20: `valora_foliage` tag,
  one mesh island per blade/stem with its root points at `valora_sway` 0, `valora_sway`, `valora_sway_len`),
  tag their floor `valora_ground`, declare `groundType`, `hasFoliage`, `windDefault`. Done (review item 5):
  `ground_conform` counts and presses blades by mesh island and roots them at `valora_sway` 0, so the
  test lawn's three-vertex assumption is gone; a world whose blades share vertices must split them.

## Owner-only items

- **O1 — say OK before Task 7:** nine headless ingest launches, no rendering, 1–3 minutes.
- **O2 — say OK before Task 25 (and Task 26 Step 1 if you are playing):** four tiny three-frame renders.
- Nothing else: no accounts, keys or purchases. Grading waits for the all-phases session.

## Open questions (recommended answer first)

1. **Default wind:** keep BLOCKS' 0.8 m/s field default for outdoor worlds, with each world setting its own
   `windDefault` (studio 0 = still air)? **Recommend yes** — "calm unless asked" holds indoors, and light air
   outdoors is what real exteriors look like.
2. **Glass caustics if not cheap:** apply Task 25's bands (keep ≤ 1.6× with a measured `costWeight`, defer
   above)? **Recommend yes.**
3. **May hand-written and harness scripts pin realism params?** **Recommend yes** (calibration needs it);
   the director still never writes `realism` (phase-3 `OWNED`).
4. **Soft detection stays conservative** (only small, unrigged, wheel-less, ≥ 80% fabric/skin parts)?
   **Recommend yes:** a missed squash is invisible; a squashing watch is a visible bug.
5. **Dust motes at ~1.5 px instead of true 20–100 µm size?** **Recommend yes** (METHODS PT-01: true-size motes
   render as nothing).
6. **A per-job switch to turn realism off** (for a stylised floating look)? **Recommend no for now:**
   `placement: "float"` already removes every ground block; add a switch only if the owner asks.
7. **Contact occlusion changes every existing studio render slightly** (a darker seam). **Recommend keep it
   on** — its absence is a T1 signature (TIERS T1-X2) — and judge the strength (0.8) at the grading session.

## Done when

- The fast loop and the Blender loop pass; the Blender tests render nothing except Task 25's ≤ 3-frame smokes.
- Every checked script carries `wind` and the realism list the resolver chose, with `info` issues only; the
  director's first-pass metric is unaffected (no new `repaired` or `error` codes from realism).
- `sports_car` compiles with four flat tyre patches within ±20% of 0.45 r, grounded, body on its springs;
  `pocket_watch` gets caustic flags; soft, dangling and foliage blocks pass on the synthetic fixtures.
- PH-01 and PH-02 appear in harness reports (report-only).
- `git diff` over this plan's commits touches nothing under `engine/director/`.

## Owner answers (2026-09-25)

Owner standing instruction: follow Claude's recommendations. All seven open questions take the
recommended answer (wind 0.8 m/s outdoors / still studio; caustics kept up to 1.6x render time;
harness scripts may pin realism params; conservative soft-subject detection; dust motes ~1.5 px;
no per-job realism switch for now; keep the contact seam, strength judged at grading).
Task 7 profile regeneration and Task 25 three-frame smokes are pre-approved as light loads;
owner grading stays deferred until all phases are built.
