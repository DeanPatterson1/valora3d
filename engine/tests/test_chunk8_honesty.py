"""Task 90 offline sweep findings: a deliverable ask the finished script does not deliver is reported, never
silently dropped: a lighting ask the script's light does not give, and lens drops without rain."""
from engine.catalog import Catalog
from engine.director.capabilities import detect, finish_unsupported
from engine.tests.test_director_package import _p


def _script(world, light, effects=()):
    return {"world": {"id": world, "params": {}}, "lighting": {"id": light, "params": {}},
            "effects": [{"id": e, "params": {}} for e in effects], "shots": [], "assumptions": ["x"],
            "subject": {"motion": {"id": "static", "params": {}}}}


def _tags(prompt, s):
    cat, p = Catalog.load(), _p("cesium_man")
    return {u["capability"]: u["note"] for u in finish_unsupported(s, detect(prompt), cat, p).get("unsupported", [])}


def test_a_sun_ask_under_another_light_is_reported():
    got = _tags("sunset on the beach", _script("rain_courtyard", "hdri_only"))
    assert "lighting.sun" in got and "sun" in got["lighting.sun"].lower()
    assert "lighting.sun" not in _tags("sunset", _script("golden_field", "hard_sun"))


def test_lens_drops_without_rain_are_reported_with_the_source_note():
    got = _tags("water on the lens, sunny day", _script("night_street", "rim_neon", ["haze_volume"]))
    assert "camera.lens_drops" in got and "rain" in got["camera.lens_drops"].lower()
    assert "camera.lens_drops" not in _tags("rain on the lens", _script("night_street", "rim_neon",
                                                                          ["rain", "lens_drops"]))
