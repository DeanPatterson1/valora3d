"""Task 87: weather and wind roll through each world's `weathers`, dice.json's implausible pairs and the quality
floor (make_viable builds the fallback WITH the package); pins are negation-aware; adherence inserts the rolled
package on vague prompts and a pinned or rolled wind beats the model's speed."""
import copy

from engine.catalog import Catalog
from engine.director.adherence import enforce_direction
from engine.director.axes import DICE, axis_values, compatible, weather_package, wind_speed
from engine.director.dice import candidates
from engine.director.direction import direction_of, interim_direction, parse_id
from engine.director.pins import read_direction_pins
from engine.tests.test_capabilities import _grown
from engine.tests.test_director_package import _p

FMT = {"aspect": "9:16", "durationS": 10, "fps": 30}


def test_weather_and_wind_are_now_rollable():
    v = axis_values(_p("sports_car"), Catalog.load(), FMT)
    assert set(v["weather"]) == {"dry", "wet", "rain", "snow", "fog"} and set(v["wind"]) == {"calm", "breeze", "windy"}
    assert "worlds" not in DICE                                 # the Task 63->88 world filter is gone


def test_weather_must_suit_the_world():
    cat = Catalog.load()
    ok = lambda **a: compatible({"mood": "clean", "tone": "grey", "wind": "calm", **a}, catalog=cat)  # noqa: E731
    assert not ok(world="studio_cyc", weather="rain")
    assert ok(world="studio_cyc", weather="dry")
    assert not ok(world="studio_cyc", weather="dry", wind="breeze")     # TG-24: still air indoors
    assert compatible({"world": "night_street", "weather": "rain", "mood": "teal_night", "tone": "na", "wind": "breeze"},
                      catalog=cat)
    assert not compatible({"world": "golden_field", "weather": "rain", "mood": "warm_golden", "tone": "na",
                           "wind": "calm"}, catalog=cat)                 # rain on the field: excluded (owner rec.)
    assert not compatible({"world": "night_street", "weather": "fog", "mood": "teal_night", "tone": "na",
                           "wind": "windy"}, catalog=cat)                # implausible pair


def test_a_pinned_tone_still_obeys_the_world_weather():
    cat = _grown()
    vals = axis_values(_p("sports_car"), cat, FMT)
    for c in candidates(vals, {"tone": "black"}, catalog=cat):
        assert c["world"] == "studio_cyc" and c["weather"] == "dry"


def test_packages_map_to_effects():
    assert weather_package("dry") == []
    assert [e["id"] for e in weather_package("rain")] == ["rain"]          # the checker couples wet+droplets
    assert [e["id"] for e in weather_package("wet")] == ["wet_surface"]
    assert [e["id"] for e in weather_package("fog")] == ["ground_fog"]
    assert [e["id"] for e in weather_package("snow")] == ["snow"]


def test_wind_speed_mapping_calm_is_the_world_default():
    cat = Catalog.load()
    assert wind_speed("calm", cat.get("world", "golden_field"), seed=1) == 0.8
    assert wind_speed("calm", cat.get("world", "studio_cyc"), seed=1) == 0.0
    for s in range(20):
        assert 2.5 <= wind_speed("breeze", cat.get("world", "golden_field"), seed=s) <= 5.0
        assert 7.0 <= wind_speed("windy", cat.get("world", "golden_field"), seed=s) <= 11.0
    assert wind_speed("windy", None, 3) == wind_speed("windy", None, 3)


def test_weather_pins_are_negation_aware():
    assert read_direction_pins("rainy night")["weather"] == "rain"
    assert read_direction_pins("no rain, sunny")["weather"] == "dry"
    assert read_direction_pins("after the rain")["weather"] == "wet"
    assert read_direction_pins("light drizzle")["weather"] == "rain"
    assert read_direction_pins("a snowy morning")["weather"] == "snow"
    assert "weather" not in read_direction_pins("snow white backdrop")
    assert read_direction_pins("misty field")["weather"] == "fog"
    assert read_direction_pins("gale force")["wind"] == "windy"
    assert read_direction_pins("a gentle breeze")["wind"] == "breeze"
    assert read_direction_pins("depth of field").get("world") != "golden_field"


def _script(world="night_street"):
    from engine.tests.test_director_pipeline import CAR
    s = copy.deepcopy(CAR)
    s.update(world={"id": world, "params": {}}, seed=5, format=dict(FMT))
    s.setdefault("effects", [])
    return s


def test_vague_prompt_inserts_the_rolled_package_and_wind():
    cat, p = _grown(), _p("sports_car")
    base = parse_id(interim_direction(0, p, cat).id)
    d = direction_of({**base, "world": "night_street", "tone": "na", "weather": "rain", "wind": "breeze"}, "dice")
    s, issues = enforce_direction(_script(), d, cat, enforce=True)
    codes = {i.code for i in issues}
    assert "rain" in {e["id"] for e in s["effects"]} and "direction_weather_applied" in codes
    assert 2.5 <= s["wind"]["params"]["speedMs"] <= 5.0 and "direction_wind_applied" in codes


def test_a_rolled_wind_beats_the_models_speed_on_vague_prompts_only():
    cat, p = _grown(), _p("sports_car")
    base = parse_id(interim_direction(0, p, cat).id)
    d = direction_of({**base, "world": "night_street", "tone": "na", "wind": "windy"}, "dice")
    s = _script()
    s["wind"] = {"id": "wind", "params": {"speedMs": 1.0}}
    vague, _ = enforce_direction(copy.deepcopy(s), d, cat, enforce=True)
    assert vague["wind"]["params"]["speedMs"] >= 7.0
    long_, issues = enforce_direction(copy.deepcopy(s), d, cat, enforce=False)
    assert long_["wind"]["params"]["speedMs"] == 1.0 and "direction_wind_applied" not in {i.code for i in issues}
    pinned = direction_of({**base, "world": "night_street", "tone": "na", "wind": "windy"}, "dice", pinned=["wind"])
    long_pin, _ = enforce_direction(copy.deepcopy(s), pinned, cat, enforce=False)
    assert long_pin["wind"]["params"]["speedMs"] >= 7.0


def test_long_prompts_only_measure_weather_drift():
    cat, p = _grown(), _p("sports_car")
    base = parse_id(interim_direction(0, p, cat).id)
    d = direction_of({**base, "world": "night_street", "tone": "na", "weather": "rain"}, "dice")
    s, issues = enforce_direction(_script(), d, cat, enforce=False)
    assert "rain" not in {e["id"] for e in s["effects"]}
    assert any(i.code == "direction_drift" and i.path == "weather" for i in issues)
