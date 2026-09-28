"""Phase 6 lane P, Task 105: the particle pack (sparks, confetti, bubbles, embers): manifests, checker behaviour
and the pure particle maths (engine/physics/particle_pack.py). Lane P keeps its own test files (the recipe's
test_blocks_phase6.py is shared between lanes)."""
import json
import math
import random
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.physics import particle_pack as P
from engine.tests.test_director_package import _p

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def cat():
    return Catalog.load()


def _num(m, k):
    return (m["params"][k]["min"], m["params"][k]["max"], m["params"][k]["default"])


def _script(sims=(), effects=(), markers=None):
    s = json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))
    s["sims"] = list(sims)
    s["effects"] = list(effects)
    if markers is not None:
        s["markers"] = markers
    return s


# ------------------------------------------------------------------------------------------ manifests

@pytest.mark.parametrize("bid,cap,tax", [("sparks", "particles.sparks", "PT-08"),
                                         ("confetti", "particles.confetti", "PT-06"),
                                         ("bubbles", "particles.bubbles", "PT-10")])
def test_gn_particle_manifests(cat, bid, cap, tax):
    m = cat.get("sim", bid)
    assert m["directorSelectable"] is False and m["capabilities"] == [cap]
    assert tax in m["physics"]["taxonomy"] and m["physics"]["state"] == "baked"
    assert m["physics"]["timeScaleParam"] == "timeScale"
    b = m["bake"]
    assert b["method"] == "gn_disk" and b["costClass"] == "cheap" and b["maxFrames"] == 240
    assert b["cacheMBMax"] <= 500 and b["estimateS"] <= 600
    assert m["physics"]["bakeCostS"] > 0                         # measured (recipe step 5), not a guess


def test_sparks_params_and_requirements(cat):
    m = cat.get("sim", "sparks")
    assert _num(m, "rate") == (100, 3000, 600)
    assert _num(m, "speedMs") == (3.0, 15.0, 7.0)
    assert _num(m, "lifeS") == (0.3, 1.5, 0.8)
    assert _num(m, "spreadDeg") == (10, 80, 35)
    assert m["physics"]["requiresSimFacts"] == ["emitters"] and m["physics"]["requiresWorld"] == {"hasGround": True}


def test_confetti_params(cat):
    m = cat.get("sim", "confetti")
    assert _num(m, "count") == (100, 3000, 800)
    assert m["params"]["palette"]["values"] == ["mixed", "gold", "silver", "grade"]
    assert m["physics"]["spawnZone"]["kind"] == "above"


def test_bubbles_params(cat):
    m = cat.get("sim", "bubbles")
    assert _num(m, "rate") == (5, 300, 60)
    assert _num(m, "sizeMm") == (0.3, 4.0, 1.2)
    assert m["physics"]["requiresSimFacts"] == ["container"]


def test_embers_is_a_stateless_effect(cat):
    m = cat.get("effect", "embers")
    assert m["directorSelectable"] is False and m["capabilities"] == ["particles.embers"]
    assert m["physics"]["state"] == "stateless" and "PT-09" in m["physics"]["taxonomy"]
    assert _num(m, "count") == (20, 600, 150)


def test_sparks_without_an_emitter_is_refused_and_with_a_marker_passes(cat):
    sim = {"id": "sparks", "params": {}, "startS": 1.0, "endS": 4.0}
    r = check(_script([sim]), _p("sneaker"), cat)
    assert any(i.code == "sim_needs_profile" for i in r.issues)
    mk = [{"id": "grind", "text": "sparks fly from the heel", "anchor": {"space": "placed",
           "point": list(_p("sneaker").surfaceSamples[0]), "normal": [0, -1, 0.3]}}]
    r = check(_script([sim], markers=mk), _p("sneaker"), cat)
    assert r.ok, [i for i in r.issues if i.severity == "error"]


def test_bubbles_need_a_container(cat):
    r = check(_script([{"id": "bubbles", "params": {}, "startS": 0.5, "endS": 4.0}]), _p("sneaker"), cat)
    assert any(i.code == "sim_needs_profile" for i in r.issues)


# ------------------------------------------------------------------------------------------ pure maths

EMIT = {"point": [0.0, 0.0, 0.3], "normal": [0.0, -1.0, 0.2]}


def test_sparks_particles():
    ps = P.sparks(dict(rate=600, speedMs=7.0, lifeS=0.8, spreadDeg=35), EMIT, 1, 72, 24, random.Random(1))
    assert len(ps) == round(600 * 72 / 24)
    for p in ps[:300]:
        s = math.sqrt(sum(c * c for c in p["vel"]))
        assert 0.5 * 7.0 <= s <= 1.5 * 7.0 + 1e-9
        assert 0.5 * 0.8 <= p["life"] <= 1.5 * 0.8
        assert P.SPARK_TEMP_K[0] <= p["temp"] <= P.SPARK_TEMP_K[1]
        assert P.SPARK_SIZE_M[0] <= p["size"] <= P.SPARK_SIZE_M[1]
        assert p["pos"] == pytest.approx(EMIT["point"], abs=0.02)
    n = P._unit(EMIT["normal"])
    mean = [sum(p["vel"][i] for p in ps) / len(ps) for i in range(3)]
    assert sum(a * b for a, b in zip(P._unit(mean), n)) > math.cos(math.radians(35))


def test_spark_blackbody_cools_to_dark():
    assert P.spark_temp(2000, 0.0, 1.0) == 2000
    assert P.spark_temp(2000, 1.0, 1.0) < P.DARK_K
    assert P.spark_temp(2000, 0.5, 1.0) < 2000


def test_confetti_burst_is_real_size_and_mixed():
    ps = P.confetti(dict(count=800, spreadM=1.0, palette="mixed"), (0.0, 0.0), 2.0, 1, 24, random.Random(2))
    assert len(ps) == 800
    assert all(0.01 <= p["size"] <= 0.03 for p in ps)                  # 1-3 cm cards
    assert all(p["birth"] < 1 + P.CONFETTI_BURST_S * 24 for p in ps)     # one shower, 0.8 s
    metal = sum(p["metal"] for p in ps) / len(ps)
    assert 0.25 < metal < 0.6
    assert all(abs(p["pos"][2] - 2.0) < 0.2 for p in ps)


def test_bubble_rise_speed_follows_size():
    assert P.bubble_rise(0.0005) == pytest.approx(0.08, abs=0.02)      # 1 mm diameter: slow
    assert P.bubble_rise(0.002) == pytest.approx(0.33, abs=0.03)       # 4 mm: fastest
    assert P.bubble_rise(0.00015) >= 0.08 - 1e-9                        # clamped at the floor
    ps = P.bubbles(dict(rate=60, sizeMm=1.2), {"opening": [0, 0, 0.2], "radiusM": 0.03}, 0.02, 0.18,
                   1, 96, 24, random.Random(4))
    assert len(ps) == round(60 * 96 / 24)
    for p in ps:
        assert math.hypot(p["pos"][0], p["pos"][1]) <= 0.03 * P.BUBBLE_WALL_FRAC + 1e-9
        assert p["pos"][2] == pytest.approx(0.02, abs=1e-6)
        assert p["life"] * p["vel"][2] >= 0.16 - 1e-6                   # it lives long enough to reach the top


def test_ember_drift_is_analytic():
    a = P.ember_state(3, 1.25, seed=5, base=(0, 0, 0), spread=0.4, rise=0.3)
    assert a == P.ember_state(3, 1.25, seed=5, base=(0, 0, 0), spread=0.4, rise=0.3)
    b = P.ember_state(3, 1.30, seed=5, base=(0, 0, 0), spread=0.4, rise=0.3)
    assert b[0][2] > a[0][2]                                              # rises with time
    assert 0.0 <= a[1] <= 1.0                                             # flicker
