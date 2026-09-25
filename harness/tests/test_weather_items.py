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


def test_ph07s_reads_the_cases_expectations_through_score_case(tmp_path):          # review chunk3 #7
    import json as _json

    from harness.score import EXPECT_FILE, score_case
    from harness.tests.test_score import FIX, TH, SubjectProfile, _write_case
    prof = SubjectProfile.from_dict(_json.loads((FIX / "profiles" / "toycar.json").read_text()))
    _write_case(tmp_path, [16, 70])
    (tmp_path / "compile.json").write_text(_json.dumps({"realismProbe": {"16": {"minZ": 0.0, "tyres": {}}}}))
    cat = Catalog.load()
    assert score_case(tmp_path, prof, cat, TH)["physics"]["PH-07s"]["status"] == "na"
    (tmp_path / EXPECT_FILE).write_text(_json.dumps({"expectDelivered": ["weather.rain"]}))
    ph = score_case(tmp_path, prof, cat, TH)["physics"]["PH-07s"]
    assert ph["status"] == "fail" and ph["value"] == ["weather.rain"]       # a missing capability is caught
    assert score_case(tmp_path, prof, cat, TH, ["weather.rain"])["physics"]["PH-07s"]["status"] == "fail"


def test_director_eval_scores_expect_delivered(tmp_path):                             # review chunk3 #7
    from engine.director.llm import FakeProvider
    from harness.director_eval import run_director_eval
    s = run_director_eval("v1", models=["sneaker"], prompt_ids=["windy", "empty"],
                          provider_factory=lambda case: FakeProvider([{"stop_reason": "refusal", "text": ""}]),
                          out_root=tmp_path, run_id="w")
    rows = {c["case"].split("__")[1]: c for c in s["cases"]}
    assert rows["empty"]["weather"]["PH-07s"] == "na"
    assert rows["windy"]["weather"]["PH-07s"] in ("pass", "fail") and s["metrics"]["deliveredMet"]["n"] == 1


def test_ph08s_exempts_a_coupled_child_the_subject_cannot_take():                    # review chunk3 #8
    import dataclasses
    cat = Catalog.load()
    s = _court("rain", "wet_surface")                                  # droplets absent, as coupled_skipped leaves it
    flat = dataclasses.replace(_p("sports_car"), surfaceSamples=[])    # no up-facing surface known
    assert weather_s_items(s, cat, profile=flat)["PH-08s"].status == "pass"
    assert weather_s_items(s, cat, profile=_p("sports_car"))["PH-08s"].status == "fail"
    assert weather_s_items(s, cat)["PH-08s"].status == "fail"
