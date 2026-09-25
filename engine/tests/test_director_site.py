"""The site gate for ungraded growth blocks (Task 88; owner recommendation: the harness and dice may roll
blocks whose golden is null, the site may not deliver them until graded). apps/web stays not_connected."""
import copy

from engine.catalog import Catalog
from engine.checker import check
from engine.director.llm import FakeProvider
from engine.director.pipeline import direct
from engine.director.site import site_catalog, site_deliverable, site_rulebook, ungraded
from engine.tests.test_director_package import _p
from engine.tests.test_director_pipeline import CAR

BASELINE = {"camera/arc_orbit", "camera/low_hero_push", "camera/macro_detail", "effect/haze_volume",
            "grade/mood_grade", "grade/neutral_film", "lighting/reflection_rig", "lighting/softbox_three_point",
            "motion/play_clip", "motion/static", "world/studio_cyc"}
KINDS = ("world", "lighting", "camera", "motion", "effect", "grade", "field")


def _sel(cat):
    return {f"{k}/{b}" for k in KINDS for b in cat.selectable_ids(k)}


def test_the_harness_catalog_offers_the_ungraded_growth_blocks():
    assert set(ungraded()) <= _sel(Catalog.load())          # the dice and the harness may roll them


def test_the_site_catalog_offers_only_graded_blocks():
    assert _sel(site_catalog()) == BASELINE                  # nothing is graded yet: the phase-4 menu
    graded = {"blocks": {"world/night_street": {"golden": "renders/night_street.png"},
                         "effect/rain": {"golden": None}}}
    sel = _sel(site_catalog(growth=graded))
    assert "world/night_street" in sel and "effect/rain" not in sel


def test_site_deliverable_names_ungraded_blocks_even_coupled_ones():
    s = copy.deepcopy(CAR)
    assert site_deliverable(s) == []
    s["world"] = {"id": "night_street"}
    s["effects"] = [{"id": "wet_surface"}]
    assert site_deliverable(s) == ["effect/wet_surface", "world/night_street"]


def test_the_checkers_still_air_is_not_a_wind_choice():
    s = check({**copy.deepcopy(CAR), "schema": "valora.scene/1", "seed": 1,
               "format": {"aspect": "9:16", "durationS": 10, "fps": 30}}, _p("sports_car"), Catalog.load()).script
    assert s["wind"]["pinned"] == [] and site_deliverable(s) == []
    s["wind"]["pinned"] = ["speedMs"]
    assert site_deliverable(s) == ["field/wind"]


def test_a_site_run_never_delivers_an_ungraded_block(monkeypatch):
    """A rain ask on the site: the refusing provider's fallback stays in the studio and says so."""
    monkeypatch.setenv("VALORA_VARIETY_SECRET", "x" * 40)
    cat = site_catalog()
    for seed in range(4):
        r = direct("rain on the car at night", _p("sports_car"), provider=FakeProvider([{"stop_reason": "refusal"}]),
                   seed=seed, duration=10, catalog=cat)
        assert site_deliverable(r.script) == [], r.script["direction"]
        assert any(u["capability"] == "weather.rain" for u in r.script.get("unsupported", []))


def test_the_site_rulebook_menu_lists_no_ungraded_block():
    from engine.director.rulebook import build_rulebook
    text, _ = site_rulebook()
    full = build_rulebook()
    for ref in ungraded():
        head = f"### {ref}  ("
        assert head in full and head not in text, ref
