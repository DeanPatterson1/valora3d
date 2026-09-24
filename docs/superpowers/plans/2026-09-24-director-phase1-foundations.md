# Director Layer Phase 1 — Foundations Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the GPU-free core of the Valora3D director layer. It measures an uploaded model into a `SubjectProfile`, defines the `valora.scene/1` scene script and the block catalog, and checks and auto-repairs any scene script before it can render.

**Architecture:** A new stdlib-only Python package `engine/` at the repo root. It must stay importable inside Blender's bundled Python, because the phase-2 compiler reuses it there.

- **Blocks** are folders: `engine/blocks/<kind>/<id>/block.json`, plus `path.py` for cameras.
- **Camera paths are pure maths.** The checker (phase 1) and the compiler (phase 2) run the same function, so they can never disagree.
- **Ingest** is two halves: a tiny Blender script that dumps raw facts, and a pure function that turns them into a profile.

**Tech Stack:** Python 3.12 (dev) / Blender 5.0 bundled Python, stdlib only in `engine/`, pytest 8 for tests, Blender 5.0 at `C:\Program Files\Blender Foundation\Blender 5.0\blender.exe` (override with env `BLENDER_EXE`).

**Spec:** `docs/superpowers/specs/2026-09-24-director-layer-design.md` §4.1–4.4, §4.6. Later phases (compiler, director, variety, catalog growth, farm, research corpus) get their own plans.

**Conventions:**

- Run every command from the repo root `C:\Users\deand\Projects\rendering`.
- Use `py`, never bare `python`; bare `python` hits a Windows Store stub on this machine.
- Tests: `py -m pytest engine/tests -q`.
- Work on branch `renderer/director`.
- Each commit message ends with the two attribution lines given in the session. Run `git diff --cached --name-only` before every commit and stage only this plan's files.

---

## File map

| File | Responsibility |
|---|---|
| `engine/__init__.py` | Package marker, `SCHEMA = "valora.scene/1"` |
| `engine/issues.py` | `Issue` record (code, path, message, severity) |
| `engine/catalog.py` | Load and validate block manifests; `Catalog.get`, `Catalog.load_camera_path` |
| `engine/blocks/**/block.json` | Six starter manifests (world, lighting, 2 cameras, motion, grade) |
| `engine/blocks/camera/*/path.py` | `sample(params, profile, u) -> Pose` for each camera |
| `engine/profile.py` | `SubjectProfile` dataclass + JSON round-trip |
| `engine/geometry.py` | Vector maths, look-at projection, frame coverage |
| `engine/script.py` | Structural validation + param repair of a scene script |
| `engine/checker.py` | `check(script, profile, catalog) -> CheckResult`: structure + geometry + repair |
| `engine/ingest/measure.py` | Pure: raw Blender facts → `SubjectProfile` (units, size class, materials) |
| `engine/ingest/blender_extract.py` | Runs inside Blender: import GLB, dump raw facts JSON |
| `engine/ingest/run.py` | Launch Blender headless, call `measure.build_profile` |
| `engine/__main__.py` | CLI: `py -m engine check …`, `py -m engine ingest …` |
| `engine/tests/…` | One test file per module + fixtures |

---

## Chunk 1: Package, issues, catalog, starter blocks

### Task 1: Package skeleton and `Issue`

**Files:**
- Create: `engine/__init__.py`, `engine/issues.py`, `engine/tests/__init__.py`, `engine/tests/test_issues.py`

- [ ] **Step 1: Write the failing test** — `engine/tests/test_issues.py`

```python
from engine.issues import Issue, errors


def test_issue_to_dict_and_errors_filter():
    a = Issue("param_clamped", "shots[0].camera.params.lensMm", "clamped 500 to 135", "repaired")
    b = Issue("unknown_block", "world.id", "no world 'moon'", "error")
    assert a.to_dict() == {
        "code": "param_clamped",
        "path": "shots[0].camera.params.lensMm",
        "message": "clamped 500 to 135",
        "severity": "repaired",
    }
    assert errors([a, b]) == [b]
```

- [ ] **Step 2: Run it, expect FAIL** — `py -m pytest engine/tests/test_issues.py -q` → `ModuleNotFoundError: No module named 'engine'`

- [ ] **Step 3: Implement**

`engine/__init__.py`:
```python
"""Valora3D director engine: scene scripts, block catalog, checker, ingest.

Stdlib only — this package is also imported inside Blender's bundled Python.
"""

SCHEMA = "valora.scene/1"
```

`engine/tests/__init__.py`: empty file.

`engine/issues.py`:
```python
from dataclasses import dataclass, asdict

SEVERITIES = ("repaired", "error")


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    message: str
    severity: str  # "repaired" (fixed in place) or "error" (must go back to the director)

    def __post_init__(self):
        if self.severity not in SEVERITIES:
            raise ValueError(f"bad severity {self.severity!r}")

    def to_dict(self) -> dict:
        return asdict(self)


def errors(issues):
    return [i for i in issues if i.severity == "error"]
```

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests/test_issues.py -q` → `1 passed`

- [ ] **Step 5: Commit**
```bash
git add engine/__init__.py engine/issues.py engine/tests/__init__.py engine/tests/test_issues.py
git commit -m "feat(engine): package skeleton and Issue record"
```

### Task 2: Starter block manifests

Six blocks, **manifests only**: their Blender `build.py` files are phase 2. Every camera
block must declare `distance` (in bounding-sphere radii), `lensMm` and `fstop`, plus
`"framing": "full"` or `"detail"`. The checker's repair relies on these.

**Files:** create each `block.json` below.

- [ ] **Step 1: Create `engine/blocks/world/studio_cyc/block.json`**
```json
{
  "id": "studio_cyc",
  "kind": "world",
  "description": "Seamless curved studio backdrop (cyclorama). Clean, premium, product-ad look. Tone ranges from white to near-black.",
  "params": {
    "tone": {"type": "enum", "values": ["white", "grey", "black"], "default": "grey"},
    "floorGloss": {"type": "number", "min": 0.0, "max": 1.0, "default": 0.2}
  },
  "hasGround": true,
  "subjectSizeM": [0.02, 8.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "costWeight": 1.0,
  "tags": {"mood": ["clean", "premium"], "energy": ["calm", "medium"], "palette": ["neutral"]}
}
```

- [ ] **Step 2: Create `engine/blocks/lighting/softbox_three_point/block.json`**
```json
{
  "id": "softbox_three_point",
  "kind": "lighting",
  "description": "Classic key, fill and rim softboxes sized to the subject. Even, flattering, commercial.",
  "params": {
    "keyAzimuthDeg": {"type": "number", "min": -180.0, "max": 180.0, "default": 35.0},
    "keyElevationDeg": {"type": "number", "min": 5.0, "max": 80.0, "default": 35.0},
    "fillRatio": {"type": "number", "min": 0.0, "max": 1.0, "default": 0.35},
    "rimStrength": {"type": "number", "min": 0.0, "max": 3.0, "default": 1.0},
    "colorTempK": {"type": "number", "min": 2500.0, "max": 9000.0, "default": 5600.0}
  },
  "subjectSizeM": [0.02, 8.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "costWeight": 1.0,
  "tags": {"mood": ["clean", "premium"], "energy": ["calm", "medium"], "palette": ["neutral", "warm"]}
}
```

- [ ] **Step 3: Create `engine/blocks/camera/low_hero_push/block.json`**
```json
{
  "id": "low_hero_push",
  "kind": "camera",
  "description": "Low camera looking up at the subject, slowly pushing in. Makes the subject feel heroic and big.",
  "framing": "full",
  "params": {
    "distance": {"type": "number", "min": 1.2, "max": 8.0, "default": 4.0},
    "azimuthDeg": {"type": "number", "min": -180.0, "max": 180.0, "default": 30.0},
    "heightFrac": {"type": "number", "min": 0.02, "max": 0.6, "default": 0.15},
    "pushFrac": {"type": "number", "min": 0.0, "max": 0.4, "default": 0.15},
    "lensMm": {"type": "number", "min": 18.0, "max": 135.0, "default": 35.0},
    "fstop": {"type": "number", "min": 1.4, "max": 16.0, "default": 2.8}
  },
  "subjectSizeM": [0.02, 8.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "costWeight": 1.0,
  "tags": {"mood": ["heroic", "premium"], "energy": ["medium"], "palette": []}
}
```

- [ ] **Step 4: Create `engine/blocks/camera/arc_orbit/block.json`**
```json
{
  "id": "arc_orbit",
  "kind": "camera",
  "description": "Camera travels a partial arc around the subject at a steady height. Shows form and silhouette. Never a full turntable.",
  "framing": "full",
  "params": {
    "distance": {"type": "number", "min": 1.2, "max": 8.0, "default": 5.0},
    "startAzimuthDeg": {"type": "number", "min": -180.0, "max": 180.0, "default": 0.0},
    "sweepDeg": {"type": "number", "min": -120.0, "max": 120.0, "default": 40.0},
    "elevationDeg": {"type": "number", "min": -5.0, "max": 60.0, "default": 15.0},
    "lensMm": {"type": "number", "min": 18.0, "max": 135.0, "default": 50.0},
    "fstop": {"type": "number", "min": 1.4, "max": 16.0, "default": 4.0}
  },
  "subjectSizeM": [0.02, 8.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "costWeight": 1.0,
  "tags": {"mood": ["clean", "premium"], "energy": ["calm", "medium"], "palette": []}
}
```

- [ ] **Step 5: Create `engine/blocks/motion/static/block.json`**
```json
{
  "id": "static",
  "kind": "motion",
  "description": "Subject does not move. The camera carries all the motion.",
  "params": {},
  "subjectSizeM": [0.02, 8.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "costWeight": 1.0,
  "tags": {"mood": [], "energy": ["calm", "medium", "hype"], "palette": []}
}
```

- [ ] **Step 6: Create `engine/blocks/grade/neutral_film/block.json`**
```json
{
  "id": "neutral_film",
  "kind": "grade",
  "description": "Gentle filmic grade: soft contrast, true colours, light bloom on highlights.",
  "params": {
    "contrast": {"type": "number", "min": 0.8, "max": 1.4, "default": 1.05},
    "saturation": {"type": "number", "min": 0.6, "max": 1.4, "default": 1.0},
    "bloom": {"type": "number", "min": 0.0, "max": 1.0, "default": 0.15}
  },
  "subjectSizeM": [0.02, 8.0],
  "aspects": ["9:16", "16:9", "1:1", "4:5"],
  "costWeight": 1.0,
  "tags": {"mood": ["clean"], "energy": ["calm", "medium", "hype"], "palette": ["neutral"]}
}
```

- [ ] **Step 7: Commit**
```bash
git add engine/blocks
git commit -m "feat(engine): six starter block manifests"
```

### Task 3: Catalog loader with manifest validation

**Files:**
- Create: `engine/catalog.py`, `engine/tests/test_catalog.py`

- [ ] **Step 1: Write the failing tests** — `engine/tests/test_catalog.py`

```python
import json
import pytest
from engine.catalog import Catalog, CatalogError, KINDS


def test_loads_starter_blocks():
    cat = Catalog.load()
    assert set(KINDS) == {"world", "lighting", "camera", "motion", "effect", "grade"}
    assert cat.get("world", "studio_cyc")["hasGround"] is True
    assert cat.get("camera", "arc_orbit")["framing"] == "full"
    assert cat.get("world", "moon") is None
    assert sorted(cat.ids("camera")) == ["arc_orbit", "low_hero_push"]


def _write(root, kind, bid, manifest):
    d = root / kind / bid
    d.mkdir(parents=True)
    (d / "block.json").write_text(json.dumps(manifest))


def _base(bid, kind="world", **extra):
    m = {"id": bid, "kind": kind, "description": "x", "params": {},
         "subjectSizeM": [0.1, 1.0], "aspects": ["9:16"], "costWeight": 1.0,
         "tags": {"mood": [], "energy": [], "palette": []}}
    m.update(extra)
    return m


def test_rejects_id_folder_mismatch(tmp_path):
    _write(tmp_path, "world", "a", _base("b"))
    with pytest.raises(CatalogError, match="id 'b' does not match folder 'a'"):
        Catalog.load(tmp_path)


def test_rejects_bad_param_spec(tmp_path):
    _write(tmp_path, "world", "a", _base("a", params={"x": {"type": "number", "min": 2, "max": 1, "default": 1}}))
    with pytest.raises(CatalogError, match="min > max"):
        Catalog.load(tmp_path)


def test_rejects_default_outside_range(tmp_path):
    _write(tmp_path, "world", "a", _base("a", params={"x": {"type": "number", "min": 0, "max": 1, "default": 5}}))
    with pytest.raises(CatalogError, match="default outside"):
        Catalog.load(tmp_path)


def test_camera_needs_framing_and_core_params(tmp_path):
    _write(tmp_path, "camera", "c", _base("c", kind="camera"))
    with pytest.raises(CatalogError, match="camera 'c' missing"):
        Catalog.load(tmp_path)
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_catalog.py -q` → `ModuleNotFoundError: No module named 'engine.catalog'`

- [ ] **Step 3: Implement** — `engine/catalog.py`

```python
"""Block catalog: every world/lighting/camera/motion/effect/grade the director may use.

The rulebook's menu is generated from these manifests (phase 3), so what the AI reads and
what the code builds cannot drift apart.
"""
import importlib.util
import json
from pathlib import Path

KINDS = ("world", "lighting", "camera", "motion", "effect", "grade")
ASPECTS = ("9:16", "16:9", "1:1", "4:5")
BLOCKS_DIR = Path(__file__).parent / "blocks"
_REQUIRED = ("id", "kind", "description", "params", "subjectSizeM", "aspects", "costWeight", "tags")
_CAMERA_PARAMS = ("distance", "lensMm", "fstop")


class CatalogError(ValueError):
    pass


def _check_param(where, name, spec):
    t = spec.get("type")
    if t == "number":
        lo, hi, d = spec.get("min"), spec.get("max"), spec.get("default")
        if not all(isinstance(v, (int, float)) for v in (lo, hi, d)):
            raise CatalogError(f"{where}: param '{name}' needs numeric min/max/default")
        if lo > hi:
            raise CatalogError(f"{where}: param '{name}' min > max")
        if not lo <= d <= hi:
            raise CatalogError(f"{where}: param '{name}' default outside [{lo}, {hi}]")
    elif t == "enum":
        vals = spec.get("values")
        if not vals or spec.get("default") not in vals:
            raise CatalogError(f"{where}: param '{name}' enum needs values containing default")
    elif t == "bool":
        if not isinstance(spec.get("default"), bool):
            raise CatalogError(f"{where}: param '{name}' bool needs a bool default")
    else:
        raise CatalogError(f"{where}: param '{name}' has unknown type {t!r}")


def _check_manifest(folder_kind, folder_id, m):
    where = f"{folder_kind}/{folder_id}"
    missing = [k for k in _REQUIRED if k not in m]
    if missing:
        raise CatalogError(f"{where}: missing keys {missing}")
    if m["id"] != folder_id:
        raise CatalogError(f"{where}: id '{m['id']}' does not match folder '{folder_id}'")
    if m["kind"] != folder_kind:
        raise CatalogError(f"{where}: kind '{m['kind']}' does not match folder '{folder_kind}'")
    lo, hi = m["subjectSizeM"]
    if not 0 < lo <= hi:
        raise CatalogError(f"{where}: bad subjectSizeM")
    bad = [a for a in m["aspects"] if a not in ASPECTS]
    if bad:
        raise CatalogError(f"{where}: unknown aspects {bad}")
    for name, spec in m["params"].items():
        _check_param(where, name, spec)
    if folder_kind == "camera":
        lacking = [p for p in _CAMERA_PARAMS if p not in m["params"]]
        if m.get("framing") not in ("full", "detail") or lacking:
            raise CatalogError(f"camera '{folder_id}' missing framing or params {lacking}")


class Catalog:
    def __init__(self, blocks, root):
        self._blocks = blocks  # {(kind, id): manifest}
        self._root = root

    @classmethod
    def load(cls, root=None):
        root = Path(root) if root else BLOCKS_DIR
        blocks = {}
        for kind in KINDS:
            kdir = root / kind
            if not kdir.is_dir():
                continue
            for bdir in sorted(p for p in kdir.iterdir() if p.is_dir()):
                mf = bdir / "block.json"
                if not mf.exists():
                    continue
                m = json.loads(mf.read_text(encoding="utf-8"))
                _check_manifest(kind, bdir.name, m)
                blocks[(kind, bdir.name)] = m
        return cls(blocks, root)

    def get(self, kind, bid):
        return self._blocks.get((kind, bid))

    def ids(self, kind):
        return [b for (k, b) in self._blocks if k == kind]

    def load_camera_path(self, bid):
        """Import engine/blocks/camera/<id>/path.py and return its sample() function."""
        f = self._root / "camera" / bid / "path.py"
        spec = importlib.util.spec_from_file_location(f"valora_camera_{bid}", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.sample
```

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests/test_catalog.py -q` → `5 passed`

- [ ] **Step 5: Commit**
```bash
git add engine/catalog.py engine/tests/test_catalog.py
git commit -m "feat(engine): block catalog loader with manifest validation"
```

---

## Chunk 2: SubjectProfile, geometry, camera paths

### Task 4: `SubjectProfile`

The profile's coordinates are **placed coordinates**:

- metres, Z up
- the subject centred on X/Y
- the lowest point at Z = 0

The compiler places the subject exactly this way, which is what lets the checker's maths
match the render.

**Files:**
- Create: `engine/profile.py`, `engine/tests/test_profile.py`, `engine/tests/fixtures/profile_watch.json`, `engine/tests/fixtures/profile_car.json`

- [ ] **Step 1: Create fixtures**

`engine/tests/fixtures/profile_watch.json`:
```json
{"schema": "valora.profile/1", "sizeM": [0.05, 0.012, 0.06], "boundsMin": [-0.025, -0.006, 0.0],
 "boundsMax": [0.025, 0.006, 0.06], "unitGuess": "m", "scaleConfidence": "high", "upAxis": "Z",
 "sizeClass": "macro", "categoryHint": "small-object", "materials": [], "polyCount": 12000,
 "rigged": false, "animated": false}
```

`engine/tests/fixtures/profile_car.json`:
```json
{"schema": "valora.profile/1", "sizeM": [4.5, 1.9, 1.3], "boundsMin": [-2.25, -0.95, 0.0],
 "boundsMax": [2.25, 0.95, 1.3], "unitGuess": "m", "scaleConfidence": "high", "upAxis": "Z",
 "sizeClass": "vehicle", "categoryHint": "vehicle-like", "materials": [], "polyCount": 400000,
 "rigged": false, "animated": false}
```

- [ ] **Step 2: Write the failing test** — `engine/tests/test_profile.py`

```python
import json
from pathlib import Path
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"


def test_round_trip_and_derived_values():
    raw = json.loads((FIX / "profile_car.json").read_text())
    p = SubjectProfile.from_dict(raw)
    assert p.to_dict() == raw
    assert p.center == (0.0, 0.0, 0.65)
    assert abs(p.radius - (2.25**2 + 0.95**2 + 0.65**2) ** 0.5) < 1e-9
    assert p.longest == 4.5
```

- [ ] **Step 3: Run, expect FAIL** — `py -m pytest engine/tests/test_profile.py -q` → `ModuleNotFoundError`

- [ ] **Step 4: Implement** — `engine/profile.py`

```python
"""SubjectProfile: what ingest measured about an uploaded model (spec §4.1)."""
from dataclasses import dataclass, field, asdict

PROFILE_SCHEMA = "valora.profile/1"


@dataclass
class SubjectProfile:
    sizeM: list            # [x, y, z] metres
    boundsMin: list        # placed coords: centred on XY, bottom at z=0
    boundsMax: list
    unitGuess: str         # "m" | "cm" | "mm" | "in" | "unknown"
    scaleConfidence: str   # "high" | "low"
    upAxis: str            # "Z" after glTF import; "unknown" if doubtful
    sizeClass: str         # macro | hand | furniture | vehicle | architectural
    categoryHint: str      # hint only — never gates a feature (spec §4.1)
    materials: list = field(default_factory=list)  # [{class, share}]
    polyCount: int = 0
    rigged: bool = False
    animated: bool = False
    schema: str = PROFILE_SCHEMA

    @classmethod
    def from_dict(cls, d):
        if d.get("schema") != PROFILE_SCHEMA:
            raise ValueError(f"not a {PROFILE_SCHEMA} document")
        return cls(**d)

    def to_dict(self):
        return asdict(self)

    @property
    def center(self):
        return tuple((a + b) / 2 for a, b in zip(self.boundsMin, self.boundsMax))

    @property
    def half(self):
        return tuple((b - a) / 2 for a, b in zip(self.boundsMin, self.boundsMax))

    @property
    def radius(self):
        return sum(h * h for h in self.half) ** 0.5

    @property
    def longest(self):
        return max(self.sizeM)
```

- [ ] **Step 5: Run, expect PASS** — `py -m pytest engine/tests/test_profile.py -q` → `1 passed`

- [ ] **Step 6: Commit**
```bash
git add engine/profile.py engine/tests/test_profile.py engine/tests/fixtures
git commit -m "feat(engine): SubjectProfile with placed-coordinate convention"
```

### Task 5: Geometry — projection and frame coverage

This matches Blender's default camera: sensor width 36 mm, `sensor_fit = AUTO`, where the
sensor spans the **larger** image dimension.

**Files:**
- Create: `engine/geometry.py`, `engine/tests/test_geometry.py`

- [ ] **Step 1: Write the failing tests** — `engine/tests/test_geometry.py`

```python
from engine.geometry import Pose, project, frame_stats, box_corners, point_in_box, aspect_wh


def test_aspect_parse():
    assert aspect_wh("9:16") == (9, 16)


def test_point_straight_ahead_projects_to_centre():
    pose = Pose(position=(0, -5, 1), target=(0, 0, 1), lens_mm=50)
    x, y, depth = project(pose, (0, 0, 1), "16:9")
    assert abs(x) < 1e-9 and abs(y) < 1e-9 and abs(depth - 5) < 1e-9


def test_point_behind_camera_has_negative_depth():
    pose = Pose(position=(0, -5, 1), target=(0, 0, 1), lens_mm=50)
    assert project(pose, (0, -10, 1), "16:9")[2] < 0


def test_frame_stats_full_box():
    # 1 m cube, 50 mm lens, 16:9. Coverage is set by the short vertical side:
    # vertical half-tan = 0.36 * 9/16 = 0.2025; front face at 5.0 m -> 1/5/0.2025/2 ≈ 0.494
    corners = box_corners((-0.5, -0.5, 0), (0.5, 0.5, 1))
    pose = Pose(position=(0, -5.5, 0.5), target=(0, 0, 0.5), lens_mm=50)
    s = frame_stats(pose, corners, "16:9")
    assert s["allInFront"] and s["inFrame"]
    assert 0.45 < s["coverage"] < 0.55


def test_frame_stats_overflow_when_too_close():
    corners = box_corners((-0.5, -0.5, 0), (0.5, 0.5, 1))
    pose = Pose(position=(0, -0.9, 0.5), target=(0, 0, 0.5), lens_mm=85)
    assert not frame_stats(pose, corners, "9:16")["inFrame"]


def test_point_in_box_with_margin():
    assert point_in_box((0.55, 0, 0.5), (-0.5, -0.5, 0), (0.5, 0.5, 1), margin=0.1)
    assert not point_in_box((0.7, 0, 0.5), (-0.5, -0.5, 0), (0.5, 0.5, 1), margin=0.1)
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_geometry.py -q` → `ModuleNotFoundError`

- [ ] **Step 3: Implement** — `engine/geometry.py`

```python
"""Camera maths shared by the checker (phase 1) and the compiler (phase 2). Stdlib only."""
import math
from dataclasses import dataclass

SENSOR_MM = 36.0
IN_FRAME_TOLERANCE = 1.02  # ndc beyond ±1.02 counts as out of frame


@dataclass(frozen=True)
class Pose:
    position: tuple
    target: tuple
    lens_mm: float


def aspect_wh(aspect):
    w, h = aspect.split(":")
    return int(w), int(h)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


def _basis(pose):
    fwd = _norm(_sub(pose.target, pose.position))
    up_world = (0.0, 0.0, 1.0) if abs(fwd[2]) < 0.999 else (0.0, 1.0, 0.0)
    right = _norm(_cross(fwd, up_world))
    up = _cross(right, fwd)
    return fwd, right, up


def _half_tans(pose, aspect):
    w, h = aspect_wh(aspect)
    half_big = (SENSOR_MM / 2) / pose.lens_mm
    if w >= h:
        return half_big, half_big * h / w
    return half_big * w / h, half_big


def project(pose, point, aspect):
    """Return (ndc_x, ndc_y, depth). ndc in [-1, 1] is inside the frame; depth <= 0 is behind."""
    fwd, right, up = _basis(pose)
    v = _sub(point, pose.position)
    depth = _dot(v, fwd)
    if depth <= 1e-9:
        return 0.0, 0.0, depth
    hx, hy = _half_tans(pose, aspect)
    return _dot(v, right) / depth / hx, _dot(v, up) / depth / hy, depth


def box_corners(lo, hi):
    return [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def point_in_box(p, lo, hi, margin=0.0):
    """margin is a fraction of each axis' size added on every side."""
    for i in range(3):
        pad = (hi[i] - lo[i]) * margin
        if not lo[i] - pad <= p[i] <= hi[i] + pad:
            return False
    return True


def frame_stats(pose, corners, aspect):
    pts = [project(pose, c, aspect) for c in corners]
    in_front = all(d > 0 for _, _, d in pts)
    if not in_front:
        return {"allInFront": False, "inFrame": False, "coverage": 0.0}
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    in_frame = max(map(abs, xs + ys)) <= IN_FRAME_TOLERANCE
    coverage = max((max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2)
    return {"allInFront": True, "inFrame": in_frame, "coverage": coverage}
```

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests/test_geometry.py -q` → `6 passed`

- [ ] **Step 5: Commit**
```bash
git add engine/geometry.py engine/tests/test_geometry.py
git commit -m "feat(engine): camera projection and frame coverage maths"
```

### Task 6: Camera path functions

`sample(params, profile, u)` returns a `Pose` at shot progress `u` ∈ [0, 1]. `distance` is
measured in bounding-sphere radii from the subject centre.

**Files:**
- Create: `engine/blocks/camera/low_hero_push/path.py`, `engine/blocks/camera/arc_orbit/path.py`, `engine/tests/test_camera_paths.py`

- [ ] **Step 1: Write the failing tests** — `engine/tests/test_camera_paths.py`

```python
import json
import math
from pathlib import Path
from engine.catalog import Catalog
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"
CAR = SubjectProfile.from_dict(json.loads((FIX / "profile_car.json").read_text()))


def _defaults(cat, bid):
    return {k: v["default"] for k, v in cat.get("camera", bid)["params"].items()}


def test_low_hero_push_moves_closer_and_stays_low():
    cat = Catalog.load()
    sample = cat.load_camera_path("low_hero_push")
    p = _defaults(cat, "low_hero_push")
    a, b = sample(p, CAR, 0.0), sample(p, CAR, 1.0)
    da = math.dist(a.position, CAR.center)
    db = math.dist(b.position, CAR.center)
    assert db < da
    assert a.position[2] <= 0.6 * CAR.sizeM[2]
    assert a.target == CAR.center and a.lens_mm == p["lensMm"]


def test_arc_orbit_sweeps_azimuth_at_constant_distance():
    cat = Catalog.load()
    sample = cat.load_camera_path("arc_orbit")
    p = _defaults(cat, "arc_orbit")
    a, b = sample(p, CAR, 0.0), sample(p, CAR, 1.0)
    assert abs(math.dist(a.position, CAR.center) - math.dist(b.position, CAR.center)) < 1e-9
    az = lambda q: math.degrees(math.atan2(q.position[1], q.position[0]))
    assert abs((az(b) - az(a)) - p["sweepDeg"]) < 1e-6
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_camera_paths.py -q` → `FileNotFoundError` for `path.py`

- [ ] **Step 3: Implement**

`engine/blocks/camera/low_hero_push/path.py`:
```python
import math
from engine.geometry import Pose

# Floor clearance so a "ground" camera never sits inside the floor plane.
MIN_HEIGHT_M = 0.03


def sample(params, profile, u):
    cx, cy, cz = profile.center
    d = profile.radius * params["distance"] * (1.0 - params["pushFrac"] * u)
    az = math.radians(params["azimuthDeg"])
    z = max(MIN_HEIGHT_M, params["heightFrac"] * profile.sizeM[2])
    pos = (cx + d * math.cos(az), cy + d * math.sin(az), z)
    return Pose(position=pos, target=(cx, cy, cz), lens_mm=params["lensMm"])
```

`engine/blocks/camera/arc_orbit/path.py`:
```python
import math
from engine.geometry import Pose


def sample(params, profile, u):
    cx, cy, cz = profile.center
    d = profile.radius * params["distance"]
    az = math.radians(params["startAzimuthDeg"] + params["sweepDeg"] * u)
    el = math.radians(params["elevationDeg"])
    horiz = d * math.cos(el)
    pos = (cx + horiz * math.cos(az), cy + horiz * math.sin(az), cz + d * math.sin(el))
    return Pose(position=pos, target=(cx, cy, cz), lens_mm=params["lensMm"])
```

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests/test_camera_paths.py -q` → `2 passed`

- [ ] **Step 5: Commit**
```bash
git add engine/blocks/camera engine/tests/test_camera_paths.py
git commit -m "feat(engine): pure-maths paths for low_hero_push and arc_orbit"
```

---

## Chunk 3: Script validation and the checker

### Task 7: Structural validation + param repair (`script.py`)

Rules come from spec §4.2:

- `schema` must be `valora.scene/1`, and `seed` a non-negative integer.
- `format.aspect` must be one of the 4 supported aspects, `durationS` in [3, 30], and
  `fps` in {24, 25, 30, 60}.
- `subject.placement` is `ground` or `float`.
- There is at least one shot, and every shot has `startS < endS`.
- Shots must be contiguous. Gaps or overlaps up to 0.05 s are snapped, and a last shot
  ending within 0.25 s of `durationS` is snapped to it. Anything larger is an error.
- Every block reference is `{"id", "params"}` with a known id.
- Params: unknown keys are dropped, missing keys get their default, out-of-range values
  are clamped, and a bad enum value is replaced by the default. Each of these is logged
  as `repaired`.
- The top-level key `audio` is reserved: an error "not in v1".

**Files:**
- Create: `engine/script.py`, `engine/tests/test_script.py`, `engine/tests/fixtures/script_valid.json`

- [ ] **Step 1: Create fixture** — `engine/tests/fixtures/script_valid.json`
```json
{
  "schema": "valora.scene/1",
  "seed": 184467,
  "direction": {"id": "clean-studio/low-hero/slow", "source": "dice"},
  "prompt": "make it look cool",
  "assumptions": ["no format given -> 9:16, 10 s"],
  "format": {"aspect": "9:16", "durationS": 10, "fps": 30},
  "subject": {"placement": "ground", "motion": {"id": "static", "params": {}}, "finishOverrides": []},
  "world": {"id": "studio_cyc", "params": {"tone": "black", "floorGloss": 0.4}},
  "lighting": {"id": "softbox_three_point", "params": {"keyAzimuthDeg": 40}},
  "shots": [
    {"startS": 0, "endS": 5, "camera": {"id": "low_hero_push", "params": {"distance": 4.0, "lensMm": 35}}, "focus": "subject"},
    {"startS": 5, "endS": 10, "camera": {"id": "arc_orbit", "params": {"lensMm": 50}}, "focus": "subject"}
  ],
  "effects": [],
  "grade": {"id": "neutral_film", "params": {}}
}
```

- [ ] **Step 2: Write the failing tests** — `engine/tests/test_script.py`

```python
import copy
import json
from pathlib import Path
from engine.catalog import Catalog
from engine.script import validate_and_repair

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()


def _script():
    return json.loads((FIX / "script_valid.json").read_text())


def codes(issues, severity=None):
    return sorted(i.code for i in issues if severity is None or i.severity == severity)


def test_valid_script_only_fills_defaults():
    out, issues = validate_and_repair(_script(), CAT)
    assert codes(issues, "error") == []
    assert out["lighting"]["params"]["fillRatio"] == 0.35  # default filled
    assert set(codes(issues)) == {"param_default"}


def test_input_not_mutated():
    s = _script()
    before = copy.deepcopy(s)
    validate_and_repair(s, CAT)
    assert s == before


def test_clamp_drop_and_bad_enum():
    s = _script()
    s["shots"][0]["camera"]["params"]["lensMm"] = 500
    s["shots"][0]["camera"]["params"]["wobble"] = 3
    s["world"]["params"]["tone"] = "purple"
    out, issues = validate_and_repair(s, CAT)
    assert out["shots"][0]["camera"]["params"]["lensMm"] == 135.0
    assert "wobble" not in out["shots"][0]["camera"]["params"]
    assert out["world"]["params"]["tone"] == "grey"
    assert {"param_clamped", "param_unknown_dropped", "param_bad_enum"} <= set(codes(issues, "repaired"))


def test_unknown_block_and_reserved_audio_are_errors():
    s = _script()
    s["world"]["id"] = "moon"
    s["audio"] = {"id": "synthwave"}
    _, issues = validate_and_repair(s, CAT)
    assert {"unknown_block", "reserved_not_in_v1"} <= set(codes(issues, "error"))


def test_small_shot_gap_snapped_large_gap_error():
    s = _script()
    s["shots"][1]["startS"] = 5.03
    s["shots"][1]["endS"] = 9.9
    out, issues = validate_and_repair(s, CAT)
    assert out["shots"][1]["startS"] == 5 and out["shots"][1]["endS"] == 10
    assert codes(issues, "error") == []
    s["shots"][1]["startS"] = 6
    _, issues = validate_and_repair(s, CAT)
    assert "shots_not_contiguous" in codes(issues, "error")


def test_malformed_input_is_error_not_crash():
    s = _script()
    s["format"] = "9:16"
    s["seed"] = True
    s["shots"][0].pop("startS")
    _, issues = validate_and_repair(s, CAT)
    assert {"bad_format", "bad_seed", "bad_shot_times"} <= set(codes(issues, "error"))


def test_bad_format_values():
    s = _script()
    s["format"] = {"aspect": "2:1", "durationS": 90, "fps": 12}
    _, issues = validate_and_repair(s, CAT)
    assert {"bad_aspect", "bad_duration", "bad_fps"} <= set(codes(issues, "error"))
```

- [ ] **Step 3: Run, expect FAIL** — `py -m pytest engine/tests/test_script.py -q` → `ModuleNotFoundError`

- [ ] **Step 4: Implement** — `engine/script.py`

```python
"""Structural validation and in-place-safe repair of a valora.scene/1 script (spec §4.2, §4.6)."""
import copy
from engine import SCHEMA
from engine.catalog import ASPECTS
from engine.issues import Issue

FPS = (24, 25, 30, 60)
DURATION_RANGE = (3, 30)
SNAP_GAP_S = 0.05
SNAP_END_S = 0.25
RESERVED = ("audio",)


def _repair_params(ref, manifest, path, issues):
    specs = manifest["params"]
    params = ref.setdefault("params", {})
    for k in [k for k in params if k not in specs]:
        del params[k]
        issues.append(Issue("param_unknown_dropped", f"{path}.params.{k}", f"'{k}' is not a param of {manifest['id']}", "repaired"))
    for k, spec in specs.items():
        p = f"{path}.params.{k}"
        if k not in params:
            params[k] = spec["default"]
            issues.append(Issue("param_default", p, f"filled default {spec['default']!r}", "repaired"))
            continue
        v = params[k]
        if spec["type"] == "number":
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                params[k] = spec["default"]
                issues.append(Issue("param_bad_type", p, f"{v!r} is not a number; used default", "repaired"))
            elif not spec["min"] <= v <= spec["max"]:
                params[k] = float(min(max(v, spec["min"]), spec["max"]))
                issues.append(Issue("param_clamped", p, f"clamped {v} to {params[k]}", "repaired"))
        elif spec["type"] == "enum" and v not in spec["values"]:
            params[k] = spec["default"]
            issues.append(Issue("param_bad_enum", p, f"{v!r} not in {spec['values']}; used default", "repaired"))
        elif spec["type"] == "bool" and not isinstance(v, bool):
            params[k] = spec["default"]
            issues.append(Issue("param_bad_type", p, f"{v!r} is not a bool; used default", "repaired"))


def _block(ref, kind, path, catalog, issues):
    if not isinstance(ref, dict) or "id" not in ref:
        issues.append(Issue("bad_block_ref", path, "expected {id, params}", "error"))
        return None
    m = catalog.get(kind, ref["id"])
    if m is None:
        issues.append(Issue("unknown_block", f"{path}.id", f"no {kind} '{ref['id']}' in catalog", "error"))
        return None
    _repair_params(ref, m, path, issues)
    return m


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _shots(s, issues):
    shots = s.get("shots") or []
    if not isinstance(shots, list) or not shots:
        issues.append(Issue("no_shots", "shots", "at least one shot required", "error"))
        return
    bad = [i for i, sh in enumerate(shots)
           if not isinstance(sh, dict) or not _num(sh.get("startS")) or not _num(sh.get("endS"))]
    if bad:
        for i in bad:
            issues.append(Issue("bad_shot_times", f"shots[{i}]", "startS and endS must be numbers", "error"))
        return
    dur = s["format"].get("durationS")
    if shots[0]["startS"] != 0:
        if abs(shots[0]["startS"]) <= SNAP_GAP_S:
            shots[0]["startS"] = 0
            issues.append(Issue("shot_snapped", "shots[0].startS", "snapped to 0", "repaired"))
        else:
            issues.append(Issue("shots_not_contiguous", "shots[0].startS", "first shot must start at 0", "error"))
    for i in range(1, len(shots)):
        prev_end, start = shots[i - 1]["endS"], shots[i]["startS"]
        if start != prev_end:
            if abs(start - prev_end) <= SNAP_GAP_S:
                shots[i]["startS"] = prev_end
                issues.append(Issue("shot_snapped", f"shots[{i}].startS", f"snapped {start} to {prev_end}", "repaired"))
            else:
                issues.append(Issue("shots_not_contiguous", f"shots[{i}].startS", f"gap/overlap {start} vs {prev_end}", "error"))
    last = shots[-1]
    if isinstance(dur, (int, float)) and last["endS"] != dur:
        if abs(last["endS"] - dur) <= SNAP_END_S:
            last["endS"] = dur
            issues.append(Issue("shot_snapped", f"shots[{len(shots) - 1}].endS", f"snapped to {dur}", "repaired"))
        else:
            issues.append(Issue("shots_not_contiguous", f"shots[{len(shots) - 1}].endS", f"last shot ends {last['endS']}, clip is {dur}", "error"))
    for i, sh in enumerate(shots):
        if not sh["startS"] < sh["endS"]:
            issues.append(Issue("bad_shot_times", f"shots[{i}]", "startS must be < endS", "error"))


def validate_and_repair(script, catalog):
    """Return (repaired_copy, issues). Never mutates the input."""
    s = copy.deepcopy(script)
    issues = []
    if s.get("schema") != SCHEMA:
        issues.append(Issue("bad_schema", "schema", f"expected {SCHEMA}", "error"))
    if not isinstance(s.get("seed"), int) or isinstance(s["seed"], bool) or s["seed"] < 0:
        issues.append(Issue("bad_seed", "seed", "seed must be a non-negative integer", "error"))
    for key in RESERVED:
        if key in s:
            issues.append(Issue("reserved_not_in_v1", key, f"'{key}' is reserved and not supported in v1", "error"))
    # The director is an LLM: malformed shapes must become errors, never crashes.
    for key in ("format", "subject"):
        if not isinstance(s.get(key), dict):
            issues.append(Issue(f"bad_{key}", key, f"'{key}' must be an object", "error"))
            s[key] = {}
    for i, sh in enumerate(s.get("shots") or []):
        if isinstance(sh, dict) and not isinstance(sh.get("camera"), dict):
            sh["camera"] = None
    fmt = s["format"]
    if fmt.get("aspect") not in ASPECTS:
        issues.append(Issue("bad_aspect", "format.aspect", f"must be one of {ASPECTS}", "error"))
    d = fmt.get("durationS")
    if not isinstance(d, (int, float)) or not DURATION_RANGE[0] <= d <= DURATION_RANGE[1]:
        issues.append(Issue("bad_duration", "format.durationS", f"must be in {DURATION_RANGE}", "error"))
    if fmt.get("fps") not in FPS:
        issues.append(Issue("bad_fps", "format.fps", f"must be one of {FPS}", "error"))
    subj = s["subject"]
    if subj.get("placement") not in ("ground", "float"):
        issues.append(Issue("bad_placement", "subject.placement", "ground or float", "error"))
    _block(subj.get("motion"), "motion", "subject.motion", catalog, issues)
    _block(s.get("world"), "world", "world", catalog, issues)
    _block(s.get("lighting"), "lighting", "lighting", catalog, issues)
    _block(s.get("grade"), "grade", "grade", catalog, issues)
    for i, fx in enumerate(s.get("effects", [])):
        _block(fx, "effect", f"effects[{i}]", catalog, issues)
    for i, sh in enumerate(s.get("shots") or []):
        if not isinstance(sh, dict):
            continue  # reported by _shots
        _block(sh.get("camera"), "camera", f"shots[{i}].camera", catalog, issues)
        if sh.get("focus", "subject") != "subject":
            issues.append(Issue("bad_focus", f"shots[{i}].focus", "v1 supports focus 'subject' only", "error"))
    _shots(s, issues)
    return s, issues
```

- [ ] **Step 5: Run, expect PASS** — `py -m pytest engine/tests/test_script.py -q` → `7 passed`

- [ ] **Step 6: Commit**
```bash
git add engine/script.py engine/tests/test_script.py engine/tests/fixtures/script_valid.json
git commit -m "feat(engine): scene script structural validation and param repair"
```

### Task 8: Checker — geometry, compatibility, distance repair

Rules (spec §4.4 hard rules / §4.6):

- **Subject size:** the world and every camera must support the subject's longest side
  (`subjectSizeM`) and the script's aspect.
- **World ground:** `placement: ground` needs a world with `hasGround: true`.
- **Sampling:** each shot is sampled at 12 evenly spaced `u` values.
- **Camera position:** never inside the subject box inflated by 10%, and never below
  2 cm above the floor.
- **`full` framing:** every sample must have all corners in front of the camera, be in
  frame, and have coverage ≥ 0.25.
- **`detail` framing:** only the position and floor rules apply.
- **Repair:** the checker only ever changes `distance`, by ×1.15 steps, for at most 12
  iterations, staying inside the block's range.
  - Inside the box or out of frame: move out.
  - Coverage below 0.25: move in.
  - Each change is logged `repaired` as `camera_distance_adjusted`.
  - If a shot still fails, it is an `error`.

**Files:**
- Create: `engine/checker.py`, `engine/tests/test_checker.py`

- [ ] **Step 1: Write the failing tests** — `engine/tests/test_checker.py`

```python
import json
from pathlib import Path
from engine.catalog import Catalog
from engine.checker import check
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()


def _load(name):
    return json.loads((FIX / name).read_text())


def _codes(result, severity):
    return {i.code for i in result.issues if i.severity == severity}


def test_valid_script_passes_for_car_and_watch_without_camera_repair():
    # Default distances (4.0 / 5.0 radii) must frame both a wide 4.5 m car and a 6 cm watch
    # in 9:16 as-is. If this fails, raise the block DEFAULT to the value the checker
    # converges to (rounded up) — never loosen MIN_COVERAGE or the in-frame rule.
    for prof in ("profile_car.json", "profile_watch.json"):
        r = check(_load("script_valid.json"), SubjectProfile.from_dict(_load(prof)), CAT)
        assert r.ok, [i.to_dict() for i in r.issues if i.severity == "error"]
        assert "camera_distance_adjusted" not in _codes(r, "repaired"), prof


def test_camera_too_close_is_pushed_out():
    s = _load("script_valid.json")
    s["shots"][1]["camera"]["params"].update({"distance": 1.2, "lensMm": 35})
    r = check(s, SubjectProfile.from_dict(_load("profile_car.json")), CAT)
    assert r.ok
    assert "camera_distance_adjusted" in _codes(r, "repaired")
    assert r.script["shots"][1]["camera"]["params"]["distance"] > 1.2


def test_tiny_subject_far_away_is_pulled_in():
    s = _load("script_valid.json")
    s["shots"][1]["camera"]["params"].update({"distance": 8.0, "lensMm": 18})
    r = check(s, SubjectProfile.from_dict(_load("profile_watch.json")), CAT)
    assert r.ok
    assert r.script["shots"][1]["camera"]["params"]["distance"] < 8.0


def test_subject_outside_supported_size_is_an_error_not_a_repair():
    prof = _load("profile_car.json")
    prof["sizeM"] = [30.0, 10.0, 10.0]
    prof["boundsMin"] = [-15.0, -5.0, 0.0]
    prof["boundsMax"] = [15.0, 5.0, 10.0]
    r = check(_load("script_valid.json"), SubjectProfile.from_dict(prof), CAT)
    assert not r.ok and "subject_size_unsupported" in _codes(r, "error")


def test_unfixable_framing_is_an_error(monkeypatch):
    # 35 mm converges unpatched (see the test above); only the narrowed range makes it fail.
    import engine.checker as chk
    s = _load("script_valid.json")
    s["shots"][1]["camera"]["params"].update({"distance": 1.2, "lensMm": 35})
    real_get = CAT.get

    def narrow(kind, bid):
        m = real_get(kind, bid)
        if kind == "camera" and bid == "arc_orbit":
            m = {**m, "params": {**m["params"], "distance": {**m["params"]["distance"], "max": 1.2}}}
        return m

    monkeypatch.setattr(CAT, "get", narrow)
    r = chk.check(s, SubjectProfile.from_dict(_load("profile_car.json")), CAT)
    assert not r.ok and "framing_unfixable" in _codes(r, "error")


def test_float_placement_world_without_ground_ok_and_structure_errors_propagate():
    s = _load("script_valid.json")
    s["world"]["id"] = "moon"
    r = check(s, SubjectProfile.from_dict(_load("profile_car.json")), CAT)
    assert not r.ok and "unknown_block" in _codes(r, "error")
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_checker.py -q` → `ModuleNotFoundError`

- [ ] **Step 3: Implement** — `engine/checker.py`

```python
"""The checker: nothing renders unless check() returns ok (spec §4.6)."""
from dataclasses import dataclass, field
from engine.geometry import box_corners, frame_stats, point_in_box
from engine.issues import Issue, errors
from engine.script import validate_and_repair

SAMPLES_PER_SHOT = 12
BOX_MARGIN = 0.10
MIN_CAMERA_Z = 0.02
MIN_COVERAGE = 0.25
STEP = 1.15
MAX_STEPS = 12


@dataclass
class CheckResult:
    ok: bool
    script: dict
    issues: list = field(default_factory=list)


def _shot_verdict(sample, params, profile, framing, aspect):
    """Return 'ok', 'out' (move camera away) or 'in' (move closer)."""
    corners = box_corners(profile.boundsMin, profile.boundsMax)
    worst_small = False
    for k in range(SAMPLES_PER_SHOT):
        pose = sample(params, profile, k / (SAMPLES_PER_SHOT - 1))
        if pose.position[2] < MIN_CAMERA_Z:
            return "out"
        if point_in_box(pose.position, profile.boundsMin, profile.boundsMax, BOX_MARGIN):
            return "out"
        if framing == "full":
            st = frame_stats(pose, corners, aspect)
            if not st["allInFront"] or not st["inFrame"]:
                return "out"
            if st["coverage"] < MIN_COVERAGE:
                worst_small = True
    return "in" if worst_small else "ok"


def _fix_shot(i, shot, catalog, profile, aspect, issues):
    ref = shot["camera"]
    m = catalog.get("camera", ref["id"])
    sample = catalog.load_camera_path(ref["id"])
    spec = m["params"]["distance"]
    params = ref["params"]
    start = params["distance"]
    tried = set()
    for _ in range(MAX_STEPS + 1):  # +1 so the last step taken is also verified
        verdict = _shot_verdict(sample, params, profile, m["framing"], aspect)
        if verdict == "ok":
            if params["distance"] != start:
                issues.append(Issue("camera_distance_adjusted", f"shots[{i}].camera.params.distance",
                                    f"{start} -> {params['distance']:.3f}", "repaired"))
            return
        nxt = params["distance"] * (STEP if verdict == "out" else 1 / STEP)
        nxt = min(max(nxt, spec["min"]), spec["max"])
        key = round(nxt, 6)
        if key in tried or nxt == params["distance"]:
            break
        tried.add(key)
        params["distance"] = nxt
    params["distance"] = start
    issues.append(Issue("framing_unfixable", f"shots[{i}].camera",
                        f"no distance in [{spec['min']}, {spec['max']}] frames the subject", "error"))


def _compat(s, catalog, profile, issues):
    aspect = s["format"]["aspect"]
    size = profile.longest
    refs = [("world", "world", s["world"]), ("lighting", "lighting", s["lighting"])]
    refs += [("camera", f"shots[{i}].camera", sh["camera"]) for i, sh in enumerate(s["shots"])]
    for kind, path, ref in refs:
        m = catalog.get(kind, ref["id"])
        lo, hi = m["subjectSizeM"]
        if not lo <= size <= hi:
            issues.append(Issue("subject_size_unsupported", path,
                                f"{ref['id']} supports {lo}-{hi} m, subject is {size:.3f} m", "error"))
        if aspect not in m["aspects"]:
            issues.append(Issue("aspect_unsupported", path, f"{ref['id']} does not support {aspect}", "error"))
    if s["subject"]["placement"] == "ground" and not catalog.get("world", s["world"]["id"]).get("hasGround"):
        issues.append(Issue("world_has_no_ground", "world.id", "placement 'ground' needs a world with a ground", "error"))


def check(script, profile, catalog):
    s, issues = validate_and_repair(script, catalog)
    if errors(issues):
        return CheckResult(False, s, issues)
    _compat(s, catalog, profile, issues)
    if errors(issues):
        return CheckResult(False, s, issues)
    for i, shot in enumerate(s["shots"]):
        _fix_shot(i, shot, catalog, profile, s["format"]["aspect"], issues)
    return CheckResult(not errors(issues), s, issues)
```

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests/test_checker.py -q` → `6 passed`. If `test_valid_script_passes_for_car_and_watch` fails on coverage, print `frame_stats` for the failing sample, and fix the **fixture's** params before touching any threshold. The thresholds are spec rules.

- [ ] **Step 5: Full suite** — `py -m pytest engine/tests -q` → all pass

- [ ] **Step 6: Commit**
```bash
git add engine/checker.py engine/tests/test_checker.py
git commit -m "feat(engine): checker with compatibility, framing and distance repair"
```

---

## Chunk 4: Ingest and CLI

### Task 9: Pure measurement — raw facts → profile

**Raw facts format**, written by the Blender script in Task 10:
```json
{"boundsMin": [x,y,z], "boundsMax": [x,y,z], "polyCount": 0, "rigged": false, "animated": false,
 "materials": [{"area": 0.0, "metallic": 0.0, "roughness": 0.5, "transmission": 0.0,
                "emission": 0.0, "subsurface": 0.0}]}
```
Bounds are world-space in glTF metres (Z up after Blender's glTF import).

**Units** (spec §4.1; glTF says metres, but exporters lie):

- If the longest side in metres is in [0.02, 30], keep `m` (`scaleConfidence: high`).
- If it is larger than 30, try `mm` first (typical of CAD) and then `cm`. Take the first
  that lands in [0.02, 30] (`low`).
- If it is smaller than 0.02, the result is `unknown`, scale is kept, and confidence is
  `low`.

**Size classes:** macro < 0.1 m, hand < 0.5 m, furniture < 2.5 m, vehicle < 8 m, and
architectural above that.

**Category hint:**

- `vehicle-like` when the longest side is 2.5–7 m, height is under 0.6 × longest, and
  length is at least 2 × width.
- Otherwise `small-object` below 0.5 m, then `large-object`.

**Material class**, first match wins:

1. emissive if `emission > 0.5`
2. glass if `transmission > 0.5`
3. skin if `subsurface > 0.2`
4. metal if `metallic > 0.5`
5. glossy if `roughness < 0.25`
6. fabric if `roughness > 0.7`
7. otherwise matte

Shares are area-weighted.

**Files:**
- Create: `engine/ingest/__init__.py`, `engine/ingest/measure.py`, `engine/tests/test_measure.py`

- [ ] **Step 1: Write the failing tests** — `engine/tests/test_measure.py`

```python
from engine.ingest.measure import infer_units, size_class, material_class, build_profile


def test_units():
    assert infer_units(4.5) == ("m", 1.0, "high")
    assert infer_units(300.0) == ("mm", 0.001, "low")      # 30 cm shoe authored in mm
    assert infer_units(4500.0) == ("mm", 0.001, "low")     # car in mm
    assert infer_units(0.001) == ("unknown", 1.0, "low")


def test_size_class():
    assert [size_class(v) for v in (0.05, 0.3, 1.2, 4.5, 20)] == \
        ["macro", "hand", "furniture", "vehicle", "architectural"]


def test_material_class_priority():
    assert material_class({"emission": 1, "transmission": 1}) == "emissive"
    assert material_class({"metallic": 1, "roughness": 0.1}) == "metal"
    assert material_class({"roughness": 0.1}) == "glossy"
    assert material_class({"roughness": 0.9}) == "fabric"
    assert material_class({"roughness": 0.5}) == "matte"


def test_build_profile_rescales_recentres_and_grounds():
    raw = {"boundsMin": [1000, -950, 200], "boundsMax": [5500, 950, 1500], "polyCount": 5,
           "rigged": False, "animated": False,
           "materials": [{"area": 3.0, "metallic": 1.0, "roughness": 0.2, "transmission": 0, "emission": 0, "subsurface": 0},
                         {"area": 1.0, "metallic": 0.0, "roughness": 0.05, "transmission": 1.0, "emission": 0, "subsurface": 0}]}
    p = build_profile(raw)
    assert p.unitGuess == "mm" and p.scaleConfidence == "low"
    assert [round(v, 3) for v in p.sizeM] == [4.5, 1.9, 1.3]
    assert [round(v, 3) for v in p.boundsMin] == [-2.25, -0.95, 0.0]
    assert p.sizeClass == "vehicle" and p.categoryHint == "vehicle-like"
    assert p.materials == [{"class": "metal", "share": 0.75}, {"class": "glass", "share": 0.25}]
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_measure.py -q` → `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`engine/ingest/__init__.py`: empty file.

`engine/ingest/measure.py`:
```python
"""Pure half of ingest: raw Blender facts -> SubjectProfile. Trusts no names (spec §4.1)."""
from engine.profile import SubjectProfile

PLAUSIBLE_M = (0.02, 30.0)
_LARGE_FACTORS = (("mm", 0.001), ("cm", 0.01))
_SIZE_CLASSES = ((0.1, "macro"), (0.5, "hand"), (2.5, "furniture"), (8.0, "vehicle"))


def infer_units(longest_raw):
    lo, hi = PLAUSIBLE_M
    if lo <= longest_raw <= hi:
        return "m", 1.0, "high"
    if longest_raw > hi:
        for name, f in _LARGE_FACTORS:
            if lo <= longest_raw * f <= hi:
                return name, f, "low"
    return "unknown", 1.0, "low"


def size_class(longest_m):
    for limit, name in _SIZE_CLASSES:
        if longest_m < limit:
            return name
    return "architectural"


def category_hint(size):
    x, y, z = size
    longest, width = max(x, y), min(x, y)
    if 2.5 <= longest <= 7.0 and z < 0.6 * longest and longest >= 2 * width:
        return "vehicle-like"
    return "small-object" if max(size) < 0.5 else "large-object"


def material_class(m):
    g = lambda k, d=0.0: m.get(k, d)
    if g("emission") > 0.5:
        return "emissive"
    if g("transmission") > 0.5:
        return "glass"
    if g("subsurface") > 0.2:
        return "skin"
    if g("metallic") > 0.5:
        return "metal"
    if g("roughness", 0.5) < 0.25:
        return "glossy"
    if g("roughness", 0.5) > 0.7:
        return "fabric"
    return "matte"


def _material_shares(mats):
    total = sum(m.get("area", 0.0) for m in mats)
    if total <= 0:
        return []
    shares = {}
    for m in mats:
        c = material_class(m)
        shares[c] = shares.get(c, 0.0) + m.get("area", 0.0) / total
    return [{"class": c, "share": round(v, 4)} for c, v in sorted(shares.items(), key=lambda kv: -kv[1])]


def build_profile(raw):
    lo, hi = raw["boundsMin"], raw["boundsMax"]
    size_raw = [b - a for a, b in zip(lo, hi)]
    unit, f, conf = infer_units(max(size_raw))
    size = [v * f for v in size_raw]
    bmin = [-size[0] / 2, -size[1] / 2, 0.0]
    bmax = [size[0] / 2, size[1] / 2, size[2]]
    return SubjectProfile(
        sizeM=size, boundsMin=bmin, boundsMax=bmax, unitGuess=unit, scaleConfidence=conf,
        upAxis="Z", sizeClass=size_class(max(size)), categoryHint=category_hint(size),
        materials=_material_shares(raw.get("materials", [])), polyCount=raw.get("polyCount", 0),
        rigged=raw.get("rigged", False), animated=raw.get("animated", False),
    )
```

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests/test_measure.py -q` → `4 passed`

- [ ] **Step 5: Commit**
```bash
git add engine/ingest/__init__.py engine/ingest/measure.py engine/tests/test_measure.py
git commit -m "feat(engine): ingest measurement (true scale, size class, material classes)"
```

### Task 10: Blender extractor + runner (integration)

**Files:**
- Create: `engine/ingest/blender_extract.py`, `engine/ingest/run.py`, `engine/tests/test_ingest_blender.py`

- [ ] **Step 1: Write the integration test** — `engine/tests/test_ingest_blender.py`

```python
import os
from pathlib import Path
import pytest
from engine.ingest.run import BLENDER, ingest

MODELS = Path(__file__).resolve().parents[2] / "assets-in" / "models"

pytestmark = pytest.mark.skipif(not os.path.exists(BLENDER), reason="Blender not installed")


@pytest.mark.parametrize("glb", ["pocket_watch/pocket_watch.glb", "toycar/toycar.glb"])
def test_ingest_real_models(glb, tmp_path):
    path = MODELS / glb
    if not path.exists():
        pytest.skip(f"{glb} not present")
    p = ingest(path, workdir=tmp_path)
    assert 0.02 <= p.longest <= 30
    assert p.boundsMin[2] == 0.0
    assert p.polyCount > 0
    assert p.materials, "expected at least one classified material"


def test_textured_materials_are_read_not_defaulted(tmp_path):
    # Both models drive material values through textures (glTF metallicRoughness /
    # emissive maps). Reading socket defaults instead of the textures classified the
    # watch's metal body as matte and the toy car's body as emissive (plan review 2026-09-24).
    watch = MODELS / "pocket_watch/pocket_watch.glb"
    car = MODELS / "toycar/toycar.glb"
    if not (watch.exists() and car.exists()):
        pytest.skip("models not present")
    w = ingest(watch, workdir=tmp_path / "w")
    assert w.materials[0]["class"] == "metal", w.materials
    c = ingest(car, workdir=tmp_path / "c")
    assert not any(m["class"] == "emissive" and m["share"] > 0.2 for m in c.materials), c.materials
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_ingest_blender.py -q` → `ModuleNotFoundError: engine.ingest.run`

- [ ] **Step 3: Implement**

`engine/ingest/blender_extract.py` (runs **inside** Blender; argv after `--` is `<model.glb> <raw_out.json>`):
```python
import json
import sys

import bpy
import numpy as np  # bundled with Blender; this file never runs outside Blender

glb, out = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)

deps = bpy.context.evaluated_depsgraph_get()
lo = [float("inf")] * 3
hi = [float("-inf")] * 3
polys = 0
areas = {}
for obj in bpy.context.scene.objects:
    if obj.type != "MESH":
        continue
    ev = obj.evaluated_get(deps)
    mesh = ev.to_mesh()
    mesh.transform(obj.matrix_world)
    for v in mesh.vertices:
        for i in range(3):
            lo[i] = min(lo[i], v.co[i])
            hi[i] = max(hi[i], v.co[i])
    polys += len(mesh.polygons)
    for p in mesh.polygons:
        slot = obj.material_slots[p.material_index] if p.material_index < len(obj.material_slots) else None
        mat = slot.material if slot else None
        key = mat.name if mat else None
        areas[key] = areas.get(key, 0.0) + p.area
    ev.to_mesh_clear()

if polys == 0:
    sys.exit(f"no mesh geometry found in {glb}")

_CHANNEL = {"Red": 0, "Green": 1, "Blue": 2, "R": 0, "G": 1, "B": 2}
_mean_cache = {}


def _image_mean(image, channel):
    """Mean of one channel (0-2) or of RGB luminance (channel=None), on a strided sample."""
    key = (image.name, channel)
    if key not in _mean_cache:
        px = np.empty(len(image.pixels), dtype=np.float32)
        image.pixels.foreach_get(px)
        px = px.reshape(-1, 4)[::97]  # ~1% sample is plenty for a mean
        v = px[:, :3].mean(axis=1) if channel is None else px[:, channel]
        _mean_cache[key] = float(v.mean()) if len(v) else 0.0
    return _mean_cache[key]


def _resolve(socket, channel=None, depth=0):
    """Scalar value reaching `socket`: its default, or the mean of the texture behind it.
    glTF imports wire metallicRoughness as Image -> Separate Color (G=roughness, B=metallic),
    sometimes through a Math MULTIPLY holding the factor. Returns None if it can't tell."""
    if depth > 6:
        return None
    if not socket.is_linked:
        v = socket.default_value
        if isinstance(v, (int, float)):
            return float(v)
        return float(sum(v[:3]) / 3)  # colour socket -> brightness
    link = socket.links[0]
    node, out = link.from_node, link.from_socket
    if node.type == "TEX_IMAGE" and node.image is not None and node.image.size[0] > 0:
        return _image_mean(node.image, channel)
    if node.type == "SEPARATE_COLOR":
        return _resolve(node.inputs[0], _CHANNEL.get(out.name), depth + 1)
    if node.type == "MATH" and node.operation == "MULTIPLY":
        vals = [_resolve(i, channel, depth + 1) for i in node.inputs[:2]]
        return None if None in vals else vals[0] * vals[1]
    return None


def _input(node, name, default):
    s = node.inputs.get(name)
    if s is None:
        return default
    v = _resolve(s)
    return default if v is None else v


def _props(mat):
    if mat is None or mat.node_tree is None:
        return {}
    node = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if node is None:
        return {}
    col = node.inputs.get("Emission Color")
    brightness = _resolve(col) if col is not None else 0.0
    emission = _input(node, "Emission Strength", 0.0) * (brightness or 0.0)
    return {
        "metallic": _input(node, "Metallic", 0.0),
        "roughness": _input(node, "Roughness", 0.5),
        "transmission": _input(node, "Transmission Weight", 0.0),
        "emission": emission,
        "subsurface": _input(node, "Subsurface Weight", 0.0),
    }


materials = []
for name, area in areas.items():
    m = bpy.data.materials.get(name) if name else None
    materials.append({"area": area, **_props(m)})

raw = {
    "boundsMin": lo, "boundsMax": hi, "polyCount": polys,
    "rigged": any(o.type == "ARMATURE" for o in bpy.context.scene.objects),
    "animated": any(o.animation_data and o.animation_data.action for o in bpy.context.scene.objects),
    "materials": materials,
}
with open(out, "w", encoding="utf-8") as f:
    json.dump(raw, f)
```

`engine/ingest/run.py`:
```python
"""Launch Blender headless to extract raw facts, then build the SubjectProfile."""
import json
import os
import subprocess
import tempfile
from pathlib import Path

from engine.ingest.measure import build_profile

BLENDER = os.environ.get("BLENDER_EXE", r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
EXTRACT = Path(__file__).with_name("blender_extract.py")
TIMEOUT_S = 300


def ingest(model_path, workdir=None):
    workdir = Path(workdir or tempfile.mkdtemp(prefix="valora-ingest-"))
    raw_path = workdir / "raw.json"
    cmd = [BLENDER, "--background", "--factory-startup", "--disable-autoexec",
           "--python-exit-code", "1", "--python", str(EXTRACT), "--", str(model_path), str(raw_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=TIMEOUT_S)
    if proc.returncode != 0 or not raw_path.exists():
        tail = (proc.stderr or proc.stdout)[-2000:]
        raise RuntimeError(f"Blender extract failed (exit {proc.returncode}):\n{tail}")
    return build_profile(json.loads(raw_path.read_text(encoding="utf-8")))
```

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests/test_ingest_blender.py -q` → `3 passed`.
  - If `test_textured_materials_are_read_not_defaulted` fails, open the model in Blender and
    look at which node sits between the texture and the BSDF socket. Extend `_resolve` for
    that node type. Do NOT weaken the assertion. Also look at a render or screenshot of
    the model to confirm the expected class (a watch body that is actually gold-plated
    plastic would change the expectation — ground it in the visual, not the name). It takes about 10–30 s per model.
  - Print each profile's `sizeM` and **sanity-check it against the real object**: a pocket watch is about 5 cm, and a toy car maybe 5–30 cm.
  - A wrong but plausible size is a units bug. Fix it, don't loosen the test.
  - Add the observed values to the test as a tolerance band only after confirming them.

- [ ] **Step 5: Commit**
```bash
git add engine/ingest/blender_extract.py engine/ingest/run.py engine/tests/test_ingest_blender.py
git commit -m "feat(engine): headless Blender ingest extractor and runner"
```

### Task 11: CLI

**Files:**
- Create: `engine/__main__.py`, `engine/tests/test_cli.py`

- [ ] **Step 1: Write the failing test** — `engine/tests/test_cli.py`

```python
import json
import subprocess
import sys
from pathlib import Path

FIX = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[2]


def test_check_command_outputs_json_and_exit_code(tmp_path):
    out = subprocess.run([sys.executable, "-m", "engine", "check", str(FIX / "script_valid.json"),
                          "--profile", str(FIX / "profile_car.json")],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    doc = json.loads(out.stdout)
    assert doc["ok"] is True and doc["script"]["schema"] == "valora.scene/1"

    bad = json.loads((FIX / "script_valid.json").read_text())
    bad["world"]["id"] = "moon"
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    out = subprocess.run([sys.executable, "-m", "engine", "check", str(p),
                          "--profile", str(FIX / "profile_car.json")],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 2
    assert json.loads(out.stdout)["ok"] is False
```

- [ ] **Step 2: Run, expect FAIL** — `py -m pytest engine/tests/test_cli.py -q` → non-zero exit / `No module named engine.__main__`

- [ ] **Step 3: Implement** — `engine/__main__.py`

```python
"""CLI: py -m engine check <script.json> --profile <profile.json>
        py -m engine ingest <model.glb> [--out profile.json]"""
import argparse
import json
import sys
from pathlib import Path

from engine.catalog import Catalog
from engine.checker import check
from engine.profile import SubjectProfile


def main(argv=None):
    ap = argparse.ArgumentParser(prog="engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("script")
    c.add_argument("--profile", required=True)
    i = sub.add_parser("ingest")
    i.add_argument("model")
    i.add_argument("--out")
    a = ap.parse_args(argv)

    if a.cmd == "check":
        script = json.loads(Path(a.script).read_text(encoding="utf-8"))
        prof = SubjectProfile.from_dict(json.loads(Path(a.profile).read_text(encoding="utf-8")))
        r = check(script, prof, Catalog.load())
        print(json.dumps({"ok": r.ok, "issues": [x.to_dict() for x in r.issues], "script": r.script}, indent=2))
        return 0 if r.ok else 2

    from engine.ingest.run import ingest  # only needs Blender for this command
    doc = json.dumps(ingest(a.model).to_dict(), indent=2)
    if a.out:
        Path(a.out).write_text(doc, encoding="utf-8")
    print(doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run, expect PASS** — `py -m pytest engine/tests/test_cli.py -q` → `1 passed`

- [ ] **Step 5: Full suite + real-model smoke**
  - Run `py -m pytest engine/tests -q`: all pass.
  - Run `py -m engine ingest assets-in/models/mid_century_lounge_chair/mid_century_lounge_chair.glb`.
    The size should read as a chair, roughly 0.7–1.3 m per side. The plan review measured
    1.01 × 1.19 × 1.17 m.

- [ ] **Step 6: Commit**
```bash
git add engine/__main__.py engine/tests/test_cli.py
git commit -m "feat(engine): check and ingest CLI"
```

---

## Done when

- `py -m pytest engine/tests -q` is fully green, and the Blender integration tests ran
  rather than being skipped.
- `py -m engine ingest` on all 6 models in `assets-in/models/` gives sizes a human agrees
  with. Record them in the phase-1 handoff.
- A human-written script for each model passes `py -m engine check`, or fails with an
  error that names the real problem.

**Next plans (not this one):** phase 2 compiler and preview tier; §9a research corpus
(already piloting); phase 3 director.
