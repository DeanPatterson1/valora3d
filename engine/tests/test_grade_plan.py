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
    from engine.grade_plan import PRESETS
    for preset in PRESETS:        # round 6: premium_dark greys its set further (bgSat), like the film's foliage
        p = plan_for(_ref("mood_grade", preset=preset, separation=1.2))
        assert p["subjectSat"] / p["backgroundSat"] == pytest.approx(1.2 / PRESETS[preset].get("bgSat", 1.0))
    assert PRESETS["premium_dark"]["bgSat"] < 1.0


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


# --- realism: the camera's own finish under every grade (render-studio rain film) --------------------------

def test_bloom_only_takes_true_highlights():
    for preset in PRESETS:
        assert plan_for(_ref("mood_grade", preset=preset))["bloom"]["threshold"] == 4.0          # emitters only


def test_camera_finish_is_the_film_recipe_under_any_grade():
    from engine.grade_plan import camera_finished
    for ref in (_ref("mood_grade", preset="clean"), _ref("neutral_film", bloom=0.0)):
        f = camera_finished(plan_for(ref, seed=3), seed=3)
        assert 0.03 <= f["bloom"]["strength"] <= 0.04 and f["bloom"]["threshold"] == 4.0   # LED glow 2-4% (mat-v2)
        assert f["halation"]["strength"] == pytest.approx(0.05) and f["halation"]["threshold"] == 4.0
        assert f["lens"]["distortion"] == pytest.approx(0.006)
        assert f["lens"]["dispersion"] == pytest.approx(0.0015)        # a touch of edge CA (round 9)
        assert 1.0 <= f["edgeSoftnessPx"] <= 2.0                      # a lens softer at its edges
        assert f["grain"]["amount"] == pytest.approx(0.5)            # 0.5-1.0 code values (engine/film_grain.py)


def test_script_finish_only_adds_to_the_camera():
    from engine.grade_plan import camera_finished
    strong = plan_for(_ref("mood_grade", halation=0.4, lensDistortion=0.01, grain=0.8), seed=5)
    f = camera_finished(strong, seed=5)
    assert f["halation"]["strength"] == pytest.approx(0.4) and f["lens"]["distortion"] == pytest.approx(0.01)
    assert f["grain"] == strong["grain"]
    assert f["bloom"]["strength"] == pytest.approx(0.04)          # premium_dark's .15 held to the lens's 4%


def test_camera_finish_leaves_the_script_grade_check_alone():
    identity = _ref("neutral_film", agxLook="none", contrast=1.0, saturation=1.0, bloom=0.0)
    assert not changes_look(identity)                                 # T2-08 judges the script, not the camera


def test_a_low_sun_world_keeps_its_sky_colour_under_premium_dark():
    """Round 8: under a golden / dawn / dusk sun the set is not greyed further (bgSat); other worlds unchanged."""
    from engine.grade_plan import keep_sun_colour, plan_for
    params = {"preset": "premium_dark", "contrast": 1.1, "saturation": 0.8, "separation": 1.12, "effectsScale": 1.0,
              "exposureEv": 0.0, "halation": 0.3, "lensDistortion": 0.0, "grain": 0.0}
    plan = plan_for({"id": "mood_grade", "params": params})
    golden = {"world": {"id": "golden_field", "params": {"timeOfDay": "golden"}}}
    rain = {"world": {"id": "rain_courtyard", "params": {"timeOfDay": "overcast_day"}}}
    kept = keep_sun_colour(plan, golden, params)
    assert kept["backgroundSat"] == pytest.approx(1.12 ** -0.5) and kept["subjectSat"] == plan["subjectSat"]
    assert {k: v for k, v in kept.items() if k != "backgroundSat"} == {k: v for k, v in plan.items() if k != "backgroundSat"}
    assert keep_sun_colour(plan, rain, params) is plan
    warm = {**params, "preset": "warm_golden"}
    assert keep_sun_colour(plan_for({"id": "mood_grade", "params": warm}), golden, warm)["backgroundSat"] == \
        plan_for({"id": "mood_grade", "params": warm})["backgroundSat"]
