"""Phase 5 Task 55: shape facts from existing surface samples (no re-ingest)."""
import dataclasses
import math
import random

from engine.catalog import Catalog, _has
from engine.checker import check
from engine.physics import shape
from engine.physics.applies import facts
from engine.tests.test_director_package import _p


def _cylinder(r=0.05, h=0.2, axis="x", n=800, seed=1):
    rng, out = random.Random(seed), []
    for _ in range(n):
        a, t = rng.uniform(0, 2 * math.pi), rng.uniform(-h / 2, h / 2)
        c, s = math.cos(a), math.sin(a)
        p = {"x": (t, r * c, r + r * s), "y": (r * c, t, r + r * s)}[axis]
        nrm = {"x": (0, c, s), "y": (c, 0, s)}[axis]
        out.append({"p": list(p), "n": list(nrm)})
    return out


def _box(sx=0.3, sy=0.2, sz=0.1, n=900, seed=2):
    rng, out = random.Random(seed), []
    for _ in range(n):
        f = rng.randrange(6)
        u, v = rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5)
        p = [[sx/2, u*sy, (v+0.5)*sz], [-sx/2, u*sy, (v+0.5)*sz], [u*sx, sy/2, (v+0.5)*sz],
             [u*sx, -sy/2, (v+0.5)*sz], [u*sx, v*sy, sz], [u*sx, v*sy, 0.0]][f]
        nrm = [[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]][f]
        out.append({"p": p, "n": nrm})
    return out


def test_principal_axes_orders_long_to_short():
    ax = shape.principal_axes(_box())
    assert abs(abs(ax[0][0]) - 1) < 0.05 and abs(abs(ax[2][2]) - 1) < 0.05


def test_roll_axis_found_on_a_lying_cylinder_not_on_a_box():
    r = shape.roll_axis(_cylinder(axis="x"))
    assert r["confidence"] == "high" and abs(abs(r["axis"][0]) - 1) < 0.05 and abs(r["radius"] - 0.05) < 0.004
    assert shape.roll_axis(_box())["confidence"] == "low"


def test_support_polygon_is_the_footprint_hull():
    poly = shape.support_polygon(_box())
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    assert abs(max(xs) - 0.15) < 0.02 and abs(min(ys) + 0.1) < 0.02 and len(poly) >= 4


def test_up_facing_and_low_edges():
    up = shape.up_facing(_box())
    assert up and all(s["n"][2] > 0.7 for s in up)
    low = shape.low_edges(_cylinder(axis="x"))
    assert low and all(s["n"][2] < -0.3 for s in low)


def test_empty_samples_degrade_to_low_confidence():
    assert shape.roll_axis([])["confidence"] == "low" and shape.support_polygon([]) == []


def _mean_abs_dot(truth):
    est = shape.estimate_normals([s["p"] for s in truth])
    return sum(abs(sum(a * b for a, b in zip(e, t["n"]))) for e, t in zip(est, truth)) / len(truth)


def test_estimated_normals_match_the_true_ones_on_bare_points():
    assert _mean_abs_dot(_box()) >= 0.95
    assert _mean_abs_dot(_cylinder(axis="y")) >= 0.95


def test_estimated_normals_point_away_from_the_centroid():
    est = shape.estimate_normals([s["p"] for s in _box()])
    top = [n for s, n in zip(_box(), est) if s["n"][2] == 1]
    assert top and sum(n[2] for n in top) / len(top) > 0.9


def _with_samples(name, pts):
    return dataclasses.replace(_p(name), surfaceSamples=[list(p) for p in pts])


def test_samples_reads_bare_profile_points_and_is_cached_by_content():
    p = _with_samples("pocket_watch", [s["p"] for s in _cylinder(axis="x")])
    a = shape.samples(p)
    assert len(a) == 800 and set(a[0]) == {"p", "n"}
    assert shape.samples(dataclasses.replace(p)) is a        # same content -> same cached list
    q = _with_samples("pocket_watch", [s["p"] for s in _box()])
    assert shape.samples(q) is not a


def test_nose_sign_parses_vector_axis():
    p = _p("sports_car")
    assert shape.nose_sign(p) == (1, "low")
    q = dataclasses.replace(p, vehicle={**p.vehicle, "forwardAxis": [-0.98, 0.1, 0.0]})
    assert shape.nose_sign(q) == (-1, "low")


def test_nose_sign_low_without_glass():
    assert shape.nose_sign(_p("pocket_watch")) == (1, "low")
    assert shape.nose_sign(_p("sports_car"))[1] == "low"   # no per-part material class at HEAD


def test_facts_and_has_expose_shape_facts():
    rolling = _with_samples("pocket_watch", [s["p"] for s in _cylinder(axis="x")])
    boxy = _with_samples("pocket_watch", [s["p"] for s in _box()])
    fr, fb = facts(rolling), facts(boxy)
    assert fr["rollAxis"] == (True, False) and fb["rollAxis"] == (False, False)
    assert fb["supportPolygon"] == (True, False) and fb["upFacing"] == (True, False)
    assert _has(rolling, "rollAxis") and not _has(boxy, "rollAxis")
    assert _has(boxy, "supportPolygon") and _has(boxy, "upFacing")


def test_checker_compat_reads_computed_facts_through_has():
    cat = Catalog.load()

    class _Cat:
        def __getattr__(self, name):
            return getattr(cat, name)

        def get(self, kind, bid):
            m = cat.get(kind, bid)
            if kind == "motion" and m is not None:
                m["requiresProfile"] = ["rollAxis"]
            return m

    from engine.tests.test_physics_applies import _script
    rolling = _with_samples("pocket_watch", [s["p"] for s in _cylinder(axis="x")])
    boxy = _with_samples("pocket_watch", [s["p"] for s in _box()])
    codes = lambda p: {i.code for i in check(_script(), p, _Cat()).issues}  # noqa: E731
    assert "motion_needs_profile" not in codes(rolling)
    assert "motion_needs_profile" in codes(boxy)
