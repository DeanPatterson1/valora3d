"""Phase 6 lane P, Task 106: tyre_spray and dust_kick (drive couplings): manifests, checker behaviour and the pure
emitter maths (engine/physics/road_spray.py): particles leave the rolling tyre contacts carried by the drive's own
pose function, only above 15 km/h, rear tyres more than front, the rooster tail up and behind."""
import json
import math
import random
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.motion_path import apply, pose_fn
from engine.physics import road_spray as R
from engine.tests.test_director_package import _p

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def cat():
    return Catalog.load()


def _drive_script(world="rain_courtyard", speed=40.0, sims=None):
    s = json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))
    s["format"] = {"aspect": "16:9", "durationS": 4, "fps": 24}
    s["world"] = {"id": world, "params": {}}
    s["lighting"] = {"id": Catalog.load().get("world", world)["lightingPairs"][0], "params": {}}
    s["subject"]["motion"] = {"id": "drive", "params": {"speedKmh": speed, "startS": 0.0, "driveS": 4.0}}
    s["shots"] = [{"startS": 0, "endS": 4, "camera": {"id": "rolling_track", "params": {}}, "focus": "subject"}]
    s["sims"] = sims if sims is not None else []
    return s


@pytest.mark.parametrize("bid,cap,tax,grounds", [
    ("tyre_spray", "vehicle.spray", "VD-12", ["asphalt", "concrete", "cobblestone"]),
    ("dust_kick", "vehicle.dust", "VD-11", ["dirt", "gravel", "sand", "grass"])])
def test_manifests(cat, bid, cap, tax, grounds):
    m = cat.get("sim", bid)
    assert m["directorSelectable"] is False and m["capabilities"] == [cap]
    assert m["physics"]["taxonomy"] == [tax] and m["requiresProfile"] == ["wheels"]
    assert m["physics"]["requiresWorld"] == {"outdoor": True, "hasGround": True, "groundType": grounds}
    assert (m["params"]["density"]["min"], m["params"]["density"]["max"], m["params"]["density"]["default"]) == (0.2, 2.0, 1.0)
    b = m["bake"]
    assert b["method"] == "gn_disk" and b["costClass"] == "cheap" and b["cacheMBMax"] <= 500
    assert m["physics"]["bakeCostS"] > 0


def test_worlds_gate_the_two_blocks(cat):
    wet = check(_drive_script(sims=[{"id": "tyre_spray", "params": {}, "startS": 0, "endS": 4}]), _p("sports_car"), cat)
    assert wet.ok, [i for i in wet.issues if i.severity == "error"]
    field = check(_drive_script("golden_field", sims=[{"id": "tyre_spray", "params": {}, "startS": 0, "endS": 4}]),
                  _p("sports_car"), cat)
    assert any(i.code == "sim_needs_world" for i in field.issues)
    dust = check(_drive_script("golden_field", sims=[{"id": "dust_kick", "params": {}, "startS": 0, "endS": 4}]),
                 _p("sports_car"), cat)
    assert dust.ok, [i for i in dust.issues if i.severity == "error"]
    assert not any(i.code == "sim_needs_world" for i in dust.issues)


def test_speed_ramp():
    assert R.speed_ramp(10 / 3.6) == 0.0
    assert R.speed_ramp(15 / 3.6) == 0.0 and R.speed_ramp(30 / 3.6) == 1.0
    assert 0 < R.speed_ramp(20 / 3.6) < 1


def _checked(cat, speed=40.0, world="rain_courtyard"):
    r = check(_drive_script(world, speed), _p("sports_car"), cat)
    assert r.ok
    return r.script


def test_particles_leave_the_tyres_through_the_drive_pose(cat):
    s, p = _checked(cat), _p("sports_car")
    ps = R.particles("spray", {"density": 1.0}, s, p, cat, 1, 96, 24, random.Random(3))
    assert 1500 < len(ps) < R.MAX_PER_BLOCK          # the lane caps this drive at ~21.6 km/h (6 m/s)
    assert ps == R.particles("spray", {"density": 1.0}, s, p, cat, 1, 96, 24, random.Random(3))      # seeded
    pose_at = pose_fn(s, p, cat)
    contacts = [w["contact"] for w in p.wheels]
    for q in ps[::97]:
        t = (math.floor(q["birth"]) + 1 - 1) / 24          # the frame it was born in
        near = min(math.dist(q["pos"][:2], apply(c, pose_at(t), p)[:2]) for c in contacts)
        assert near < 0.6, (q, near)                      # at a tyre (within its radius + width)
        assert q["vel"][2] >= 0                           # thrown up, never into the road
        assert 0.0002 <= q["size"] <= 0.12                   # fine mist 0.2 mm .. a puff


def test_rear_tyres_throw_more_than_front(cat):
    s, p = _checked(cat), _p("sports_car")
    pose_at = pose_fn(s, p, cat)
    rear = front = 0
    for f in range(40, 60):                               # one frame at a time: the car moves 25 cm per frame
        ps = R.particles("spray", {"density": 1.0}, s, p, cat, f, f, 24, random.Random(f))
        states = [R.wheel_state(pose_at, p, w, (f - 1) / 24) for w in p.wheels]
        vcar = states[0][1]
        fwd = [c / math.sqrt(sum(x * x for x in vcar)) for c in vcar]
        mid = sum(sum(a * b for a, b in zip(st[0], fwd)) for st in states) / len(states)
        for q in ps:
            if sum(a * b for a, b in zip(q["pos"], fwd)) < mid:
                rear += 1
            else:
                front += 1
    assert rear > 2 * front, (rear, front)


def test_slow_drive_makes_nothing(cat):
    s, p = _checked(cat, speed=10.0), _p("sports_car")
    assert R.particles("dust", {"density": 1.0}, s, p, cat, 1, 96, 24, random.Random(1)) == []


def test_density_scales_the_count(cat):
    s, p = _checked(cat, world="golden_field"), _p("sports_car")
    a = len(R.particles("dust", {"density": 1.0}, s, p, cat, 1, 48, 24, random.Random(1)))
    b = len(R.particles("dust", {"density": 2.0}, s, p, cat, 1, 48, 24, random.Random(1)))
    assert 1.9 * a <= b <= 2.1 * a


def test_hero_pass_mist_is_many_fine_droplets_not_a_few_big_puffs(cat):
    """Hero pass (2026-09-28): the lane clip's spray mist read as round blobs (a few 4-12 cm uniform puffs). The
    mist is now carried by a fine population of sub-millimetre droplets that outnumber the puffs by far; puffs are
    smaller; every particle carries its own drag and gravity share (mist hangs in the air, grains fly)."""
    s, p = _checked(cat), _p("sports_car")
    ps = R.particles("spray", {"density": 1.0}, s, p, cat, 1, 96, 24, random.Random(3))
    fine = [q for q in ps if q["fine"] == 1.0]
    puff = [q for q in ps if q["puff"] == 1.0]
    grain = [q for q in ps if q["fine"] == 0.0 and q["puff"] == 0.0]
    assert fine and puff and grain and len(fine) > 15 * len(puff) and len(fine) > 3 * len(grain)
    assert all(0.0002 <= q["size"] <= 0.0007 for q in fine) and all(q["size"] <= 0.08 for q in puff)
    assert {q["k"] for q in fine} == {R.SPRAY["fineDrag"]} and {q["fall"] for q in fine} == {R.SPRAY["fineFall"]}
    assert {q["k"] for q in grain} == {R.SPRAY["drag"]} and {q["fall"] for q in puff} == {R.SPRAY["puffFall"]}
    assert R.SPRAY["fineFall"] < 0.5 < R.SPRAY["fall"] and R.SPRAY["fineDrag"] > R.SPRAY["drag"]
    assert all(q["vel"][2] >= 0 for q in fine)


def test_hero_pass_dust_motes_hang_longer_than_grit(cat):
    s, p = _checked(cat, world="golden_field"), _p("sports_car")
    ps = R.particles("dust", {"density": 1.0}, s, p, cat, 1, 48, 24, random.Random(2))
    fine = [q for q in ps if q["fine"] == 1.0]
    assert fine and min(q["life"] for q in fine) >= R.DUST["fineLifeS"][0]
    assert R.DUST["fineFall"] < 0.2 and R.DUST["fineLifeS"][0] > R.DUST["grainLifeS"][1]
