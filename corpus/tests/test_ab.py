import json

import pytest

from corpus.ab import PAIRS, record_for, scripts_for, set_path
from corpus.schema import validate
from engine.catalog import Catalog
from engine.checker import check
from engine.profile import SubjectProfile
from corpus import ROOT


def _profile(model):
    p = ROOT / "engine" / "tests" / "fixtures" / "profiles" / f"{model}.json"
    return SubjectProfile.from_dict(json.loads(p.read_text(encoding="utf-8")))


def test_set_path_handles_lists_and_dicts():
    s = {"shots": [{"camera": {"params": {"lensMm": 40}}}], "effects": []}
    set_path(s, "shots[0].camera.params.lensMm", 85)
    set_path(s, "effects", [{"id": "haze_volume", "params": {}}])
    assert s["shots"][0]["camera"]["params"]["lensMm"] == 85 and s["effects"][0]["id"] == "haze_volume"


def test_ten_pairs_with_unique_names():
    assert len(PAIRS) == 10 and len({p["name"] for p in PAIRS}) == 10


@pytest.mark.parametrize("pair", PAIRS, ids=[p["name"] for p in PAIRS])
def test_both_variants_pass_the_checker_and_differ(pair):
    cat = Catalog.load()
    a, b = scripts_for(pair)
    prof = _profile(pair["model"])
    ra, rb = check(a, prof, cat), check(b, prof, cat)
    assert ra.ok and rb.ok, [i.to_dict() for i in ra.issues + rb.issues if i.severity == "error"]
    assert a != b


@pytest.mark.parametrize("pair", PAIRS, ids=[p["name"] for p in PAIRS])
def test_record_from_script_ground_truth_validates(pair):
    rec = record_for(pair, Catalog.load())
    assert validate(rec) == []
    assert rec["method"] == "script_ground_truth" and rec["ab"]["finding"] is None


def test_cli_render_is_owner_gated(capsys):
    from corpus.__main__ import main
    assert main(["ab", "render", "--pair", PAIRS[0]["name"]]) == 2
    assert "Owner-gated" in capsys.readouterr().out


def test_cli_record_writes_a_valid_draft(tmp_path, monkeypatch):
    import corpus.ab as ab_mod
    from corpus.__main__ import main
    monkeypatch.setattr(ab_mod, "DRAFTS", tmp_path)
    assert main(["ab", "record", "--pair", PAIRS[0]["name"]]) == 0
    rec = json.loads((tmp_path / f"ab-{PAIRS[0]['name']}.json").read_text(encoding="utf-8"))
    assert validate(rec) == []
