"""Task 80: reveal_rise (crane rise, CATALOG-GAPS rank 12), pure."""
import math

import pytest

from engine.checker import check
from engine.director.axes import DICE, _opener_ok, axis_values
from engine.easing import ease
from engine.geometry import box_corners, frame_stats
from engine.tests.camera_helpers import CAT, bearing_rate, defaults, path_module, sample, script_with
from engine.tests.test_director_package import _p

RISE = sample("reveal_rise")


def _exact(prm, p, u):
    """The Task 80 formula, written out: hold, then ease-out-quad rise and pull-back."""
    cx, cy, cz = p.center
    h = p.sizeM[2]
    m = min(max((u - prm["holdFrac"]) / (1.0 - prm["holdFrac"]), 0.0), 1.0)
    m = min(m / (1.0 - prm["settleFrac"]), 1.0) if prm["settleFrac"] else m
    k = ease(prm["easing"], m)
    d = p.radius * (prm["startDistance"] + (prm["distance"] - prm["startDistance"]) * k)
    z = max(0.03, h * (prm["startHeightFrac"] + (prm["endHeightFrac"] - prm["startHeightFrac"]) * k))
    az = math.radians(prm["azimuthDeg"])
    tz = h * prm["startHeightFrac"] + (cz - h * prm["startHeightFrac"]) * k
    return (cx + d * math.cos(az), cy + d * math.sin(az), z), (cx, cy, tz)


@pytest.mark.parametrize("model", ["sports_car", "pocket_watch"])
@pytest.mark.parametrize("u", [0.0, 0.5, 1.0])
def test_path_matches_its_formula(model, u):
    p, prm = _p(model), defaults("reveal_rise")
    pose = RISE(prm, p, u)
    pos, tgt = _exact(prm, p, u)
    assert pose.position == pytest.approx(pos, abs=1e-12) and pose.target == pytest.approx(tgt, abs=1e-12)
    assert pose.lens_mm == prm["lensMm"]


def test_defaults_are_the_plan_table():
    prm = defaults("reveal_rise")
    assert (prm["startHeightFrac"], prm["holdFrac"], prm["endHeightFrac"]) == (0.15, 0.2, 0.9)
    assert prm["easing"] == "out_quad"


def test_the_hold_is_honoured_and_z_rises_monotonically_after_it():
    p, prm = _p("sports_car"), defaults("reveal_rise")
    held = [RISE(prm, p, u / 100) for u in range(0, int(prm["holdFrac"] * 100) + 1)]
    assert all(q.position == held[0].position and q.target == held[0].target for q in held)
    zs = [RISE(prm, p, u / 200).position[2] for u in range(int(prm["holdFrac"] * 200), 201)]
    assert all(b >= a - 1e-12 for a, b in zip(zs, zs[1:])) and zs[-1] > zs[0]


def test_it_starts_on_a_detail_and_ends_on_the_whole_subject():
    for model in ("sports_car", "pocket_watch", "sneaker"):
        p, prm = _p(model), defaults("reveal_rise")
        corners = box_corners(p.boundsMin, p.boundsMax)
        end = frame_stats(RISE(prm, p, 1.0), corners, "9:16")
        start = frame_stats(RISE(prm, p, 0.0), corners, "9:16")
        assert end["inFrame"] and end["allInFront"], model
        assert not start["inFrame"] or start["coverage"] > end["coverage"], model   # tight: overflows or bigger


def test_ease_out_quad_and_the_settle_stillness():
    assert ease("out_quad", 0.0) == 0.0 and ease("out_quad", 1.0) == 1.0 and ease("out_quad", 0.5) == 0.75
    p = _p("sports_car")
    prm = {**defaults("reveal_rise"), "settleFrac": 0.2}
    eps = 1e-4
    for u in (0.0, 1.0):
        a = RISE(prm, p, max(0.0, u - eps)).position
        b = RISE(prm, p, min(1.0, u + eps)).position
        assert math.dist(a, b) < 1e-9, u                    # velocity 0 at both ends (hold, then settle)


def test_the_checker_frames_it_from_the_end_of_the_rise():
    """framed_from: the tight start is by design; the checker judges full framing once the rise lands."""
    assert path_module("reveal_rise").framed_from(defaults("reveal_rise")) == 1.0
    assert path_module("reveal_rise").framed_from({**defaults("reveal_rise"), "settleFrac": 0.25}) == 0.75
    for model in ("sports_car", "pocket_watch"):
        r = check(script_with("reveal_rise", {}), _p(model), CAT)
        assert r.ok, (model, [(i.code, i.message) for i in r.issues if i.severity == "error"])
        assert r.script["shots"][2]["camera"]["id"] == "reveal_rise"


def test_bearing_rate_under_the_cap():
    for model in ("sports_car", "pocket_watch"):
        assert bearing_rate("reveal_rise", _p(model)) <= 80.0


def test_never_an_opener():
    m = CAT.get("camera", "reveal_rise")
    assert m["hookable"] is False and not _opener_ok(m)
    assert _opener_ok(CAT.get("camera", "low_hero_push"))                    # a full hook still opens
    grown = _selectable_copy()
    assert "reveal_rise" in grown.selectable_ids("camera")
    fmt = {"aspect": "9:16", "durationS": 10, "fps": 30}
    dice = {**DICE, "openers": list(DICE["openers"]) + ["reveal_rise"]}
    assert "reveal_rise" not in axis_values(_p("sports_car"), grown, fmt, dice=dice)["opener"]


def _selectable_copy():
    import copy
    g = copy.copy(CAT)
    g._blocks = copy.deepcopy(CAT._blocks)
    g._blocks[("camera", "reveal_rise")]["directorSelectable"] = True
    return g
