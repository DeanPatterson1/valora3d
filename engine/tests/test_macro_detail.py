import copy
import math
import json
from pathlib import Path

from engine.catalog import Catalog
from engine.checker import DETAIL_CENTER, SAMPLES_PER_SHOT, check
from engine.geometry import project
from engine.profile import SubjectProfile
from engine.targets import resolve_target

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()
_CAR = json.loads((FIX / "profile_car.json").read_text())
LAMP = {"kind": "emissive", "point": [2.25, 0.6, 0.7], "normal": [1, 0, 0], "score": 3.0}
CAR = SubjectProfile.from_dict({**_CAR, "detailPoints": [LAMP]})
BASE = json.loads((FIX / "script_valid.json").read_text())


def _macro(**shot):
    s = copy.deepcopy(BASE)
    s["shots"][1] = {"startS": 5, "endS": 10, "focus": "subject",
                     "camera": {"id": "macro_detail", "params": {}}, **shot}
    return s


def _codes(r, sev):
    return {i.code for i in r.issues if i.severity == sev}


def test_macro_on_a_detail_point_passes_and_keeps_it_centred():
    r = check(_macro(target={"detail": 0}), CAR, CAT)
    assert r.ok, [i.to_dict() for i in r.issues if i.severity == "error"]
    shot = r.script["shots"][1]
    sample = CAT.load_camera_path("macro_detail")
    tgt = resolve_target(shot, CAR, [])
    for k in range(SAMPLES_PER_SHOT):
        x, y, depth = project(sample(shot["camera"]["params"], CAR, k / (SAMPLES_PER_SHOT - 1), tgt),
                              tgt.point, "9:16")
        assert depth > 0 and max(abs(x), abs(y)) <= DETAIL_CENTER


def test_missing_target_defaults_to_the_best_detail_point():
    r = check(_macro(), CAR, CAT)
    assert r.ok and "detail_target_defaulted" in _codes(r, "repaired")
    assert r.script["shots"][1]["target"] == {"detail": 0}


def test_unknown_targets_are_errors():
    assert "unknown_target" in _codes(check(_macro(target={"detail": 3}), CAR, CAT), "error")
    assert "unknown_target" in _codes(check(_macro(target={"marker": "nope"}), CAR, CAT), "error")


def test_marker_target_works():
    s = _macro(target={"marker": "lamp"})
    s["markers"] = [{"id": "lamp", "anchor": {"space": "placed", "point": LAMP["point"], "normal": [1, 0, 0]},
                     "text": "macro on the headlight"}]
    assert check(s, CAR, CAT).ok


def test_too_close_macro_is_pushed_out_of_the_subject_margin():
    s = _macro(target={"detail": 0})
    s["shots"][1]["camera"]["params"] = {"distance": 0.1}
    r = check(s, CAR, CAT)
    assert r.ok and "camera_distance_adjusted" in _codes(r, "repaired")


def test_long_lens_wide_slide_is_repaired_by_narrowing_the_slide():
    # lens 150 + slideFrac 0.6 on 9:16 puts the target at |ndc| ~0.62 at the slide ends; no
    # distance can fix that (the offset scales with distance), so the slide must shrink.
    s = _macro(target={"detail": 0})
    s["shots"][1]["camera"]["params"] = {"lensMm": 150, "slideFrac": 0.6}
    r = check(s, CAR, CAT)
    assert r.ok, [i.to_dict() for i in r.issues if i.severity == "error"]
    assert "detail_slide_narrowed" in _codes(r, "repaired")
    assert "framing_unfixable" not in _codes(r, "error")
    prm = r.script["shots"][1]["camera"]["params"]
    assert 0.0 <= prm["slideFrac"] < 0.6
    tgt = resolve_target(r.script["shots"][1], CAR, [])
    sample = CAT.load_camera_path("macro_detail")
    for k in range(SAMPLES_PER_SHOT):
        x, y, _ = project(sample(prm, CAR, k / (SAMPLES_PER_SHOT - 1), tgt), tgt.point, "9:16")
        assert max(abs(x), abs(y)) <= DETAIL_CENTER


def test_macro_without_detail_points_warns_it_aims_at_a_surface_point():
    bare = SubjectProfile.from_dict({**_CAR, "detailPoints": []})
    r = check(_macro(), bare, CAT)
    assert "detail_target_surface" in _codes(r, "warning")


def _solid_box(lo=(-1.0, -0.5, 0.0), hi=(1.0, 0.5, 0.8), n=12):
    """A solid box profile with no detail points: surfaceSamples on its six faces, as ingest records them."""
    pts = set()
    for ax in range(3):
        for side in (lo[ax], hi[ax]):
            a, b = [k for k in range(3) if k != ax]
            for i in range(n + 1):
                for j in range(n + 1):
                    p = [0.0, 0.0, 0.0]
                    p[ax] = side
                    p[a] = lo[a] + (hi[a] - lo[a]) * i / n
                    p[b] = lo[b] + (hi[b] - lo[b]) * j / n
                    pts.add(tuple(round(v, 6) for v in p))
    size = [h - l for l, h in zip(lo, hi)]
    return SubjectProfile.from_dict({**_CAR, "sizeM": size, "boundsMin": list(lo), "boundsMax": list(hi),
                                     "detailPoints": [], "surfaceSamples": [list(p) for p in sorted(pts)],
                                     "wheels": [], "vehicle": {}})


def _box_distance(p, lo, hi):
    """Distance from p to the box surface (inside or out)."""
    inside = all(l <= v <= h for v, l, h in zip(p, lo, hi))
    if inside:
        return min(min(v - l, h - v) for v, l, h in zip(p, lo, hi))
    return math.dist(p, [min(max(v, l), h) for v, l, h in zip(p, lo, hi)])


def test_no_detail_points_aims_at_the_surface_facing_the_camera_not_inside():
    """Gap after 32a7801: the centre fallback aimed macro shots inside a solid mesh (camera clearance fails).
    With no detail point the target is the first surface hit along the macro camera's direction."""
    box = _solid_box()
    tgt = resolve_target({"camera": {"id": "macro_detail"}}, box, [])
    assert tgt.source == "surface"
    size = box.longest
    assert _box_distance(tgt.point, box.boundsMin, box.boundsMax) < 0.01 * size, tgt.point
    assert not all(l + 1e-9 < v < h - 1e-9 for v, l, h in zip(tgt.point, box.boundsMin, box.boundsMax))
    assert tgt.point[1] < box.boundsMin[1] + 0.01 * size   # the -Y face the default normal looks at
    assert resolve_target({"camera": {"id": "macro_detail"}}, box, []) == tgt   # deterministic
    r = check(_macro(), box, CAT)
    assert r.ok, [i.to_dict() for i in r.issues if i.severity == "error"]
    sample = CAT.load_camera_path("macro_detail")
    prm = r.script["shots"][1]["camera"]["params"]
    for k in range(SAMPLES_PER_SHOT):   # every camera key stays outside the solid
        pos = sample(prm, box, k / (SAMPLES_PER_SHOT - 1), tgt).position
        assert not all(l <= v <= h for v, l, h in zip(pos, box.boundsMin, box.boundsMax)), pos


def test_no_surface_samples_falls_back_to_the_bbox_face_not_the_centre():
    box = _solid_box()
    box.surfaceSamples = []
    tgt = resolve_target({"camera": {"id": "macro_detail"}}, box, [])
    assert tgt.source == "surface"
    assert _box_distance(tgt.point, box.boundsMin, box.boundsMax) < 0.01 * box.longest
