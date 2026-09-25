"""TEST ONLY synthetic subject profiles for the shape-driven motions (phase 5 Task 77): a can lying on its side
(it rolls) and an upright bottle (it topples). Surface samples come from the shape-test cylinder recipe
(engine/tests/test_physics_shape._cylinder: seeded points on the side, plus the end caps a real mesh has);
the materials are written down, not measured. The JSONs in fixtures/synthetic_profiles are these functions'
output (test_shape_profiles_are_generated keeps them in step): `py -m engine.tests.shape_profiles` rewrites them."""
import json
import math
import random
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "fixtures" / "synthetic_profiles"
TEMPLATE = HERE / "fixtures" / "profiles" / "sneaker.json"


def _cylinder_points(r, length, axis, n_side=900, n_cap=180, seed=1):
    """Seeded points on a closed cylinder: side + two caps. axis 'x' lies on its side (centre at height r),
    'z' stands up from z = 0."""
    rng, out = random.Random(seed), []
    for _ in range(n_side):
        a, t = rng.uniform(0, 2 * math.pi), rng.uniform(-length / 2, length / 2)
        c, s = math.cos(a), math.sin(a)
        out.append((t, r * c, r + r * s) if axis == "x" else (r * c, r * s, t + length / 2))
    for end in (-1, 1):
        for _ in range(n_cap):
            a, q = rng.uniform(0, 2 * math.pi), r * math.sqrt(rng.random())
            c, s = q * math.cos(a), q * math.sin(a)
            out.append((end * length / 2, c, r + s) if axis == "x" else (c, s, (end + 1) / 2 * length))
    return [[round(v, 6) for v in p] for p in out]


def _profile(pts, materials, category):
    base = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    lo[2] = 0.0
    size = [hi[i] - lo[i] for i in range(3)]
    top = max(pts, key=lambda p: p[2])
    side = max(pts, key=lambda p: p[0])
    base.update({
        "sizeM": size, "boundsMin": lo, "boundsMax": hi, "sourceCenter": [0.0, 0.0, size[2] / 2],
        "sourceMinZ": 0.0, "scaleFactor": 1.0, "categoryHint": category, "materials": materials,
        "surfaceSamples": pts, "reflectionTargets": [], "shoulderLine": [], "wheels": [], "vehicle": {},
        "softParts": [], "danglingParts": [], "animationClips": [], "rigged": False, "animated": False,
        "parts": [{"index": 0, "boundsMin": lo, "boundsMax": hi, "polyShare": 1.0}],
        "detailPoints": [{"kind": "high_curvature", "point": top, "normal": [0.0, 0.0, 1.0], "score": 1.0},
                         {"kind": "high_curvature", "point": side, "normal": [1.0, 0.0, 0.0], "score": 0.9}],
        "groundContacts": [{"center": [0.0, 0.0, 0.0], "radius": round(min(size[0], size[1]) / 2, 6), "share": 1.0}],
    })
    return base


def can_profile():
    """A 12 cm drinks can lying on its side along x (r 3.3 cm): round side, axis flat, resting on it."""
    return _profile(_cylinder_points(0.033, 0.12, "x"), [{"class": "metal", "share": 1.0}], "small-object")


def bottle_profile():
    """A 26 cm bottle standing up (r 3.5 cm): a flat round base and an aspect of 3.7, so it can topple."""
    return _profile(_cylinder_points(0.035, 0.26, "z", seed=3),
                    [{"class": "glass", "share": 0.85}, {"class": "glossy", "share": 0.15}], "small-object")


SHAPES = {"can": can_profile, "bottle": bottle_profile}


if __name__ == "__main__":
    for name, fn in SHAPES.items():
        (OUT / f"{name}.json").write_text(json.dumps(fn(), indent=1), encoding="utf-8")
        print("wrote", OUT / f"{name}.json")
