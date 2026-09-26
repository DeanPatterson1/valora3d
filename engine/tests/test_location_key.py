"""Per-shot reflection shaping on location (critique mat-v2 #2): a camera-left soft key across the visible side
and a dark flag where the windshield mirrors the sky."""
import math

import pytest

from engine.lighting import location_key as LK
from engine.tests.test_director_package import _p


def _dist(a, b):
    return math.dist(a, b)


@pytest.fixture(scope="module")
def car():
    return _p("sports_car")


def _cam(car, az_deg, dist=5.5, h=0.8):
    c = car.center
    a = math.radians(az_deg)
    return (c[0] + dist * math.cos(a), c[1] + dist * math.sin(a), h)


@pytest.mark.parametrize("az", [-120, -58, 0, 60, 150])
def test_hero_key_is_high_out_and_aimed(car, az):
    pos = _cam(car, az)
    k = LK.hero_key(car, pos)
    s = LK.scale(car)
    assert k["center"][2] == pytest.approx(car.boundsMin[2] + 2.5 * s, abs=1e-6)
    assert (round(k["sizeX"] / s, 6), round(k["sizeY"] / s, 6)) == (4.0, 3.0)
    to_c = tuple(b - a for a, b in zip(k["center"], car.center))
    assert sum(f * t for f, t in zip(k["facing"], to_c)) > 0                   # it points at the body


def test_hero_key_sits_where_the_visible_side_panel_mirrors_it(car):
    pos = _cam(car, -58)
    pt, n = LK.side_panel(car, pos)
    k = LK.hero_key(car, pos)
    assert k["mirrors"]
    v = tuple(a - b for a, b in zip(pt, pos))
    r = LK._reflect(LK._unit(v), n)
    to_key = LK._unit((k["center"][0] - pt[0], k["center"][1] - pt[1], 0.0))
    rh = LK._unit((r[0], r[1], 0.0))
    assert sum(a * b for a, b in zip(to_key, rh)) == pytest.approx(1.0)
    assert math.dist(k["center"][:2], pt[:2]) == pytest.approx(3.5 * LK.scale(car))


def test_hero_key_falls_back_camera_left_without_a_side_panel(car):
    import dataclasses
    top = dataclasses.replace(car, reflectionTargets=[t for t in car.reflectionTargets if t["kind"] == "top"])
    pos = _cam(car, 30)
    k = LK.hero_key(top, pos)
    rel = tuple(a - b for a, b in zip(k["center"], top.center))
    assert not k["mirrors"] and sum(r * l for r, l in zip(rel, LK.camera_left(pos, top.center))) > 2.0


def test_key_watts_follow_the_bracket_and_scale_with_area(car):
    assert LK.BRACKET_W == (300.0, 600.0, 900.0) and LK.DETAIL_BRACKET_W == (40.0, 80.0, 120.0)
    pos = _cam(car, 30)
    s = LK.scale(car)
    assert LK.hero_key(car, pos, watts=900)["watts"] == pytest.approx(900 * s * s)


def test_detail_key_is_small_close_and_a_little_above_the_detail(car):
    w = car.wheels[0]["center"]
    pos = (w[0] + 1.4, w[1] - 0.3, w[2] + 0.1)
    k = LK.detail_key(car, pos, tuple(w))
    s = LK.scale(car)
    assert (round(k["sizeX"] / s, 6), round(k["sizeY"] / s, 6)) == (1.5, 1.0)
    assert 1.0 * s <= _dist(k["center"], w) <= 1.5 * s and k["center"][2] > w[2]
    rel = tuple(a - b for a, b in zip(k["center"], w))
    assert sum(r * l for r, l in zip(rel, LK.camera_left(pos, w))) > 0


def test_flag_sits_on_the_windshield_mirror_direction_toward_the_sky(car):
    pos = _cam(car, -90, h=1.0)            # in front of the windshield patch ('top-y' faces -y)
    f = LK.windshield_flag(car, pos)
    assert f is not None
    d = tuple(a - b for a, b in zip(f["center"], f["aim"]))
    assert d[2] > 0                                                         # above the glass: the sky side
    assert _dist(f["center"], f["aim"]) == pytest.approx(LK.FLAG["distM"] * LK.scale(car))
    assert f["reachM"] > _dist(f["center"], f["aim"])
    assert (LK.FLAG["albedo"], LK.FLAG["roughness"]) == (0.01, 1.0)


def test_no_flag_when_no_sloped_patch_faces_the_camera(car):
    import dataclasses
    flat = dataclasses.replace(car, reflectionTargets=[t for t in car.reflectionTargets if t["kind"] == "top"])
    assert LK.windshield_flag(flat, _cam(car, -90)) is None


def test_shot_rigs_give_detail_shots_the_detail_key_and_no_flag(car):
    w = tuple(car.wheels[0]["center"])
    rigs = LK.shot_rigs(car, [
        {"shot": 0, "frame": 30, "detail": False, "position": _cam(car, -90, h=1.0), "target": None},
        {"shot": 1, "frame": 83, "detail": True, "position": (w[0] + 1.4, w[1], w[2]), "target": w}])
    assert rigs[0]["key"]["sizeX"] > rigs[1]["key"]["sizeX"] and rigs[0]["flag"] is not None
    assert rigs[1]["flag"] is None and [r["frame"] for r in rigs] == [30, 83]
