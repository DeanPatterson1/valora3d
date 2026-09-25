"""Phase 5 grows worlds, grade params, cameras and motions. The frozen phase-3 default must not notice:
it rolls moods from a FROZEN tuple, keeps studio_cyc, and fills no new param differently."""
import copy
import json

from engine.catalog import Catalog
from engine.director.baseline_phase3 import BASELINE
from engine.director.direction import AXES, PHASE3_MOODS, interim_direction
from engine.director.floor import phase3_default, script_tier
from engine.director.job import make_job
from engine.tests.test_director_package import _p

CASES = json.loads(BASELINE.read_text(encoding="utf-8"))["cases"]


def _grown(cat):
    """A catalog with an extra world and an extra mood preset, as phase 5 might add."""
    g = copy.copy(cat)
    g._blocks = copy.deepcopy(cat._blocks)
    grade = g._blocks[("grade", "mood_grade")]
    grade["params"]["preset"]["values"] = list(grade["params"]["preset"]["values"]) + ["zz_new_mood"]
    w = copy.deepcopy(g._blocks[("world", "studio_cyc")])
    w["id"] = "zz_new_world"
    g._blocks[("world", "zz_new_world")] = w
    return g


def test_axes_are_frozen_at_seven():
    assert AXES == ("world", "mood", "tone", "pace", "opener", "weather", "wind")   # a new axis changes every id


def test_interim_moods_are_frozen():
    cat = Catalog.load()
    assert set(PHASE3_MOODS) <= set(cat.get("grade", "mood_grade")["params"]["preset"]["values"])


def test_phase3_default_ignores_catalog_growth():
    cat = Catalog.load()
    grown = _grown(cat)
    for case in CASES[::9]:                          # 10 spread cases; the full 90 run in test_director_floor
        p = _p(case["model"])
        d0 = interim_direction(case["seed"], p, cat)
        d1 = interim_direction(case["seed"], p, grown)
        assert d0 == d1 and d0.world == "studio_cyc"
        job = make_job(case["prompt"], p, cat, seed=case["seed"], direction=d0)
        s0, s1 = phase3_default(job, p, cat), phase3_default(job, p, grown)
        assert (script_tier(s0, p, cat), len(s0["shots"]), s0["direction"]["id"]) == \
               (case["tier"], case["shots"], case["directionId"]) == \
               (script_tier(s1, p, grown), len(s1["shots"]), s1["direction"]["id"])
