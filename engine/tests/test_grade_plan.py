import pytest
from engine.catalog import Catalog
from engine.grade_plan import PRESETS, changes_look, plan_changes_look, plan_for

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


def test_separation_alone_changes_the_look():
    assert changes_look(_ref("neutral_film", agxLook="none", contrast=1.0, saturation=1.0, bloom=0.0, separation=1.2))


def test_exposure_alone_changes_the_look():
    identity = plan_for(_ref("neutral_film", agxLook="none", contrast=1.0, saturation=1.0, bloom=0.0))
    assert not plan_changes_look(identity)
    assert plan_changes_look({**identity, "exposureEv": 0.5})


# --- Task 61: halation, lens distortion + dispersion, seeded grain (neutral "off" defaults) ---------------

TODAY_KEYS = {"agxLookCandidates", "exposureEv", "lift", "gamma", "gain", "contrast", "saturation", "subjectSat",
              "backgroundSat", "bloom", "halation", "vignette"}


def test_new_params_default_off_on_both_blocks():
    mg, nf = CAT.get("grade", "mood_grade")["params"], CAT.get("grade", "neutral_film")["params"]
    assert (mg["halation"]["min"], mg["halation"]["max"], mg["halation"]["default"]) == (0.0, 1.0, 0.0)
    assert (mg["lensDistortion"]["min"], mg["lensDistortion"]["max"], mg["lensDistortion"]["default"]) == (0.0, 0.02, 0.0)
    for p in (mg, nf):
        assert (p["grain"]["min"], p["grain"]["max"], p["grain"]["default"]) == (0.0, 1.0, 0.0)
    assert mg["preset"]["values"] == ["clean", "premium_dark", "warm_golden", "teal_night", "noir", "vivid"]


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_a_script_without_the_new_params_gets_exactly_todays_plan(preset):
    q = {k: v["default"] for k, v in CAT.get("grade", "mood_grade")["params"].items()
         if k not in ("halation", "lensDistortion", "grain")}
    q["preset"] = preset
    old = plan_for({"id": "mood_grade", "params": q})
    assert set(old) == TODAY_KEYS
    assert plan_for(_ref("mood_grade", preset=preset), seed=7) == old          # defaults (0) = today's plan
    nq = {k: v["default"] for k, v in CAT.get("grade", "neutral_film")["params"].items() if k != "grain"}
    assert plan_for(_ref("neutral_film"), seed=7) == plan_for({"id": "neutral_film", "params": nq})


def test_halation_param_sets_the_strength_and_only_when_positive():
    p = plan_for(_ref("mood_grade", preset="clean", halation=0.3))
    assert p["halation"]["strength"] == pytest.approx(0.3) and p["halation"]["tint"] == (1.0, 0.58, 0.38)
    assert plan_for(_ref("mood_grade", preset="clean"))["halation"] is None


def test_lens_distortion_carries_render_studio_dispersion():
    p = plan_for(_ref("mood_grade", lensDistortion=0.006))
    assert p["lens"]["distortion"] == pytest.approx(0.006)
    assert p["lens"]["dispersion"] == pytest.approx(0.00035, abs=1e-6) and p["lens"]["fit"] is True
    assert "lens" not in plan_for(_ref("mood_grade"))


def test_grain_is_seeded_per_block_and_varies_per_frame():
    from engine.compiler.context import block_seed
    from engine.grade_plan import grain_w
    p = plan_for(_ref("mood_grade", grain=0.5), seed=42)
    g = p["grain"]
    assert g["seed"] == block_seed(42, "grade", "mood_grade") and g["amplitude"] == pytest.approx(0.05)
    assert grain_w(g, 10) == grain_w(g, 10) and grain_w(g, 11) - grain_w(g, 10) == pytest.approx(1.0)
    assert plan_for(_ref("mood_grade", grain=0.5), seed=43)["grain"]["seed"] != g["seed"]
    assert plan_for(_ref("neutral_film", grain=0.2), seed=42)["grain"]["seed"] == block_seed(42, "grade", "neutral_film")
    assert "grain" not in plan_for(_ref("mood_grade"), seed=42)


def test_new_finishing_changes_the_look():
    identity = _ref("neutral_film", agxLook="none", contrast=1.0, saturation=1.0, bloom=0.0)
    assert not changes_look(identity) and changes_look({**identity, "params": {**identity["params"], "grain": 0.3}})
