import copy
import json
import shutil
from pathlib import Path

import pytest

from engine.catalog import BLOCKS_DIR, Catalog
from engine.checker import check
from engine.director.hard_rules import HARD_RULES, render_hard_rules
from engine.profile import SubjectProfile

ROOT = Path(__file__).resolve().parents[2]
T3 = json.loads((ROOT / "harness" / "suites" / "v0" / "t3_attempt.json").read_text(encoding="utf-8"))
CAR = json.loads((ROOT / "engine" / "tests" / "fixtures" / "profiles" / "sports_car.json").read_text(encoding="utf-8"))


def _codes(script, profile=None, catalog=None):
    r = check(script, SubjectProfile.from_dict(profile or CAR), catalog or Catalog.load())
    return {i.code for i in r.issues}


def _no_detail(s):
    for i, sh in enumerate(s["shots"]):
        if sh["camera"]["id"] == "macro_detail":
            sh["camera"] = {"id": "arc_orbit", "params": {"startAzimuthDeg": -100 + 60 * i}}


def _long_hero(s):
    del s["shots"][3]
    s["shots"][3]["startS"] = 5.5


MUTATE = {
    "unknown_block": lambda s: s["world"].update(id="moon"),
    "param_clamped": lambda s: s["shots"][0]["camera"]["params"].update(lensMm=500),
    "shots_not_contiguous": lambda s: s["shots"][1].update(startS=2.5),
    "shot_not_frame_aligned": lambda s: (s["shots"][0].update(endS=2.013), s["shots"][1].update(startS=2.013)),
    "shot_too_short": lambda s: (s["shots"][1].update(endS=61 / 30), s["shots"][2].update(startS=61 / 30)),
    "bad_focus": lambda s: s["shots"][0].update(focus="background"),
    "reserved_not_in_v1": lambda s: s.update(audio={"id": "x"}),
    "transition_not_available": lambda s: s["shots"][1].update(transitionIn="whip"),
    "unknown_target": lambda s: s["shots"][1].update(target={"marker": "nope"}),
    "bad_purpose": lambda s: s["shots"][0].update(purpose="vibes"),
    "seq_no_detail": _no_detail,
    "seq_bad_hook": lambda s: s["shots"][0].update(purpose="hero"),
    "seq_bad_ending": lambda s: s["shots"][-1].update(purpose="detail"),
    "seq_shot_length": _long_hero,
    "bad_marker_text": lambda s: s.update(markers=[{"id": "m1", "text": "hi\u0007",
                                                    "anchor": {"space": "placed", "point": [0, 0, 0.5]}}]),
    "marker_off_subject": lambda s: s.update(markers=[{"id": "m1", "text": "hi",
                                                       "anchor": {"space": "placed", "point": [50, 50, 50]}}]),
    "bad_unsupported": lambda s: s.update(unsupported=[{"ask": "rain"}]),
}


def test_base_script_passes():
    assert not {c for c in _codes(copy.deepcopy(T3))} & set(MUTATE)


CASES = [(r["id"], c) for r in HARD_RULES for c in r["enforced_by"] if not c.startswith("director:")]


@pytest.mark.parametrize("rule,code", CASES, ids=[f"{r}-{c}" for r, c in CASES])
def test_every_checker_code_of_every_rule_fires(rule, code, tmp_path):
    s = copy.deepcopy(T3)
    if code == "subject_size_unsupported":
        big = copy.deepcopy(CAR)
        for k in ("sizeM", "boundsMin", "boundsMax"):
            big[k] = [v * 5 for v in big[k]]
        assert code in _codes(s, profile=big)
    elif code == "world_has_no_ground":
        root = tmp_path / "blocks"
        shutil.copytree(BLOCKS_DIR, root, ignore=shutil.ignore_patterns("__pycache__"))
        f = root / "world" / "studio_cyc" / "block.json"
        m = json.loads(f.read_text(encoding="utf-8"))
        m["hasGround"] = False
        f.write_text(json.dumps(m), encoding="utf-8")
        assert code in _codes(s, catalog=Catalog.load(root))
    elif code == "camera_distance_adjusted":
        assert code in _codes(s)  # the unmutated T3 script already needs it on the car (4.0 -> ~4.6)
    else:
        MUTATE[code](s)
        assert code in _codes(s)


def test_render_mentions_every_rule_and_its_codes():
    text = render_hard_rules()
    for r in HARD_RULES:
        assert r["id"] in text and all(c in text for c in r["enforced_by"])
