import json
import shutil
from pathlib import Path

import pytest

from engine.catalog import BLOCKS_DIR, Catalog, CatalogError
from engine.director.capabilities import detect, unsupported
from engine.realism import realism_defaults
from engine.script import validate_and_repair
from engine.tests.test_director_package import _p

T3 = Path(__file__).resolve().parents[2] / "harness" / "suites" / "v0" / "t3_attempt.json"


def _catalog_with_contact(tmp_path, kind="effect", **extra):
    root = tmp_path / "blocks"
    shutil.copytree(BLOCKS_DIR, root, ignore=shutil.ignore_patterns("__pycache__"))
    d = root / kind / "test_tyre_contact"
    d.mkdir(parents=True)
    m = json.loads((root / "effect" / "haze_volume" / "block.json").read_text(encoding="utf-8"))
    fields = dict(id="test_tyre_contact", kind=kind, description="test-only realism default", params={},
                  capabilities=["sim.tyre_contact"], alwaysOn=True, requiresProfile="wheels")
    fields.update(extra)
    m.update(fields)
    m.pop("atmosphere", None)
    for k in [k for k, v in m.items() if v is None]:  # None = leave the key out
        m.pop(k)
    (d / "block.json").write_text(json.dumps(m), encoding="utf-8")
    return Catalog.load(root)


def test_always_on_blocks_apply_by_profile_and_are_never_selectable(tmp_path):
    cat = _catalog_with_contact(tmp_path)
    assert "test_tyre_contact" not in cat.selectable_ids("effect")
    only = lambda rs: [r for r in rs if r["id"] == "test_tyre_contact"]
    assert only(realism_defaults(_p("sports_car"), cat)) == [{"kind": "effect", "id": "test_tyre_contact", "params": {}}]
    assert only(realism_defaults(_p("pocket_watch"), cat)) == []          # no wheels
    assert "sim.tyre_contact" in cat.capabilities(_p("sports_car"))
    assert "sim.tyre_contact" not in cat.capabilities(_p("pocket_watch"))


def test_realism_kind_is_always_on_and_delivers_its_tag_when_the_subject_qualifies(tmp_path):
    # research/physics/BLOCKS.md §1: kind `realism` = always-on (no explicit alwaysOn needed), and
    # requiresProfile may be a list. "tyres squish" is then not unsupported on a wheeled subject.
    cat = _catalog_with_contact(tmp_path, kind="realism", alwaysOn=None, requiresProfile=["wheels"])
    assert cat.selectable_ids("realism") == []
    only = [r for r in realism_defaults(_p("sports_car"), cat) if r["id"] == "test_tyre_contact"]
    assert only == [{"kind": "realism", "id": "test_tyre_contact", "params": {}}]
    asks = detect("tyres squish on the floor")
    assert [a["capability"] for a in asks] == ["sim.tyre_contact"]
    assert unsupported(asks, cat, _p("sports_car")) == []
    assert [u["capability"] for u in unsupported(asks, cat, _p("pocket_watch"))] == ["sim.tyre_contact"]


def test_script_realism_must_be_always_on(tmp_path):
    cat = _catalog_with_contact(tmp_path)
    s = json.loads(T3.read_text(encoding="utf-8"))
    s["realism"] = [{"kind": "effect", "id": "test_tyre_contact", "params": {}}]
    assert not [i for i in validate_and_repair(s, cat)[1] if i.severity == "error"]
    s["realism"] = [{"kind": "effect", "id": "haze_volume", "params": {}}]
    assert any(i.code == "realism_not_always_on" for i in validate_and_repair(s, cat)[1])
    s["realism"] = {"kind": "effect"}
    assert any(i.code == "bad_realism" for i in validate_and_repair(s, cat)[1])


def test_every_shipped_always_on_block_is_a_realism_block():
    assert {k for k, _ in Catalog.load().always_on()} <= {"realism"}


def test_always_on_flag_is_validated(tmp_path):
    with pytest.raises(CatalogError, match="alwaysOn"):
        _catalog_with_contact(tmp_path / "x", alwaysOn="yes")
