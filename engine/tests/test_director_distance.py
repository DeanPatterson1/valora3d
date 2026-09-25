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
