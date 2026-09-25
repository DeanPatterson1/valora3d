"""Task 69: script-level weather items and the physics section's weather entries."""
import copy
import json
from pathlib import Path

from engine.catalog import Catalog
from engine.checker import check
from engine.tests.test_director_package import _p
from harness.physics import PH_ITEMS
from harness.score import weather_s_items

T3 = json.loads((Path(__file__).resolve().parents[2] / "engine" / "tests" / "fixtures" / "script_t3.json").read_text(encoding="utf-8"))


def _court(*effects):
    s = copy.deepcopy(T3)
    s["world"] = {"id": "rain_courtyard", "params": {}}
    s["lighting"] = {"id": "softbox_three_point", "params": {}}
    s["effects"] = list(s.get("effects", [])) + [{"id": e, "params": {}} for e in effects]
    return s


def test_rain_keeps_its_coupling_in_the_checked_script():
    cat = Catalog.load()
    r = check(_court("rain"), _p("sports_car"), cat)
    items = weather_s_items(r.script, cat, ["weather.rain", "surface.wet"])
    assert items["PH-08s"].status == "pass" and items["PH-07s"].status == "pass" and items["W-01"].status == "pass"
    bare = copy.deepcopy(r.script)
    bare["effects"] = [e for e in bare["effects"] if e["id"] != "droplets"]
    assert weather_s_items(bare, cat)["PH-08s"].status == "fail"


def test_delivered_capabilities_and_one_family():
    cat = Catalog.load()
    s = _court("snow")
    assert weather_s_items(s, cat, ["weather.rain"])["PH-07s"].status == "fail"
    assert weather_s_items(s, cat)["PH-07s"].status == "na" and weather_s_items(s, cat)["PH-08s"].status == "na"
    assert weather_s_items(_court("snow", "ground_fog"), cat)["W-01"].status == "fail"


def test_physics_section_lists_the_weather_items():
    ph = {p["id"]: p["method"] for p in PH_ITEMS}
    assert (ph["PH-05"], ph["PH-06"], ph["PH-08"]) == ("C+M", "M", "V")
