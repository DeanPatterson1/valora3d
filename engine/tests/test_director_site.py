"""The site gate for ungraded growth blocks (Task 88; owner recommendation: the harness and dice may roll
blocks whose golden is null, the site may not deliver them until graded). apps/web stays not_connected."""
import copy

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.director.llm import FakeProvider
from engine.director.pipeline import direct
from engine.director.site import load_growth, site_catalog, site_deliverable, site_rulebook, ungraded
from engine.tests.test_director_package import _p
from engine.tests.test_director_pipeline import CAR

BASELINE = {"camera/arc_orbit", "camera/low_hero_push", "camera/macro_detail", "effect/haze_volume",
            "grade/mood_grade", "grade/neutral_film", "lighting/reflection_rig", "lighting/softbox_three_point",
            "motion/play_clip", "motion/static", "world/studio_cyc"}
# Owner grades 2026-09-27 (realism round 16 "all good now"; the golden field from round 15): the blocks of
# those graded renders' scripts. field/wind is not among them (the graded scripts' breeze was not judged).
GRADED = {"world/rain_courtyard", "world/night_street", "world/golden_field", "effect/rain", "effect/wet_surface",
          "effect/droplets", "lighting/hdri_only", "lighting/hard_sun"}
KINDS = ("world", "lighting", "camera", "motion", "effect", "grade", "field")


def _sel(cat):
    return {f"{k}/{b}" for k in KINDS for b in cat.selectable_ids(k)}


def test_the_harness_catalog_offers_the_ungraded_growth_blocks():
    assert set(ungraded()) <= _sel(Catalog.load())          # the dice and the harness may roll them


def test_the_site_catalog_offers_only_graded_blocks():
    # the phase-4 menu plus the owner-graded blocks; practicals_only is harness-off but lights the graded night street
    assert _sel(site_catalog()) == BASELINE | GRADED | {"lighting/practicals_only"}
    graded = {"blocks": {"world/night_street": {"golden": "renders/night_street.png"},
                         "effect/rain": {"golden": None}}}
    sel = _sel(site_catalog(growth=graded))
    assert "world/night_street" in sel and "effect/rain" not in sel


def test_the_site_offers_the_three_owner_graded_worlds():
    assert set(site_catalog().selectable_ids("world")) == {"studio_cyc", "rain_courtyard", "night_street",
                                                           "golden_field"}


def test_every_golden_is_a_graded_still_path_and_wind_stays_ungraded():
    growth = load_growth()
    goldens = {ref: e["golden"] for ref, e in growth["blocks"].items() if e.get("golden")}
    assert set(goldens) == GRADED
    for ref, path in goldens.items():
        assert path.startswith("harness/out/look/real_r1") and path.endswith(".png") and "\\" not in path, ref
    assert "field/wind" in ungraded()


@pytest.mark.parametrize("world", ["rain_courtyard", "night_street", "golden_field"])
def test_a_site_run_in_each_graded_world_is_deliverable(monkeypatch, world):
    """The site pins a world by avoiding the others; the dice never roll an ungraded weather (snow, fog) or
    wind back in through a weather package (axes.weather_fits_world)."""
    monkeypatch.setenv("VALORA_VARIETY_SECRET", "x" * 40)
    cat = site_catalog()
    others = [w for w in cat.selectable_ids("world") if w != world]
    for seed in range(6):
        r = direct("", _p("sports_car"), provider=FakeProvider([{"stop_reason": "refusal"}]), seed=seed, catalog=cat,
                   rulebook=site_rulebook(cat), avoid={"world": others})
        assert r.script["world"]["id"] == world and site_deliverable(r.script) == [], (seed, r.script["direction"])


def test_site_deliverable_names_ungraded_blocks_even_coupled_ones():
    s = copy.deepcopy(CAR)
    assert site_deliverable(s) == []
    s["world"] = {"id": "golden_field"}
    s["effects"] = [{"id": "snow"}, {"id": "ground_fog"}]
    assert site_deliverable(s) == ["effect/ground_fog", "effect/snow"]


def test_the_checkers_still_air_is_not_a_wind_choice():
    s = check({**copy.deepcopy(CAR), "schema": "valora.scene/1", "seed": 1,
               "format": {"aspect": "9:16", "durationS": 10, "fps": 30}}, _p("sports_car"), Catalog.load()).script
    assert s["wind"]["pinned"] == [] and site_deliverable(s) == []
    s["wind"]["pinned"] = ["speedMs"]
    assert site_deliverable(s) == ["field/wind"]


def test_a_site_run_never_delivers_an_ungraded_block(monkeypatch):
    """A snow ask on the site (snow is ungraded): the refusing provider's fallback never delivers it and says so."""
    monkeypatch.setenv("VALORA_VARIETY_SECRET", "x" * 40)
    cat = site_catalog()
    for seed in range(4):
        r = direct("snow on the car", _p("sports_car"), provider=FakeProvider([{"stop_reason": "refusal"}]),
                   seed=seed, duration=10, catalog=cat)
        assert site_deliverable(r.script) == [], r.script["direction"]
        assert any(u["capability"] == "weather.snow" for u in r.script.get("unsupported", []))


def test_the_site_rulebook_menu_lists_no_ungraded_block():
    from engine.director.rulebook import build_rulebook
    text, _ = site_rulebook()
    full = build_rulebook()
    for ref in ungraded():
        head = f"### {ref}  ("
        assert head in full and head not in text, ref


def test_site_catalog_never_mutates_the_catalog_it_is_given():
    # review chunk7 #5: a shared harness/server catalog must keep every growth block on its menu
    cat = Catalog.load()
    before = _sel(cat)
    site = site_catalog(cat)
    assert _sel(cat) == before and set(ungraded()) <= _sel(cat)
    assert _sel(site) == BASELINE | GRADED | {"lighting/practicals_only"} and site is not cat


def test_an_ask_for_an_ungraded_wind_does_not_push_the_pick_out_of_the_chosen_world(monkeypatch):
    """'after a storm' asks for rain (graded) and strong wind (field/wind is not): the wind pin is dropped and
    reported, the courtyard and its rain stay (the site E2E of 2026-09-28 landed in the studio before)."""
    monkeypatch.setenv("VALORA_VARIETY_SECRET", "x" * 40)
    cat = site_catalog()
    others = [w for w in cat.selectable_ids("world") if w != "rain_courtyard"]
    for seed in range(3):
        r = direct("after a storm", _p("sports_car"), provider=FakeProvider([{"stop_reason": "refusal"}]), seed=seed,
                   catalog=cat, rulebook=site_rulebook(cat), avoid={"world": others})
        s = r.script
        assert s["world"]["id"] == "rain_courtyard" and site_deliverable(s) == [], s["direction"]
        assert "rain" in {e["id"] for e in s.get("effects", [])}
        assert any(u["capability"] == "wind.strong" for u in s.get("unsupported", []))


GRADED_LIGHT = {"rain_courtyard": "hdri_only", "night_street": "practicals_only", "golden_field": "hard_sun"}


@pytest.mark.parametrize("world,aspect", [("rain_courtyard", "9:16"), ("rain_courtyard", "16:9"),
                                          ("night_street", "9:16"), ("golden_field", "16:9")])
def test_the_site_fallback_lights_each_world_as_the_owner_graded_it(monkeypatch, world, aspect):
    """Without an API key the fallback lit every site world with reflection_rig (a glossy car picks it wherever the
    world pairs it); the site's fallback uses the graded script's lighting (Render Studio e2e 2026-09-28)."""
    monkeypatch.setenv("VALORA_VARIETY_SECRET", "x" * 40)
    from engine import site_job
    res, _ = site_job.direct_site("", _p("sports_car"), world=world, aspect=aspect, seed=3,
                                  provider=FakeProvider([{"stop_reason": "refusal"}]))
    assert res.source.startswith("fallback") and res.script["lighting"]["id"] == GRADED_LIGHT[world]
    assert site_deliverable(res.script) == []


def test_the_harness_fallback_keeps_its_own_lighting(monkeypatch):
    """siteLighting lives only on the site catalog: the harness (and the frozen baselines) are unchanged."""
    monkeypatch.setenv("VALORA_VARIETY_SECRET", "x" * 40)
    cat = Catalog.load()
    assert all("siteLighting" not in (cat.get("world", w) or {}) for w in GRADED_LIGHT)
    assert not cat.get("lighting", "practicals_only").get("directorSelectable", True)
    site = site_catalog()
    assert {w: site.get("world", w)["siteLighting"]["id"] for w in GRADED_LIGHT} == GRADED_LIGHT


def test_site_lighting_matches_the_graded_scripts():
    """The siteLighting record is the lighting (id and params) of the script behind each world's golden still."""
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    growth = load_growth()
    for world, light in growth["siteLighting"].items():
        if world == "note":
            continue
        golden = growth["blocks"][f"world/{world}"]["golden"]
        job = root / Path(golden).parents[1] / "job.json"
        if not job.is_file():
            pytest.skip(f"graded render not on this machine: {job}")
        assert json.loads(job.read_text(encoding="utf-8"))["script"]["lighting"] == light, world
