"""Phase 5 grows worlds, grade params, cameras and motions. The frozen phase-3 default must not notice:
it rolls moods from a FROZEN tuple, keeps studio_cyc, and every one of the 90 frozen scripts stays the same
script (new params only appear at their off default)."""
import copy
import json

from engine.catalog import Catalog
from engine.director.baseline_phase3 import BASELINE
from engine.director.direction import AXES, PHASE3_MOODS, interim_direction
from engine.director.floor import phase3_default, script_tier
from engine.director.job import make_job
from engine.tests.test_director_package import _p

CASES = json.loads(BASELINE.read_text(encoding="utf-8"))["cases"]


# Params phase 5 might add to EXISTING blocks (default "off"), and new selectable blocks of every kind.
ADDED_PARAMS = {("grade", "mood_grade"): "zzHalation", ("grade", "neutral_film"): "zzGrain",
                ("world", "studio_cyc"): "zzTimeOfDay", ("lighting", "softbox_three_point"): "zzSunDeg",
                ("camera", "*"): "zzRollDeg", ("motion", "*"): "zzSpeed"}
NEW_BLOCKS = {("world", "zz_new_world"): ("world", "studio_cyc"), ("camera", "zz_new_cam"): ("camera", "arc_orbit"),
              ("motion", "zz_new_motion"): ("motion", "static"),
              ("lighting", "zz_new_light"): ("lighting", "softbox_three_point")}


def _grown(cat):
    """A catalog grown the way phase 5 grows it: an extra mood preset, new off-by-default params on existing
    worlds/lights/grades/cameras/motions, and new selectable world, camera, motion and lighting blocks."""
    g = copy.copy(cat)
    g._blocks = copy.deepcopy(cat._blocks)
    grade = g._blocks[("grade", "mood_grade")]
    grade["params"]["preset"]["values"] = list(grade["params"]["preset"]["values"]) + ["zz_new_mood"]
    for (kind, bid), name in ADDED_PARAMS.items():
        for (k, b), m in g._blocks.items():
            if k == kind and bid in ("*", b):
                m["params"][name] = {"type": "number", "min": 0.0, "max": 1.0, "default": 0.0}
    for (kind, new), src in NEW_BLOCKS.items():
        m = copy.deepcopy(g._blocks[src])
        m["id"], m["directorSelectable"] = new, True
        g._blocks[(kind, new)] = m
    return g


def _without_added(script):
    """The script with every ADDED param removed, asserting each was filled at its "off" default: the only
    difference growth may make to a phase-3 script."""
    names = set(ADDED_PARAMS.values())

    def walk(x):
        if isinstance(x, dict):
            out = {}
            for k, v in x.items():
                if k == "params" and isinstance(v, dict):
                    assert all(v[n] == 0.0 for n in names & set(v)), v
                    v = {pk: pv for pk, pv in v.items() if pk not in names}
                out[k] = walk(v)
            return out
        return [walk(v) for v in x] if isinstance(x, list) else x
    return walk(script)


def _scripts(cat, grown, cases=CASES):
    for case in cases:
        p = _p(case["model"])
        d0 = interim_direction(case["seed"], p, cat)
        d1 = interim_direction(case["seed"], p, grown)
        j0 = make_job(case["prompt"], p, cat, seed=case["seed"], direction=d0)
        j1 = make_job(case["prompt"], p, grown, seed=case["seed"], direction=d1)
        yield case, p, d0, d1, phase3_default(j0, p, cat), phase3_default(j1, p, grown)


def test_axes_are_frozen_at_seven():
    assert AXES == ("world", "mood", "tone", "pace", "opener", "weather", "wind")   # a new axis changes every id


def test_interim_moods_are_frozen():
    cat = Catalog.load()
    assert set(PHASE3_MOODS) <= set(cat.get("grade", "mood_grade")["params"]["preset"]["values"])


def test_phase3_default_ignores_catalog_growth():
    """All 90 frozen cases: the COMPLETE script is unchanged by growth (camera, grade, motion, weather and
    every param), apart from new params filled at their off default. Takes about 2.5 s, so it stays fast."""
    cat = Catalog.load()
    grown = _grown(cat)
    for case, p, d0, d1, s0, s1 in _scripts(cat, grown):
        assert d0 == d1 and d0.world == "studio_cyc"
        assert (script_tier(s0, p, cat), len(s0["shots"]), s0["direction"]["id"]) ==                (case["tier"], case["shots"], case["directionId"])
        assert _without_added(s1) == s0, case


def test_the_guard_sees_a_changed_param_the_old_tuple_check_missed():
    """Mutation: moving an existing default leaves tier, shot count and direction id alone (the old guard
    passed) but changes the script, which the full comparison catches."""
    cat = Catalog.load()
    bad = _grown(cat)
    bad._blocks[("camera", "arc_orbit")]["params"]["easing"]["default"] = "smoothstep"     # a camera-move change
    diffs = old_equal = 0
    for case, p, _, _, s0, s1 in _scripts(cat, bad, CASES[::9]):        # 10 spread cases suffice here
        old_equal += (script_tier(s0, p, cat), len(s0["shots"]), s0["direction"]["id"]) ==                      (script_tier(s1, p, bad), len(s1["shots"]), s1["direction"]["id"])
        diffs += _without_added(s1) != s0
    assert old_equal == 10 and diffs > 0
