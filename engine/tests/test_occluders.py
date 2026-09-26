"""Declared world occluders and the lower-frame sight-line guard (TG-47 follow-up, 2026-09-25).

Look 4ced996a (night_street, sports_car, seed 0, wet): TG-47's low hero camera stood behind the far pavement,
at ground level, and the 15 cm kerb/pavement slab filled the bottom ~40% of the 9:16 frame. The fixture is that
exact script."""
import json
from pathlib import Path

import pytest

from engine.checker import COARSE_US, check
from engine.camera_context import camera_sampler
from engine.occluders import LOS_TOL, blocked_share, declared, valid
from engine.tests.test_capabilities import _grown
from engine.tests.test_director_fallback_phase5 import _fb
from engine.tests.test_director_package import _p

BAD = Path(__file__).resolve().parent / "fixtures" / "tg47_street_slab_4ced996a.json"
OUTDOOR = ("night_street", "rain_courtyard", "golden_field")


def _worst(s, p, cat, i, boxes):
    sh = s["shots"][i]
    prm = {k: v["default"] for k, v in cat.get("camera", sh["camera"]["id"])["params"].items()}
    prm.update(sh["camera"]["params"])
    smp = camera_sampler(cat, sh, p, None)
    return max(blocked_share(smp(prm, p, u), p.boundsMin, p.boundsMax, boxes, s["format"]["aspect"])
               for u in COARSE_US)


@pytest.mark.parametrize("world", OUTDOOR)
def test_every_outdoor_world_declares_its_occluders(world):
    m = _grown().get("world", world)
    assert "occluders" in m and valid(m["occluders"])


@pytest.mark.parametrize("model", ["sports_car", "pocket_watch", "mid_century_lounge_chair"])
def test_street_occluders_cover_the_layouts_kerbs_and_pavements(model):
    from engine.worlds.street_layout import layout
    p = _p(model)
    boxes = declared(_grown().get("world", "night_street"), p)
    lay = layout(p, 0, 30.0)
    ax = 0 if lay["road"]["alongAxis"] == "y" else 1              # the across axis
    reach = lay["road"]["width"] / 2 + 0.15 + 3.0                 # kerb + a standard pavement (a small subject's
    for it in lay["kerbs"] + lay["pavements"]:                    # pavement runs on to its pushed-back facades)
        lo, hi = it["min"], it["max"]
        span = (max(lo[ax], -reach), min(hi[ax], reach))
        assert any(blo[ax] - 1e-6 <= span[0] and span[1] <= bhi[ax] + 1e-6 and blo[2] <= lo[2] and hi[2] <= bhi[2]
                   and blo[1 - ax] <= lo[1 - ax] and hi[1 - ax] <= bhi[1 - ax] for blo, bhi in boxes), (it, boxes)
    road_half = lay["road"]["width"] / 2
    assert min(min(abs(b[0][ax]), abs(b[1][ax])) for b in boxes) == pytest.approx(road_half - 0.075)


@pytest.mark.parametrize("model", ["sports_car", "pocket_watch"])
def test_courtyard_occluders_are_the_curbs(model):
    from engine.worlds.courtyard_layout import box, layout
    p = _p(model)
    boxes = declared(_grown().get("world", "rain_courtyard"), p)
    curbs = [box(it) for it in layout(p, 0)["props"] if it["kind"] == "curb"]
    assert curbs
    for lo, hi in curbs:
        assert any(all(blo[i] - 1e-6 <= lo[i] and hi[i] <= bhi[i] + 1e-6 for i in range(3)) for blo, bhi in boxes)


def test_the_field_declares_nothing_raised():
    assert declared(_grown().get("world", "golden_field"), _p("sports_car")) == []


def test_the_4ced996a_hero_camera_sees_the_slab_in_its_lower_frame():
    s = json.loads(BAD.read_text(encoding="utf-8"))
    cat, p = _grown(), _p("sports_car")
    boxes = declared(cat.get("world", "night_street"), p)
    assert _worst(s, p, cat, len(s["shots"]) - 1, boxes) > 0.25


def test_the_checker_rejects_the_4ced996a_script():
    s = json.loads(BAD.read_text(encoding="utf-8"))
    r = check(s, _p("sports_car"), _grown())
    assert not r.ok
    assert any(i.code == "camera_view_blocked" and i.severity == "error" for i in r.issues), r.issues


def test_a_camera_in_the_road_is_clear():
    from engine.geometry import Pose
    p = _p("sports_car")
    boxes = declared(_grown().get("world", "night_street"), p)
    pose = Pose(position=(1.5, 10.0, 0.5), target=tuple(p.center), lens_mm=40.0)   # down the road, road level
    assert blocked_share(pose, p.boundsMin, p.boundsMax, boxes, "9:16") == 0.0


@pytest.mark.parametrize("world", OUTDOOR)
@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_the_fallback_car_keeps_every_camera_on_the_subjects_side(world, seed):
    s, p, cat, _ = _fb("sports_car", seed=seed, world=world, weather="wet")
    r = check(s, p, cat)
    assert r.ok, [i for i in r.issues if i.severity == "error"]
    boxes = declared(cat.get("world", world), p)
    for i in range(len(r.script["shots"])):
        assert _worst(r.script, p, cat, i, boxes) <= LOS_TOL, (i, r.script["shots"][i]["camera"])


def test_the_street_hero_stands_in_the_road_at_road_level():
    s, p, cat, _ = _fb("sports_car", seed=0, world="night_street", weather="wet")
    from engine.worlds.street_layout import layout
    road = layout(p, 0, 30.0)["road"]
    ax = 0 if road["alongAxis"] == "y" else 1
    for i in (0, len(s["shots"]) - 1):
        sh = s["shots"][i]
        prm = {k: v["default"] for k, v in cat.get("camera", sh["camera"]["id"])["params"].items()}
        prm.update(sh["camera"]["params"])
        for u in COARSE_US:
            pos = cat.load_camera_path(sh["camera"]["id"])(prm, p, u).position
            assert abs(pos[ax] - p.center[ax]) < road["width"] / 2 - 0.075, (i, u, pos)
            assert pos[2] <= 0.75                                  # TG-47's low camera, from the road surface
