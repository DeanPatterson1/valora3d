"""Task 88: the fallback (refusing provider) produces a finished T3 script for the grown catalog: new worlds,
weather packages, wind, detected motion asks and phase-5 cameras; studio fallbacks stay byte-identical to
phase 4 (fixtures captured before this task: engine/tests/fallback_phase4_cases.py)."""
import json

import pytest

from engine.checker import check
from engine.director.direction import direction_of, interim_direction, parse_id
from engine.director.fallback import build_fallback
from engine.director.floor import make_viable, script_tier
from engine.director.job import make_job
from engine.tests.fallback_phase4_cases import MODELS, SEEDS, case, path
from engine.tests.test_capabilities import _grown
from engine.tests.test_director_package import _p

pytestmark = pytest.mark.usefixtures("legacy_fps30")
FAMILIES = ("sports_car", "pocket_watch", "mid_century_lounge_chair", "cesium_man")
WORLDS = ("rain_courtyard", "night_street", "golden_field")


def _dir(p, cat, seed=0, **axes):
    base = parse_id(interim_direction(seed, p, cat).id)
    base.update(axes)
    return direction_of(base, "dice")


def _fb(model, prompt="", seed=0, cat=None, **axes):
    cat = cat or _grown()
    p = _p(model)
    job = make_job(prompt, p, cat, seed=seed, direction=_dir(p, cat, seed, **axes), duration=10)
    return build_fallback(job, p, cat), p, cat, job


@pytest.mark.parametrize("model,seed", [(m, s) for m in MODELS for s in SEEDS])
def test_studio_fallback_is_byte_identical_to_phase4(model, seed):
    assert case(model, seed) == json.loads(path(model, seed).read_text(encoding="utf-8"))


@pytest.mark.parametrize("world", WORLDS)
@pytest.mark.parametrize("model", FAMILIES)
def test_new_world_fallback_reaches_t3_or_is_not_viable(world, model):
    cat, p = _grown(), _p(model)
    tone = "na"
    mood = "teal_night" if world == "night_street" else "warm_golden"
    job = make_job("", p, cat, seed=0, direction=_dir(p, cat, world=world, tone=tone, mood=mood), duration=10)
    axes = job.direction.axes()
    viable = make_viable(job, p, cat)(axes)
    try:
        s = build_fallback(job, p, cat)
    except Exception:  # noqa: BLE001 - a non-viable world may not build
        assert not viable
        return
    ok = check(s, p, cat).ok and script_tier(s, p, cat) == "T3"
    assert s["world"]["id"] == world
    assert ok or not viable, (world, model, script_tier(s, p, cat))


@pytest.mark.parametrize("weather,world,expect", [
    ("rain", "night_street", {"rain", "wet_surface"}), ("snow", "golden_field", {"snow"}),
    ("fog", "rain_courtyard", {"ground_fog"}), ("wet", "night_street", {"wet_surface"})])
def test_weather_packages_are_present_and_coupled(weather, world, expect):
    s, p, cat, _ = _fb("sports_car", weather=weather, world=world, tone="na",
                       mood="teal_night" if world == "night_street" else "warm_golden")
    assert expect <= {e["id"] for e in s["effects"]}
    assert check(s, p, cat).ok


def test_rolled_wind_is_written_calm_is_not():
    s, *_ = _fb("sports_car", world="golden_field", tone="na", mood="warm_golden", wind="breeze")
    assert 2.5 <= s["wind"]["params"]["speedMs"] <= 5.0
    calm, *_ = _fb("sports_car", world="golden_field", tone="na", mood="warm_golden")
    assert "wind" not in calm or calm["wind"].get("pinned") == []


def test_a_drive_ask_tracks_the_car_and_ends_settled():
    s, p, cat, _ = _fb("sports_car", "driving down a neon street at night", world="night_street", tone="na",
                       mood="teal_night")
    assert s["subject"]["motion"]["id"] == "drive"
    assert any(sh["camera"]["id"] == "rolling_track" for sh in s["shots"])
    assert s["subject"]["motion"]["params"]["accel"] == "brake_to_stop"
    assert check(s, p, cat).ok and script_tier(s, p, cat) == "T3"


def test_a_vague_prompt_never_invents_motion():
    for w in WORLDS:
        s, *_ = _fb("sports_car", world=w, tone="na", mood="warm_golden")
        assert s["subject"]["motion"]["id"] == "static"


def test_phase5_cameras_never_appear_in_the_studio():
    new = {"reveal_rise", "dutch_hero", "handheld_operator", "profile_slide", "rolling_track"}
    for m in FAMILIES:
        for pace in ("calm", "medium", "hype"):
            s, *_ = _fb(m, pace=pace)
            assert not new & {sh["camera"]["id"] for sh in s["shots"]}


def test_a_motion_the_subject_cannot_do_is_reported():
    s, *_ = _fb("mid_century_lounge_chair", "the chair rolls across the floor")
    assert s["subject"]["motion"]["id"] == "static"
    assert any(u["capability"] == "motion.roll" for u in s.get("unsupported", []))


# --- Task 87 Step 7: rolled weather reaches the floor once the fallback applies its package -----------

def test_a_rain_pin_never_rolls_the_studio():
    cat, p = _grown(), _p("sports_car")
    for seed in range(6):
        job = make_job("rain", p, cat, seed=seed, duration=10)
        assert job.direction.weather == "rain" and job.direction.world != "studio_cyc", job.direction.id


def test_every_rolled_weather_direction_is_viable_and_suits_its_world():
    cat, p = _grown(), _p("sports_car")
    seen = set()
    for seed in range(12):
        job = make_job("", p, cat, seed=seed, duration=10)
        d = job.direction
        assert d.weather == "dry" or d.world != "studio_cyc"
        assert d.weather in (cat.get("world", d.world).get("weathers") or ["dry"])
        if d.source == "dice":
            assert make_viable(job, p, cat)(d.axes())
        seen.add(d.weather)
    assert seen - {"dry"}, "twelve seeds roll some weather"


@pytest.mark.parametrize("world", WORLDS)
@pytest.mark.parametrize("model", ("sports_car", "pocket_watch"))
def test_every_new_world_is_viable_for_the_vehicle_and_product_families(world, model):
    """review chunk7 #7: the reach-T3-or-not-viable test above passes vacuously when nothing is viable. Measured
    2026-09-25: all 12 (world, family) pairs are viable; the vehicle and product families must stay so, and
    their fallback must build in that world at T3."""
    cat, p = _grown(), _p(model)
    mood = "teal_night" if world == "night_street" else "warm_golden"
    job = make_job("", p, cat, seed=0, direction=_dir(p, cat, world=world, tone="na", mood=mood), duration=10)
    assert make_viable(job, p, cat)(job.direction.axes()), (world, model)
    s = build_fallback(job, p, cat)
    assert s["world"]["id"] == world and check(s, p, cat).ok and script_tier(s, p, cat) == "T3"
