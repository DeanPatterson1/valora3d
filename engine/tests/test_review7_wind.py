"""Review chunk 7 #1: wind is written only when field/wind is on the menu and the world is outdoor."""
import copy
import json

import pytest

from engine.catalog import Catalog
from engine.director.adherence import drift, enforce_direction
from engine.director.direction import direction_of
from engine.director.llm import FakeProvider
from engine.director.pipeline import direct
from engine.director.rulebook import EXAMPLES_DIR, example_script
from engine.director.site import site_catalog, site_deliverable
from engine.tests.test_director_package import _p

AX = {"world": "studio_cyc", "mood": "teal_night", "tone": "black", "pace": "calm", "opener": "low_hero_push",
      "weather": "dry", "wind": "calm"}
S = example_script(json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8")))
REFUSE = [{"stop_reason": "refusal"}]


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setenv("VALORA_VARIETY_SECRET", "x" * 40)


def _still(s):
    """No wind the director chose: absent, or the checker's own default for the world (nothing pinned, the world's
    windDefault: 0 in the studio, a 0.8 m/s ambient air outdoors). Since the site offers the outdoor worlds
    (8b5732b) the site may put the watch on the night street, whose unpinned ambient air is no wind choice
    (site._refs does not count it either)."""
    w = s.get("wind")
    if w is None:
        return True
    cat = Catalog.load()
    ambient = (cat.get("world", s["world"]["id"]) or {}).get("windDefault",
                                                             cat.get("field", "wind")["params"]["speedMs"]["default"])
    return w.get("pinned") == [] and w["params"].get("speedMs") == float(ambient)


# ---- #1: wind is written only when field/wind is on the menu AND the world is outdoor ----

def test_site_windy_watch_gets_no_ungraded_wind():
    r = direct("a windy shot of the watch", _p("pocket_watch"), provider=FakeProvider(REFUSE), seed=2,
               duration=10, catalog=site_catalog(Catalog.load()))
    assert _still(r.script), r.script.get("wind")
    assert site_deliverable(r.script) == []
    assert any(u["capability"].startswith("wind.") for u in r.script.get("unsupported", []))


def test_harness_studio_strong_wind_keeps_still_air_and_says_so():
    r = direct("studio, strong wind", _p("sports_car"), provider=FakeProvider(REFUSE), seed=2, duration=10,
               catalog=Catalog.load())
    s = r.script
    assert s["world"]["id"] == "studio_cyc"
    assert _still(s), s.get("wind")
    assert not s["direction"]["id"].endswith(("/breeze", "/windy", "/strong")), s["direction"]
    assert any(u["capability"].startswith("wind.") for u in s.get("unsupported", [])), s.get("unsupported")


def test_enforced_wind_is_not_applied_indoors():
    s = copy.deepcopy(S)
    s.pop("wind", None)
    d = direction_of({**AX, "wind": "breeze"}, "dice", pinned={"wind": "breeze"})
    assert "wind" not in drift(s, d, Catalog.load())
    s, issues = enforce_direction(s, d, Catalog.load(), enforce=True)
    assert "wind" not in s and not any(i.code == "direction_wind_applied" for i in issues)


def test_enforced_wind_is_not_applied_when_the_field_is_off_the_menu():
    cat = site_catalog(Catalog.load())
    s = copy.deepcopy(S)
    s.pop("wind", None)
    s["world"] = {"id": "night_street", "params": {}}
    d = direction_of({**AX, "world": "night_street", "tone": "na", "wind": "breeze"}, "dice",
                     pinned={"wind": "breeze"})
    s, _ = enforce_direction(s, d, cat, enforce=True)
    assert "wind" not in s


def test_enforced_wind_still_applies_outdoors():
    s = copy.deepcopy(S)
    s.pop("wind", None)
    s["world"] = {"id": "night_street", "params": {}}
    d = direction_of({**AX, "world": "night_street", "tone": "na", "wind": "breeze"}, "dice",
                     pinned={"wind": "breeze"})
    s, issues = enforce_direction(s, d, Catalog.load(), enforce=True)
    assert s["wind"]["params"]["speedMs"] > 0
    assert any(i.code == "direction_wind_applied" for i in issues)
