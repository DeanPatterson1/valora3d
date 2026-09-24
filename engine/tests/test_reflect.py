import json
import math
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.color import kelvin_to_rgb, kelvin_to_srgb, srgb_to_linear
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


def _accents(points, **params):
    rich = SubjectProfile.from_dict({**CAR.to_dict(), "detailPoints": points})
    return [l for l in rig_layout(rich, (8, -8, 1), {**P, **params}).lights if l.role == "accent"]


GLINT = {"kind": "glossy_peak", "point": [2.25, 0.5, 0.9], "normal": [1, 0, 0], "score": 2.1}
BACK = {"kind": "high_curvature", "point": [-2.25, 0.0, 0.8], "normal": [-1, 0, 0], "score": 1.1}
SIDE = {"kind": "glossy_peak", "point": [0.0, -0.95, 0.8], "normal": [0, -1, 0], "score": 1.0}


def test_accents_use_detail_points_and_respect_the_count():
    # BACK faces away from the (8, -8, 1) camera: no accent is spent on it.
    assert len(_accents([GLINT, BACK], accentCount=4)) == 1
    assert len(_accents([GLINT, BACK, SIDE], accentCount=4)) == 2
    assert len(_accents([GLINT, BACK, SIDE], accentCount=1)) == 1


def test_accents_skip_points_facing_away_before_the_count():
    got = _accents([BACK, GLINT], accentCount=1)
    assert len(got) == 1 and got[0].center[0] > 2.25  # placed off GLINT, not the hidden BACK


def test_accent_size_is_a_fraction_of_the_overhead_key():
    rich = SubjectProfile.from_dict({**CAR.to_dict(), "detailPoints": [GLINT]})
    rig = rig_layout(rich, (8, -8, 1), {**P, "accentScale": 0.5})
    over = next(l for l in rig.lights if l.role == "overhead")
    acc = next(l for l in rig.lights if l.role == "accent")
    assert acc.sizeX == pytest.approx(0.5 * min(over.sizeX, over.sizeY)) and acc.sizeY == acc.sizeX
    spec = CAT.get("lighting", "reflection_rig")["params"]["accentScale"]
    assert (spec["min"], spec["max"]) == (0.2, 0.7)  # V-L05: accents are 0.2-0.7 of the key


def test_zero_length_normals_are_skipped_with_a_note():
    bad = {**GLINT, "normal": [0, 0, 0]}
    rich = SubjectProfile.from_dict({**CAR.to_dict(), "detailPoints": [bad, SIDE],
                                     "reflectionTargets": [{"kind": "-y", "point": [0, -0.95, 0.78],
                                                            "normal": [0, 0, 0], "area": 1.0}]})
    rig = rig_layout(rich, (8, -8, 1), P)
    assert len([l for l in rig.lights if l.role == "accent"]) == 1
    assert any("zero-length normal" in n for n in rig.notes)


def test_each_missing_flank_is_filled_from_bounds():
    # Only +x measured: the -y flank the camera also sees still gets a strip.
    rich = SubjectProfile.from_dict({**CAR.to_dict(), "reflectionTargets": [
        {"kind": "+x", "point": [2.25, 0.0, 0.78], "normal": [1, 0, 0], "area": 1.0}]})
    strips = {l.name for l in rig_layout(rich, (8, -8, 1), P).lights if l.role == "strip"}
    assert strips == {"valora_strip_+x", "valora_strip_-y"}


def test_rig_objects_are_hidden_from_camera_rays():
    rig = rig_layout(CAR, (8, -8, 1), P)
    assert all(l.cameraVisible is False for l in rig.lights)


def test_ambient_is_one_over_key_fill():
    assert rig_layout(CAR, (8, -8, 1), {**P, "keyFill": 4.0}).ambient == pytest.approx(0.25)


def test_kelvin_to_rgb_is_warm_to_cool():
    w, d, c = kelvin_to_rgb(3000), kelvin_to_rgb(6500), kelvin_to_rgb(9000)
    assert w[0] == 1.0 and w[0] > w[1] > w[2]
    assert all(v > 0.9 for v in d)
    assert c[2] >= c[0]


def test_srgb_to_linear_matches_the_standard_curve():
    assert srgb_to_linear(0.0) == 0.0 and srgb_to_linear(1.0) == pytest.approx(1.0)
    assert srgb_to_linear(0.5) == pytest.approx(0.2140411, rel=1e-5)
    assert srgb_to_linear(0.04) == pytest.approx(0.04 / 12.92)


def test_kelvin_to_rgb_is_linear_for_blender_light_colour():
    s = kelvin_to_srgb(3000)
    assert kelvin_to_rgb(3000) == pytest.approx(tuple(srgb_to_linear(v) for v in s))
    assert kelvin_to_rgb(3000)[2] < s[2]
