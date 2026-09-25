"""Review chunk 7 #4: an enforced direction removes model-added weather outside its package."""
import copy
import json

import pytest

from engine.catalog import Catalog
from engine.director.adherence import drift, enforce_direction
from engine.director.direction import direction_of
from engine.director.rulebook import EXAMPLES_DIR, example_script

AX = {"world": "studio_cyc", "mood": "teal_night", "tone": "black", "pace": "calm", "opener": "low_hero_push",
      "weather": "dry", "wind": "calm"}
S = example_script(json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8")))


# ---- #4: an enforced direction removes model-added weather outside its package ----


def _rainy(world="rain_courtyard"):
    s = copy.deepcopy(S)
    s["world"] = {"id": world, "params": {}}
    s["effects"] = [{"id": "haze_volume", "params": {}}, {"id": "rain", "params": {}},
                    {"id": "wet_surface", "params": {}}]
    return s


def _dir(weather, pinned=None):
    return direction_of({**AX, "world": "rain_courtyard", "tone": "na", "weather": weather}, "dice",
                        pinned=pinned or {})


def test_pinned_dry_removes_model_rain_and_drift_flags_it():
    s, d = _rainy(), _dir("dry", {"weather": "dry"})
    assert "weather" in drift(s, d, Catalog.load())
    s, issues = enforce_direction(s, d, Catalog.load(), enforce=False)
    ids = [e["id"] for e in s["effects"]]
    assert ids == ["haze_volume"], ids
    assert any(i.code == "direction_weather_applied" and i.severity == "repaired" for i in issues)


def test_rolled_snow_on_a_vague_prompt_replaces_model_rain():
    s, d = _rainy(), _dir("snow")
    s, _ = enforce_direction(s, d, Catalog.load(), enforce=True)
    ids = {e["id"] for e in s["effects"]}
    assert "rain" not in ids and "wet_surface" not in ids and "haze_volume" in ids


def test_rolled_rain_keeps_its_own_couplings():
    s, d = _rainy(), _dir("rain")
    assert "weather" not in drift(s, d, Catalog.load())
    s, issues = enforce_direction(s, d, Catalog.load(), enforce=True)
    assert {"rain", "wet_surface"} <= {e["id"] for e in s["effects"]}
    assert not any(i.code == "direction_weather_applied" for i in issues)


def test_unpinned_weather_on_a_long_prompt_is_only_drift():
    s, d = _rainy(), _dir("dry")
    s, issues = enforce_direction(s, d, Catalog.load(), enforce=False)
    assert "rain" in {e["id"] for e in s["effects"]}
    assert any(i.code == "direction_drift" and i.path == "weather" for i in issues)
