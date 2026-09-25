import copy
import json

from engine.catalog import Catalog
from engine.director.distance import direction_distance, near_duplicate, script_distance
from engine.director.rulebook import EXAMPLES_DIR, example_script

A = {"world": "studio_cyc", "mood": "teal_night", "tone": "black", "pace": "calm", "opener": "arc_orbit",
     "weather": "dry", "wind": "calm"}


def _ex(name):
    return example_script(json.loads((EXAMPLES_DIR / f"{name}.json").read_text(encoding="utf-8")))


def test_direction_distance_is_a_weighted_hamming_in_0_1():
    assert direction_distance(A, A) == 0.0
    b = {**A, "mood": "clean"}
    assert direction_distance(A, b) == direction_distance(b, A) == 3 / 13
    far = {k: v + "_x" for k, v in A.items()}
    assert direction_distance(A, far) == 1.0


def test_script_distance_zero_for_identical_and_symmetric():
    cat, s = Catalog.load(), _ex("watch_luxury")
    assert script_distance(s, copy.deepcopy(s), cat) == 0.0
    t = _ex("chair_warm")
    d = script_distance(s, t, cat)
    assert 0.0 < d <= 1.0 and abs(d - script_distance(t, s, cat)) < 1e-12


def test_small_param_change_is_small_and_near_duplicate():
    cat, s = Catalog.load(), _ex("watch_luxury")
    t = copy.deepcopy(s)
    t["shots"][0]["camera"]["params"]["lensMm"] = t["shots"][0]["camera"]["params"].get("lensMm", 50) + 2
    d = script_distance(s, t, cat)
    assert 0.0 < d < 0.08 and near_duplicate(s, t, cat)


def test_different_grade_preset_is_not_a_near_duplicate():
    cat, s = Catalog.load(), _ex("watch_luxury")
    t = copy.deepcopy(s)
    t["grade"] = {"id": "mood_grade", "params": {"preset": "vivid"}}
    assert not near_duplicate(s, t, cat)


def _set_cam_params(script, cat, end, only=None):
    """Every shot's camera: each numeric param (or just `only`) at the min (end=0) / max (end=1) of its range,
    each enum at its first (end=0) / last (end=1) value."""
    for sh in script["shots"]:
        spec = cat.get("camera", sh["camera"]["id"])["params"]
        ps = sh["camera"].setdefault("params", {})
        for name, p in spec.items():
            if only and name not in only:
                continue
            if p["type"] == "number":
                ps[name] = p["max"] if end else p["min"]
            elif p["type"] == "enum":
                ps[name] = p["values"][-1] if end else p["values"][0]
            elif p["type"] == "bool":
                ps[name] = bool(end)
    return script


def test_effect_param_extremes_add_visible_distance():
    cat, s = Catalog.load(), _ex("watch_luxury")
    lo, hi = copy.deepcopy(s), copy.deepcopy(s)
    lo["effects"] = [{"id": "haze_volume", "params": {"density": 0.0}}]
    hi["effects"] = [{"id": "haze_volume", "params": {"density": 1.0}}]
    assert script_distance(lo, copy.deepcopy(lo), cat) == 0.0
    d = script_distance(lo, hi, cat)
    assert d > 0.015 and abs(d - script_distance(hi, lo, cat)) < 1e-12
    mid = copy.deepcopy(lo)
    mid["effects"][0]["params"]["density"] = 0.5
    assert 0.0 < script_distance(lo, mid, cat) < d                      # proportional to the change


def test_camera_params_at_opposite_range_ends_are_not_near_duplicates():
    cat, s = Catalog.load(), _ex("watch_luxury")
    lo, hi = _set_cam_params(copy.deepcopy(s), cat, 0), _set_cam_params(copy.deepcopy(s), cat, 1)
    assert not near_duplicate(lo, hi, cat)
    framing = ("azimuthDeg", "startAzimuthDeg", "azimuthOffsetDeg", "sweepDeg", "lensMm")
    lo = _set_cam_params(copy.deepcopy(s), cat, 0, only=framing)
    hi = _set_cam_params(copy.deepcopy(s), cat, 1, only=framing)
    assert not near_duplicate(lo, hi, cat)                             # azimuth / lens / sweep only


def test_tiny_camera_nudges_on_every_shot_stay_near_duplicates():
    cat, s = Catalog.load(), _ex("watch_luxury")
    t = copy.deepcopy(s)
    for sh in t["shots"]:
        ps, spec = sh["camera"].setdefault("params", {}), cat.get("camera", sh["camera"]["id"])["params"]
        ps["lensMm"] = ps.get("lensMm", spec["lensMm"]["default"]) + 3
        for az in ("azimuthDeg", "startAzimuthDeg", "azimuthOffsetDeg"):
            if az in spec:
                ps[az] = ps.get(az, spec[az]["default"]) + 5
    d = script_distance(s, t, cat)
    assert 0.0 < d < 0.08 and near_duplicate(s, t, cat)
