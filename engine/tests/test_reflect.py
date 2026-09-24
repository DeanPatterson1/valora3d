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
