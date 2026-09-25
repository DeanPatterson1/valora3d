import pytest

from engine.catalog import Catalog
from engine.tests.test_director_package import _p
from harness.director_eval import expected_unsupported, load_prompt_set, markers_for


def _has_play_clip():
    return "play_clip" in Catalog.load().selectable_ids("motion")


def test_prompt_set_covers_spec_9_and_unsupported_cases():
    prompts, sets = load_prompt_set("v1")
    ids = {p["id"] for p in prompts}
    assert {"empty", "cool", "ad", "luxury", "rainy_night"} <= ids                 # spec §9 list
    assert {"add_rain", "liquid", "drive", "walks", "sunset_music"} <= ids          # coordinator 2026-09-24
    assert {"markers_details", "markers_hostile"} <= ids and set(sets) == {"details2", "hostile"}
    assert len(ids) == len(prompts) == 15


def test_markers_are_built_on_the_subject_surface():
    prompts, sets = load_prompt_set("v1")
    watch = _p("pocket_watch")
    ms = markers_for(sets["details2"], watch)
    assert [m["id"] for m in ms] == ["m0", "m1"] and ms[0]["anchor"]["point"] == watch.detailPoints[0]["point"]
    assert ms[1]["timeS"] == 6.0 and "timeS" not in ms[0]


def test_expectations_depend_on_the_model():
    prompts, _ = load_prompt_set("v1")
    walks = next(p for p in prompts if p["id"] == "walks")
    assert expected_unsupported(walks, _p("pocket_watch")) == ["motion.character_clip"]
    liquid = next(p for p in prompts if p["id"] == "liquid")
    # physics hand-off (plan 2026-09-25): the finer BLOCKS.md tag is reported alongside sim.liquid
    assert expected_unsupported(liquid, _p("pocket_watch")) == ["sim.liquid", "liquid.run_down"]
    assert expected_unsupported(next(p for p in prompts if p["id"] == "cool"), _p("pocket_watch")) is None


def test_walks_on_an_animated_model_expects_nothing_unsupported():
    assert _has_play_clip()
    prompts, _ = load_prompt_set("v1")
    walks = next(p for p in prompts if p["id"] == "walks")
    assert expected_unsupported(walks, _p("cesium_man")) == []
