"""Phase 6 Task 104 (lane P): the `runners` and `condensation` manifests, their checker behaviour and their pure
maths (engine/physics/runners.py, engine/physics/condensation.py). The lane keeps its own file so the parallel
lanes never edit one test module."""
import json
import math
import random
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.physics import condensation as C
from engine.physics import gn_sim
from engine.physics import runners as R
from engine.tests.test_director_package import _p

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def cat():
    return Catalog.load()


def _script(sims):
    s = json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))
    s["sims"] = sims
    return s


def _num(m, k):
    return (m["params"][k]["min"], m["params"][k]["max"], m["params"][k]["default"])


# ---------------------------------------------------------------- manifests

def test_runners_manifest(cat):
    m = cat.get("sim", "runners")
    assert m["directorSelectable"] is False and m["tierMax"] == "T4"
    assert _num(m, "count") == (3, 30, 3)                 # the default is condensation's coupled count
    assert _num(m, "speedCmS") == (1.0, 10.0, 3.0)
    assert _num(m, "dropMm") == (1.5, 4.0, 2.5)
    assert _num(m, "timeScale") == (0.25, 1.0, 1.0)
    assert m["params"]["trail"] == {"type": "bool", "default": True}
    ph = m["physics"]
    assert ph["taxonomy"] == ["FL-04", "FL-20"] and ph["state"] == "baked" and ph["touchesSubject"] is True
    assert ph["timeScaleParam"] == "timeScale" and ph["windDriven"] is False
    assert ph["bakeCostS"] > 0
    assert m["requiresProfile"] == ["upFacing"] and "requiresSimFacts" not in ph
    b = m["bake"]
    assert (b["method"], b["costClass"], b["prerollS"], b["maxFrames"]) == ("gn_disk", "cheap", 0, 300)
    assert b["proxies"] == [] and b["maxSpeedMs"] == 3   # it runs on the render surface, not a shell
    assert b["estimateS"] >= R.estimate_s(30, 300) and b["cacheMBMax"] >= R.cache_mb_max(30, 300)
    assert m["capabilities"] == ["liquid.run_down"]


def test_condensation_manifest(cat):
    m = cat.get("sim", "condensation")
    assert m["directorSelectable"] is False and m["tierMax"] == "T4"
    assert _num(m, "density") == (20, 60, 35)
    assert _num(m, "fog") == (0.0, 1.0, 0.5)
    ph = m["physics"]
    assert ph["taxonomy"] == ["FL-05"] and ph["state"] == "stateless" and ph["couplings"] == ["runners"]
    assert m["requiresProfile"] == ["upFacing"]
    assert m["bake"] == {"method": "none", "costClass": "cheap"}
    assert m["capabilities"] == ["liquid.condensation"]
    assert not (Path(cat.root) / "sim" / "condensation" / "bake.py").exists()   # stateless: nothing to bake


def test_condensation_couples_three_runners_with_its_window(cat):
    r = check(_script([{"id": "condensation", "params": {}, "startS": 0.0, "endS": 4.0}]), _p("sneaker"), cat)
    assert r.ok, [i for i in r.issues if i.severity == "error"]
    sims = {x["id"]: x for x in r.script["sims"]}
    assert sims["runners"]["params"]["count"] == 3
    assert (sims["runners"]["startS"], sims["runners"]["endS"]) == (0.0, 4.0)
    assert any(i.code == "coupled_added" and "runners" in i.message for i in r.issues)


def test_runners_check_clean_on_the_studio(cat):
    r = check(_script([{"id": "runners", "params": {"count": 12}, "startS": 1.0, "endS": 5.0}]), _p("sneaker"), cat)
    assert r.ok, [i for i in r.issues if i.severity == "error"]


# ---------------------------------------------------------------- runners maths

def test_run_velocity_is_tangential_gravity_times_speed_and_slope():
    assert R.run_velocity((1.0, 0.0, 0.0), 0.03) == pytest.approx((0.0, 0.0, -0.03), abs=1e-15)
    s = math.sqrt(0.5)
    assert R.run_velocity((s, 0.0, s), 0.04) == pytest.approx((0.02, 0.0, -0.02), abs=1e-12)
    assert R.run_velocity((0.0, 0.0, 1.0), 0.05) == (0.0, 0.0, 0.0)          # a level top: a drop stays put
    for n in ((0.3, 0.4, 0.866), (0.0, -1.0, 0.0), (0.6, 0.0, -0.8)):
        v = R.run_velocity(R._unit(n), 0.05)
        assert v[2] <= 0.0                                                    # never uphill
        assert abs(sum(a * b for a, b in zip(v, R._unit(n)))) < 1e-12         # on the surface


def test_stick_slip_pauses_then_moves():
    assert R.moving(0.05, 0.0, 0.1, 0.5) is False
    assert R.moving(0.3, 0.0, 0.1, 0.5) is True
    assert R.moving(0.65, 0.0, 0.1, 0.5) is False         # cycle 0.6: 0.05 into the second pause
    assert R.moving(0.0, 0.35, 0.1, 0.5) is True           # the phase shifts the schedule


def test_detach_on_a_convex_edge_or_an_underside():
    assert R.detaches((1.0, 0.0, 0.0), (0.0, 0.0, -1.0)) is True          # underside
    assert R.detaches((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)) is True            # turned 90 degrees: an edge
    assert R.detaches((1.0, 0.0, 0.0), (0.98, 0.0, -0.199)) is False       # a gentle bend
    assert (R.EDGE_DOT, R.DETACH_NZ) == (0.6, -0.5)


def _cylinder(r=0.03, h=0.12, seg=24):
    verts, tris, normals = [], [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        verts += [(r * math.cos(a), r * math.sin(a), 0.0), (r * math.cos(a), r * math.sin(a), h)]
    for i in range(seg):
        j = (i + 1) % seg
        a0, a1 = 2 * math.pi * (i + 0.5) / seg, 0.0
        n = (math.cos(a0), math.sin(a0), 0.0)
        tris += [(2 * i, 2 * j, 2 * j + 1), (2 * i, 2 * j + 1, 2 * i + 1)]
        normals += [n, n]
    top = len(verts)
    verts.append((0.0, 0.0, h))
    for i in range(seg):
        tris.append((top, 2 * i + 1, 2 * ((i + 1) % seg) + 1))
        normals.append((0.0, 0.0, 1.0))
    return verts, tris, normals


def test_seed_runners_on_the_side_below_the_fill_line_seeded():
    verts, tris, normals = _cylinder()
    kw = dict(count=12, fill_z=0.1, z_min=0.0, height=0.12, first=1, last=121, fps=30, speed_cms=3.0, drop_mm=2.5)
    a = R.seed_runners(verts, tris, normals, rng=random.Random(7), **kw)
    b = R.seed_runners(verts, tris, normals, rng=random.Random(7), **kw)
    assert a == b and len(a) == 12
    lo, hi = R.seed_band(0.1, 0.0, 0.12, 0.0025)
    assert (lo, hi) == pytest.approx((0.03, 0.1 - 0.0025))
    for p in a:
        x, y, z = p["pos"]
        assert lo - 1e-9 <= z <= hi + 1e-9
        assert math.hypot(x, y) == pytest.approx(0.03 * math.cos(math.pi / 24) + R.SKIN_M, abs=2e-3)
        assert 1 <= p["birth"] <= 1 + R.STAGGER * 121
        assert 0.01 <= p["speed"] <= 0.10
        assert R.PAUSE_S[0] <= p["pause"] <= R.PAUSE_S[1] and R.MOVE_S[0] <= p["move"] <= R.MOVE_S[1]
        assert 0.0025 * (1 - R.SIZE_JITTER) - 1e-12 <= p["size"] <= 0.0025 * (1 + R.SIZE_JITTER) + 1e-12
        assert p["vel"] == (0.0, 0.0, 0.0) and p["trail"] == 0.0 and p["free"] == 0.0
        assert p["life"] == pytest.approx((121 - p["birth"]) / 30 + 1.0)
        assert math.hypot(*p["n"]) == pytest.approx(1.0) and abs(p["n"][2]) < 1e-9


def test_seed_runners_clamps_the_count_and_needs_a_side():
    verts, tris, normals = _cylinder()
    kw = dict(fill_z=0.1, z_min=0.0, height=0.12, first=1, last=60, fps=30, speed_cms=3.0, drop_mm=2.5)
    assert len(R.seed_runners(verts, tris, normals, count=1, rng=random.Random(1), **kw)) == 3
    assert len(R.seed_runners(verts, tris, normals, count=99, rng=random.Random(1), **kw)) == 30
    top_only = [i for i, n in enumerate(normals) if n[2] > 0.9]
    assert R.seed_runners(verts, [tris[i] for i in top_only], [normals[i] for i in top_only], count=5,
                          rng=random.Random(1), **kw) == []


def test_runner_budget_numbers():
    assert R.trail_points(3, 150) == int(3 * 150 * R.MOVE_SHARE_MAX)
    assert R.estimate_s(3, 150) == pytest.approx(gn_sim.estimate_s(3 + R.trail_points(3, 150), 150, R.SUBSTEPS))
    assert R.cache_mb_max(30, 300) == pytest.approx((30 + R.trail_points(30, 300)) * 300 * R.BYTES_PER_POINT / 1e6)


# ---------------------------------------------------------------- condensation maths

def test_condensation_density_and_sizes():
    assert C.per_m2(35) == 350000.0 and C.per_m2(20) == 200000.0 and C.per_m2(60) == 600000.0
    assert C.size_m(0.0) == pytest.approx(0.0002) and C.size_m(1.0) == pytest.approx(0.0015)
    assert C.size_m(0.5) == pytest.approx(0.0002 + 0.0013 * 0.25)
    assert C.expected_count(0.075, 35) == 26250
    assert C.effective_per_m2(10.0, 60) == C.MAX_DROPS / 10.0              # a big surface is capped
    assert C.effective_per_m2(0.075, 35) == 350000.0


def test_condensation_zone_is_below_the_fill_line_and_not_facing_down():
    assert C.in_zone((1.0, 0.0, 0.0), 0.05, 0.1) is True
    assert C.in_zone((0.0, 0.0, 1.0), 0.05, 0.1) is True
    assert C.in_zone((1.0, 0.0, 0.0), 0.15, 0.1) is False                  # a dry shoulder above the line
    assert C.in_zone((0.0, 0.0, -1.0), 0.05, 0.1) is False                 # the underside drips, it does not bead
    assert C.FILM_M == 0.00015


def test_the_block_modules_load_without_bpy(cat):
    import sys
    assert callable(cat.load_builder("sim", "runners")) and callable(cat.load_baker("runners"))
    assert callable(cat.load_builder("sim", "condensation"))
    assert "bpy" not in sys.modules
