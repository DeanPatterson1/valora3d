import pytest
from engine.catalog import Catalog
from engine.grade_plan import PRESETS, changes_look, plan_for

CAT = Catalog.load()


def _ref(bid, **params):
    return {"id": bid, "params": {**{k: v["default"] for k, v in CAT.get("grade", bid)["params"].items()}, **params}}


def test_mood_grade_offers_six_presets_matching_the_plan():
    assert set(CAT.get("grade", "mood_grade")["params"]["preset"]["values"]) == set(PRESETS) and len(PRESETS) == 6


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_every_preset_builds_a_complete_plan(preset):
    p = plan_for(_ref("mood_grade", preset=preset))
    assert set(p) == {"agxLookCandidates", "exposureEv", "lift", "gamma", "gain", "contrast",
                      "saturation", "subjectSat", "backgroundSat", "bloom", "halation", "vignette"}
    assert p["agxLookCandidates"][-1] == "None"  # always a safe fallback


def test_separation_splits_saturation_between_subject_and_background():
    p = plan_for(_ref("mood_grade", separation=1.2))
    assert p["subjectSat"] / p["backgroundSat"] == pytest.approx(1.2)


def test_effects_scale_zero_turns_bloom_halation_vignette_off():
    p = plan_for(_ref("mood_grade", preset="teal_night", effectsScale=0.0))
    assert p["bloom"]["strength"] == 0 and p["halation"] is None and p["vignette"] == 0


def test_neutral_film_is_the_clean_preset():
    p = plan_for(_ref("neutral_film", bloom=0.3))
    assert p["bloom"]["strength"] == 0.3 and p["agxLookCandidates"][0] == "AgX - Base Contrast"


def test_changes_look():
    assert changes_look(_ref("mood_grade", preset="noir"))
    assert not changes_look(_ref("neutral_film", agxLook="none", contrast=1.0, saturation=1.0, bloom=0.0))
