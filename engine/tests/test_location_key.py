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
    # a lamp, not a wheel (round 8: a wheel close-up has its own face-mirror key, below)
    w = (car.center[0] + 0.55, car.boundsMin[1] + 0.25, car.boundsMin[2] + 0.75)
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


# ---- round 6 (2026-09-25) ------------------------------------------------------------------------------------------
def test_a_close_up_on_the_bonnet_keeps_the_flag(car):
    """The hood under the open overcast turned every bead into a dark speck: a close-up keeps the flag too."""
    lamp = (car.center[0] + 0.55, car.boundsMin[1] + 0.25, car.boundsMin[2] + 0.75)
    pos = (lamp[0] + 1.3, lamp[1] - 1.7, lamp[2] + 0.6)
    rigs = LK.shot_rigs(car, [{"shot": 0, "frame": 1, "detail": True, "position": pos, "target": lamp}])
    assert rigs[0]["flag"] is not None and rigs[0]["key"]["sizeX"] == pytest.approx(1.5 * LK.scale(car))


def test_flag_is_large_far_and_feathered():
    """The 2 x 3 m flag at 2.2 m left a hard cap across the glass: larger, further, feathered edges."""
    w, h = LK.FLAG["sizeM"]
    assert w >= 3.0 and h >= 4.0 and LK.FLAG["distM"] >= 3.0 and 0.3 <= LK.FLAG["feather"] <= 0.6


def test_a_near_front_hero_keys_camera_left_not_behind_the_car(car):
    """A flank seen almost edge-on mirrors the key behind the car, where nothing visible shows it."""
    pos = _cam(car, -78, dist=5.5, h=0.45)
    k = LK.hero_key(car, pos)
    assert not k["mirrors"]
    rel = tuple(a - b for a, b in zip(k["center"], car.center))
    assert sum(r * l for r, l in zip(rel, LK.camera_left(pos, car.center))) > 0
    assert LK.hero_key(car, _cam(car, -58))["mirrors"]            # a 3/4 hero still mirrors on the door


# ---- round 7 (2026-09-26): the night street's sheen ----------------------------------------------------------------
@pytest.mark.parametrize("az", [-78, -58, 30, 120])
def test_after_dark_a_full_frame_shot_gets_a_street_light_strip_on_the_camera_side(car, az):
    """A black car at night read as a silhouette (real_r6_street_night): the flank facing the camera now mirrors a
    long thin street-light strip, parallel to the car, out on that side and up where a shoulder mirrors it."""
    pos = _cam(car, az, h=0.4)
    g = LK.shoulder_sheen(car, pos)
    ia = LK._long_axis(car)
    ib = 1 - ia
    assert g is not None and g["axis"][ia] == 1.0 and g["sizeX"] > 2.0 * car.sizeM[ia]   # runs the car's length
    assert (g["center"][ib] - car.center[ib]) * (pos[ib] - car.center[ib]) > 0             # on the camera's side
    assert g["center"][2] > car.boundsMax[2] and g["sizeY"] < 0.5                          # high and thin
    assert abs(sum(a * b for a, b in zip(g["facing"], g["axis"]))) < 1e-9                  # faces the flank
    assert (g["facing"][ib] < 0) == (g["center"][ib] > car.center[ib])


def test_the_sheen_is_night_only_and_skips_head_on_and_detail_set_ups(car):
    head_on = list(car.center)
    head_on[LK._long_axis(car)] -= 6.0
    assert LK.shoulder_sheen(car, (head_on[0], head_on[1], 0.4)) is None
    w = tuple(car.wheels[0]["center"])
    ups = [{"shot": 0, "frame": 30, "detail": False, "position": _cam(car, -60, h=0.4), "target": None},
           {"shot": 1, "frame": 83, "detail": True, "position": (w[0] + 1.4, w[1], w[2]), "target": w}]
    assert [r["sheen"] for r in LK.shot_rigs(car, ups)] == [None, None]                     # day: no strip
    night = LK.shot_rigs(car, ups, sheen=True)
    assert night[0]["sheen"] is not None and night[1]["sheen"] is None


# ---- round 8 (2026-09-26): the wheel close-up ----------------------------------------------------------------------
def test_a_wheel_close_up_is_keyed_where_the_wheel_face_mirrors_the_camera(car):
    """The spokes, rotor, tyre and arch sat in one dark range: the key goes on the face's mirror direction."""
    w = car.wheels[0]
    c = w["center"]
    out = 1.0 if c[0] > car.center[0] else -1.0
    pos = (c[0] + out * 1.3, c[1] - 0.6, c[2] + 0.1)
    k = LK.detail_key(car, pos, tuple(c))
    s = LK.scale(car)
    assert k["sizeX"] == pytest.approx(2.0 * s) and _dist(k["center"], c) == pytest.approx(1.6 * s)
    v = LK._unit(LK._sub(c, pos))
    n = (out, 0.0, 0.0)
    r = LK._reflect(v, n)
    lifted = LK._unit(LK._add(r, (0.0, 0.0, LK.WHEEL_KEY["liftK"])))
    assert LK._dot(LK._unit(LK._sub(k["center"], c)), lifted) > 0.999      # round 9: the mirror direction, lifted
    assert 0.85 < LK._dot(lifted, r) < 0.97 and k["center"][2] > c[2]      # above the axle: not lit-for-clarity
    assert (k["center"][0] - c[0]) * out > 0                               # outboard, facing the wheel
    lamp = (car.center[0] + 0.55, car.boundsMin[1] + 0.25, car.boundsMin[2] + 0.75)
    assert LK.detail_key(car, pos, lamp)["sizeX"] == pytest.approx(1.5 * s)   # not a wheel: the detail key


def test_by_day_a_full_frame_shot_mirrors_a_nose_scrim_and_a_dim_wheel_source(car):
    """Round 9: the bumper mirrors one broad source (the open sky behind the photographer) and the near wheel a
    dim one, so the front end and wheels are not buried in black; a close detail gets neither."""
    lo, hi, c = car.boundsMin, car.boundsMax, car.center
    ia = LK._long_axis(car)
    ib = 1 - ia
    cam = [0.0, 0.0, 0.45]
    cam[ia] = hi[ia] + 2.2
    cam[ib] = c[ib] + 2.0
    n = LK.nose_scrim(car, tuple(cam))
    assert n is not None and n["watts"] == pytest.approx(LK.NOSE["wattsPerM2"] * n["sizeX"] * n["sizeY"])
    assert (n["center"][ia] - c[ia]) > 0 and n["center"][2] > lo[2]            # out in front of the nose, above ground
    rigs = LK.shot_rigs(car, [{"shot": 0, "frame": 1, "detail": False, "position": cam, "target": None},
                              {"shot": 1, "frame": 40, "detail": True, "position": cam, "target": tuple(c)}], front=True)
    assert rigs[0]["nose"] is not None and rigs[0]["glint"]["watts"] == pytest.approx(
        LK.DAY_WHEEL_W * LK.scale(car) ** 2)
    assert rigs[1]["nose"] is None and rigs[1]["glint"] is None
    high = list(cam)
    high[2] = 6.0
    assert LK.nose_scrim(car, tuple(high)) is None or LK.nose_scrim(car, tuple(high))["center"][2] > 0



def test_after_dark_the_lower_bumper_mirrors_a_road_sheen_strip(car):
    """Round 10: at night a full-frame shot's lower bumper mirrors a low strip lying just above the road in front of
    it (the wet road's sheen); never by day, never on a detail."""
    lo, hi, c = car.boundsMin, car.boundsMax, car.center
    ia = LK._long_axis(car)
    ib = 1 - ia
    cam = [0.0, 0.0, 0.4]
    cam[ia] = lo[ia] - 4.7
    cam[ib] = c[ib] + 1.5
    g = LK.lower_sheen(car, tuple(cam))
    s = LK.scale(car)
    assert g is not None and 0.0 < g["center"][2] < 0.1 * s                   # on the road ...
    assert g["center"][ia] < lo[ia] and lo[ia] - g["center"][ia] <= LK.LOWER["maxM"] * s + 1e-6   # ... ahead of the nose
    ups = [{"shot": 0, "frame": 1, "detail": False, "position": cam, "target": None},
           {"shot": 1, "frame": 40, "detail": True, "position": cam, "target": tuple(c)}]
    night = LK.shot_rigs(car, ups, sheen=True)
    assert night[0]["lower"] is not None and night[1]["lower"] is None
    assert all(r["lower"] is None for r in LK.shot_rigs(car, ups, front=True))
