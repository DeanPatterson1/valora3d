"""The fallback director replays the owner-graded look for each graded world (engine/director/graded.py):
world / lighting / effects / grade params equal the graded script's, the clip opens on the graded hero shot, the
site gate and the checker pass, on cars and on small products, at every seed."""
import json
from pathlib import Path

import pytest

from engine.checker import check
from engine.director import graded_recipes
from engine.director.direction import direction_of, interim_direction, parse_id
from engine.director.fallback import build_fallback
from engine.director.floor import script_tier
from engine.director.job import make_job
from engine.director.site import site_catalog, site_deliverable
from engine.tests.test_director_package import _p

pytestmark = pytest.mark.usefixtures("legacy_fps30")
WORLDS = ("rain_courtyard", "golden_field", "night_street")
SUBJECTS = ("sports_car", "sneaker", "pocket_watch")
RECIPES = graded_recipes.load()


def _job(cat, p, world, seed, duration=10, aspect=None, prompt="", **axes):
    base = parse_id(interim_direction(seed, p, cat).id)
    base.update(world=world, tone="na", **{**graded_recipes.direction_axes(RECIPES[world]), **axes})
    job = make_job(prompt, p, cat, seed=seed, direction=direction_of(base, "dice"), duration=duration)
    if aspect:
        job.fmt["aspect"] = aspect
    return job


def _key(s, k):
    return json.dumps(s[k], sort_keys=True)


def test_recipes_cover_the_three_graded_worlds_and_name_their_sources():
    assert set(RECIPES) == set(WORLDS)
    for w, r in RECIPES.items():
        assert r["source"].startswith("harness/out/look/") and r["source"].endswith("/job.json")
        assert r["world"]["id"] == w and r["shots"][0]["camera"]["id"] == "low_hero_push"
        assert r["shots"][0]["camera"]["params"]["lensMm"] == 40


def test_recipes_match_their_graded_sources_when_present():
    root = graded_recipes.DEFAULT_ROOT
    if not all((root / rel).exists() for rel in graded_recipes.SOURCES):
        pytest.skip("graded harness outputs are not in this checkout")
    assert graded_recipes.extract(root)["worlds"] == RECIPES


@pytest.mark.parametrize("seed", (0, 1, 2, 7))
@pytest.mark.parametrize("subject", SUBJECTS)
@pytest.mark.parametrize("world", WORLDS)
def test_fallback_reproduces_the_graded_look(world, subject, seed):
    cat, p = site_catalog(), _p(subject)
    r = RECIPES[world]
    s = build_fallback(_job(cat, p, world, seed), p, cat)
    for k in ("world", "lighting", "grade"):
        assert s[k] == r[k], k
    assert all(e in s["effects"] for e in r["effects"])     # every graded effect verbatim (+ T2-07's haze, courtyard)
    assert script_tier(s, p, cat) == "T3"                    # so the floor keeps it (never swapped for the studio)
    hero = s["shots"][0]
    assert hero["camera"]["id"] == "low_hero_push" and hero["camera"]["params"]["lensMm"] == 40
    assert hero["camera"]["params"]["fstop"] == r["shots"][0]["camera"]["params"]["fstop"]
    assert s["shots"][-1]["camera"]["id"] == r["shots"][-1]["camera"]["id"]
    assert s["shots"][-1]["camera"]["params"]["lensMm"] == r["shots"][-1]["camera"]["params"]["lensMm"]
    assert site_deliverable(s) == []
    assert check(s, p, cat).ok


@pytest.mark.parametrize("world", WORLDS)
def test_the_graded_look_does_not_vary_with_the_seed(world):
    cat, p = site_catalog(), _p("sports_car")
    outs = [build_fallback(_job(cat, p, world, sd), p, cat) for sd in (0, 3, 9)]
    for k in ("world", "lighting", "grade", "effects"):
        assert len({_key(o, k) for o in outs}) == 1, k
    assert len({json.dumps([sh["camera"] for sh in o["shots"]], sort_keys=True) for o in outs}) == 1


@pytest.mark.parametrize("duration", (5, 6, 7, 8, 9, 10, 11, 12, 15))
@pytest.mark.parametrize("world", WORLDS)
def test_shot_list_is_trimmed_or_scaled_to_the_duration(world, duration):
    cat, p = site_catalog(), _p("sports_car")
    s = build_fallback(_job(cat, p, world, 0, duration=duration), p, cat)
    assert s["format"]["durationS"] == duration
    assert s["shots"][0]["camera"]["id"] == "low_hero_push" and s["shots"][0]["endS"] <= 2.5
    assert s["shots"][-1]["endS"] == duration and site_deliverable(s) == [] and check(s, p, cat).ok
    assert s["world"] == RECIPES[world]["world"] and s["grade"] == RECIPES[world]["grade"]
    assert script_tier(s, p, cat) == "T3" and any("graded" in a for a in s["assumptions"])


@pytest.mark.parametrize("subject", ("sports_car", "sneaker"))
@pytest.mark.parametrize("world", WORLDS)
def test_landscape_frames_pass_too(world, subject):
    cat, p = site_catalog(), _p(subject)
    s = build_fallback(_job(cat, p, world, 0, aspect="16:9"), p, cat)
    assert s["shots"][0]["camera"]["id"] == "low_hero_push" and check(s, p, cat).ok


def test_the_studio_is_unchanged():
    cat, p = site_catalog(), _p("sports_car")
    job = make_job("", p, cat, seed=0, direction=direction_of(parse_id(interim_direction(0, p, cat).id), "dice"),
                   duration=10)
    s = build_fallback(job, p, cat)
    assert s["world"]["id"] == "studio_cyc" and not any("graded" in a for a in s["assumptions"])


def test_the_phase3_default_never_takes_the_graded_path():
    from engine.director.floor import phase3_default
    cat, p = site_catalog(), _p("sports_car")
    job = _job(cat, p, "rain_courtyard", 0)
    assert phase3_default(job, p, cat)["world"]["id"] == "studio_cyc"


def test_the_graded_wind_is_the_only_wind():
    cat, p = site_catalog(), _p("sports_car")
    s = build_fallback(_job(cat, p, "golden_field", 0), p, cat)
    from engine.director.site import graded_wind
    assert site_deliverable(s) == [] and {k: s["wind"]["params"][k] for k in graded_wind("golden_field")} == graded_wind(
        "golden_field")
    assert Path(graded_recipes.DATA).exists()


@pytest.mark.parametrize("world", WORLDS)
def test_direct_without_a_key_delivers_the_graded_look(monkeypatch, world):
    """End to end (no Anthropic key: a refusing provider): the site path keeps the graded recipe through the floor."""
    from engine.director.llm import FakeProvider
    from engine.director.pipeline import direct
    from engine.director.site import site_rulebook
    monkeypatch.setenv("VALORA_VARIETY_SECRET", "x" * 40)
    cat = site_catalog()
    others = [w for w in cat.selectable_ids("world") if w != world]
    for seed in range(3):
        r = direct("", _p("sports_car"), provider=FakeProvider([{"stop_reason": "refusal"}]), seed=seed, catalog=cat,
                   rulebook=site_rulebook(cat), avoid={"world": others})
        s = r.script
        assert s["world"] == RECIPES[world]["world"] and s["grade"] == RECIPES[world]["grade"], seed
        assert s["lighting"] == RECIPES[world]["lighting"] and s["shots"][0]["camera"]["id"] == "low_hero_push"
        assert site_deliverable(s) == []
