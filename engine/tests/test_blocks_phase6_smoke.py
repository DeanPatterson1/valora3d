"""Phase 6 lane S (Tasks 112, 113): smoke_plume, steam, fire (effects) and smoke_sim, tyre_smoke (sims):
manifests, checker behaviour and the pure placement maths (engine/physics/plume.py, tyre_smoke.py)."""
import json
import math
import random
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.physics import plume as PL
from engine.physics import tyre_smoke as TS
from engine.physics import vdb as V
from engine.tests.test_director_package import _p

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def cat():
    return Catalog.load()


def _script(sims=(), effects=(), motion="static", markers=None):
    s = json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))
    s["sims"], s["effects"] = list(sims), list(effects)
    s["subject"]["motion"] = {"id": motion, "params": {}}
    if markers is not None:
        s["markers"] = markers
    return s


# ------------------------------------------------------------------------------------------ manifests

@pytest.mark.parametrize("bid,cap,tax", [("smoke_plume", "smoke.plume", "GS-01"), ("steam", "smoke.steam", "GS-02"),
                                         ("fire", "fire.flame", "GS-06")])
def test_effect_manifests(cat, bid, cap, tax):
    m = cat.get("effect", bid)
    assert m["directorSelectable"] is False and m["landsIn"] == "Task 119"
    assert m["capabilities"] == [cap] and tax in m["physics"]["taxonomy"] and m["physics"]["state"] == "stateless"
    assert m["maxPerClip"] == 1


def test_smoke_sim_manifest_is_a_heavy_gas_bake_in_budget(cat):
    m = cat.get("sim", "smoke_sim")
    b = m["bake"]
    assert b["method"] == "gas_vdb" and b["costClass"] == "heavy" and b["prerollS"] == 2.0
    assert b["maxFrames"] == 180 and b["cacheMBMax"] <= 4000 and b["proxies"] == ["shell"]
    assert m["params"]["res"]["max"] <= 160
    assert set(m["capabilities"]) == {"smoke.interactive", "smoke.coloured"}
    assert m["params"]["colour"]["default"] == "grey" and m["physics"]["timeScaleParam"] == "timeScale"


def test_tyre_smoke_is_library_playback_on_measured_wheels(cat):
    m = cat.get("sim", "tyre_smoke")
    assert m["bake"] == {"method": "none", "costClass": "cheap"} and m["requiresProfile"] == ["wheels"]
    assert m["capabilities"] == ["vehicle.tyre_smoke"]


def test_the_checker_accepts_each_block(cat):
    for sims, fx, prof in (([{"id": "smoke_sim", "params": {}, "startS": 0, "endS": 4}], [], "sports_car"),
                           ([{"id": "tyre_smoke", "params": {}, "startS": 0.5, "endS": 4}], [], "sports_car"),
                           ([], [{"id": "smoke_plume", "params": {}}], "sports_car"),
                           ([], [{"id": "fire", "params": {}}], "sports_car"),
                           ([], [{"id": "steam", "params": {}}], "camera_01")):
        r = check(_script(sims, fx), _p(prof), cat)
        assert r.ok, [(i.code, i.message) for i in r.issues if i.severity == "error"]


def test_tyre_smoke_needs_wheels(cat):
    r = check(_script([{"id": "tyre_smoke", "params": {}, "startS": 0, "endS": 3}]), _p("sneaker"), cat)
    assert not r.ok and any(i.code in ("sim_needs_profile", "subject_size") or "wheels" in i.message
                            for i in r.issues if i.severity == "error")


def test_two_heavy_sims_are_refused(cat):
    sims = [{"id": "smoke_sim", "params": {}, "startS": 0, "endS": 4},
            {"id": "smoke_sim", "params": {"colour": "white"}, "startS": 4, "endS": 8}]
    r = check(_script(sims), _p("sports_car"), cat)
    assert not r.ok and {i.code for i in r.issues} & {"sim_budget", "sim_duplicate"}


# ------------------------------------------------------------------------------------------ plume placement

@pytest.mark.parametrize("placement,count", [("behind", 1), ("around", 3), ("side", 2)])
def test_plumes_stand_clear_of_the_subject(placement, count):
    prof = _p("sports_car")
    cam = (prof.center[0], prof.center[1] - 12.0, 1.5)
    for a in PL.anchors(prof, cam, 2.0, placement, count, random.Random(3)):
        assert PL.clear_of_subject(prof, a, 2.0) and a[2] == 0.0


def test_behind_is_away_from_the_camera():
    prof = _p("sports_car")
    cam = (prof.center[0], prof.center[1] - 12.0, 1.5)
    (a,) = PL.anchors(prof, cam, 2.0, "behind", 1)
    assert a[1] > prof.boundsMax[1] and abs(a[0] - prof.center[0]) < 1e-6


def test_fit_play_opens_on_a_developed_plume_and_fits_the_clip():
    first, rt = PL.fit_play(150, 120, 1.0, random.Random(1))
    assert first >= int(PL.SETTLED_FRAC * 150) and first + 119 <= 150 or first == 31
    first, rt = PL.fit_play(150, 300, 1.0)                     # a 10 s clip at 30 fps: slow, never below MIN
    assert first == 1 and V.MIN_RETIME <= rt < 1.0 and 1 + (300 - 1) * rt <= 150 + 1e-9


def test_flicker_is_seeded_mean_one_and_5_to_12_hz():
    a = PL.flicker(240, 30, random.Random(4))
    assert a == PL.flicker(240, 30, random.Random(4)) and min(a) >= 0.2
    assert abs(sum(a) / len(a) - 1.0) < 0.1
    crossings = sum(1 for x, y in zip(a, a[1:]) if (x - 1) * (y - 1) < 0)
    assert 2 * 3 <= crossings / 8.0 <= 2 * 15                  # zero crossings per second ~ 2 x frequency


def test_wind_drift_follows_the_wind():
    assert PL.wind_drift(None, 0.8, 4) == (0.0, 0.0)
    dx, dy = PL.wind_drift({"speedMs": 2.0, "directionDeg": 90.0}, 0.8, 4)
    assert abs(dx) < 1e-9 and dy == pytest.approx(6.4)


# ------------------------------------------------------------------------------------------ tyre smoke fit

def test_tyre_smoke_sits_on_the_rear_axle_and_blows_backward(cat):
    prof = _p("sports_car")
    s = check(_script([{"id": "tyre_smoke", "params": {}, "startS": 0.0, "endS": 4}]), prof, cat).script
    f = TS.fit(prof, s, cat, 0.0)
    rear = TS.rear_contacts(prof)
    assert len(rear) == 2
    fwd = TS._forward(prof)
    assert all(sum((r[i] - prof.center[i]) * fwd[i] for i in range(3)) < 0 for r in rear)
    assert f["scale"] == pytest.approx(f["trackM"] / 1.6, rel=1e-6)
    yaw = math.radians(f["yawDeg"])
    assert (math.cos(yaw), math.sin(yaw)) == pytest.approx((fwd[0], fwd[1]), abs=1e-6)
    ax = (f["anchor"][0] + f["scale"] * TS.LIB_AXLE_X * math.cos(yaw),
          f["anchor"][1] + f["scale"] * TS.LIB_AXLE_X * math.sin(yaw))
    assert ax == pytest.approx(tuple(f["axleMid"][:2]), abs=1e-6)
