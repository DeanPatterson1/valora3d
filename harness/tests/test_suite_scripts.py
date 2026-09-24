"""Every suite script must pass the checker on every suite model (no Blender). Catches fixtures
that only work on one subject."""
import json
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.craft_rules import score_script
from engine.profile import SubjectProfile

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "harness" / "suites" / "v0"
SPEC = json.loads((SUITE / "suite.json").read_text())
CAT = Catalog.load()


def _profile(m):
    return SubjectProfile.from_dict(json.loads((ROOT / SPEC["profiles"] / f"{m}.json").read_text()))


def _script(name):
    return json.loads((SUITE / f"{name}.json").read_text())


@pytest.mark.parametrize("model", SPEC["models"])
@pytest.mark.parametrize("name", SPEC["scripts"])
def test_suite_script_checks_on_every_model(model, name):
    r = check(_script(name), _profile(model), CAT)
    assert r.ok, [i.to_dict() for i in r.issues if i.severity == "error"]


@pytest.mark.parametrize("model", SPEC["models"])
def test_t1_control_really_is_the_flat_t1_signature(model):
    r = check(_script("t1_control"), _profile(model), CAT)
    items = {i.id: i.status for i in score_script(r.script, _profile(model), CAT)}
    assert items["T1-X3"] == "fail" and items["T2-08"] == "fail"
