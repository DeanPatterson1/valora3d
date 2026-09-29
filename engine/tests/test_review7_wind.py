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
    """No wind the director chose: absent, or the checker's own still-air default (speed 0, nothing pinned)."""
    w = s.get("wind")
    return w is None or (w["params"].get("speedMs") == 0 and w.get("pinned") == [])


def _site_wind(s):
    """The site's wind: exactly the world's graded wind (unpinned), or still air where none is graded."""
    from engine.director.site import graded_wind
    w = s.get("wind")
    g = graded_wind(s["world"]["id"])
    if g is None:
        return _still(s)
    return w is not None and w["params"] == g and w.get("pinned") == []


# ---- #1: wind is written only when field/wind is on the menu AND the world is outdoor ----

def test_site_windy_watch_gets_no_ungraded_wind():
    r = direct("a windy shot of the watch", _p("pocket_watch"), provider=FakeProvider(REFUSE), seed=2,
               duration=10, catalog=site_catalog(Catalog.load()))
    assert _site_wind(r.script), r.script.get("wind")
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


# ---- owner decision 2026-09-29: a site job in an outdoor world gets EXACTLY the wind the graded renders used ----

GRADED = {"speedMs": 3.0, "directionDeg": 256.0, "gustiness": 0.3, "turbulence": 0.2}
OUTDOOR = ["rain_courtyard", "night_street", "golden_field"]


def _check_in(world, seed=1, catalog=None, wind=None):
    from engine.checker import check
    s = {**copy.deepcopy(S), "world": {"id": world, "params": {}}, "seed": seed}
    s.pop("wind", None)
    if wind is not None:
        s["wind"] = wind
    return check(s, _p("sports_car"), catalog or site_catalog(Catalog.load())).script


@pytest.mark.parametrize("world", OUTDOOR)
def test_site_wind_is_exactly_the_graded_wind_never_default_never_seeded(world):
    cat = site_catalog(Catalog.load())
    assert cat.get("world", world)["windDefault"] != GRADED["speedMs"]
    for seed in range(8):
        s = _check_in(world, seed, cat)
        assert s["wind"]["params"] == GRADED and s["wind"]["pinned"] == [], (world, seed)
        assert site_deliverable(s) == []


def test_site_studio_stays_still_air():
    s = _check_in("studio_cyc")
    assert s["wind"]["params"]["speedMs"] == 0 and site_deliverable(s) == []


def test_the_full_menu_still_uses_the_world_default_not_the_graded_wind():
    s = _check_in("golden_field", catalog=Catalog.load())
    assert s["wind"]["params"]["speedMs"] == 0.8


@pytest.mark.parametrize("world", OUTDOOR)
@pytest.mark.parametrize("other", [{"speedMs": 6.0}, {"speedMs": 3.0, "directionDeg": 10.0}, {"gustiness": 0.9},
                                   {"turbulence": 0.0}, {"speedMs": 0.0}, {"speedMs": 0.8}])
def test_any_other_wind_on_the_site_fails_the_gate(world, other):
    s = _check_in(world, wind={"id": "wind", "params": other})
    assert site_deliverable(s) == ["field/wind"], s["wind"]
    s2 = copy.deepcopy(s)
    s2["wind"] = {"id": "wind", "params": {**GRADED, **other}, "pinned": []}     # an unpinned drifted wind too
    assert site_deliverable(s2) == ["field/wind"]


def test_a_wind_on_the_still_air_studio_fails_the_gate():
    s = _check_in("studio_cyc", wind={"id": "wind", "params": {"speedMs": 3.0}})
    assert site_deliverable(s) == ["field/wind"]
    s["wind"] = {"id": "wind", "params": {"speedMs": 3.0}, "pinned": []}
    assert site_deliverable(s) == ["field/wind"]


def test_a_bad_graded_wind_fails_the_catalog(tmp_path):
    from engine.catalog import CatalogError
    import shutil
    root = tmp_path / "blocks"
    shutil.copytree(Catalog.load()._root, root)
    p = root / "world" / "golden_field" / "block.json"
    m = json.loads(p.read_text(encoding="utf-8"))
    m["gradedWind"]["speedMs"] = 30.0
    p.write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(CatalogError, match="gradedWind"):
        Catalog.load(root)
