"""Phase 5 Task 58 (hand-off H3): wind is director-selectable through the output schema only. Sanitize keeps a
schema-valid `wind` and resolve_wind pins what the LLM set; `field` and per-effect wind params are still
dropped; the LLM still never writes realism."""
import json

from engine.catalog import Catalog
from engine.director.job import make_job
from engine.director.llm import FakeProvider
from engine.director.output_schema import scene_output_schema
from engine.director.pipeline import direct
from engine.director.rulebook import EXAMPLES_DIR
from engine.director.sanitize import sanitize
from engine.tests.dice_seeds import seed_matching
from engine.tests.test_director_package import _p

WATCH = json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8"))["script"]
WIND_PARAMS = {"directionDeg", "speedMs", "gustiness", "turbulence"}


def _direct(prompt, reply):
    seed = seed_matching(reply, prompt, duration=10)          # a roll the canned reply already follows
    return direct(prompt, _p("pocket_watch"), provider=FakeProvider([reply]), seed=seed, duration=10)


def test_schema_has_one_wind_object_and_no_field_key():
    cat = Catalog.load()
    props = scene_output_schema(cat)["properties"]
    assert "wind" in props and "field" not in props
    assert set(props["wind"]["properties"]["params"]["properties"]) == WIND_PARAMS
    assert "wind" not in scene_output_schema(cat)["required"]            # optional: still air unless asked
    compact = scene_output_schema(cat, compact=True)["properties"]["wind"]
    assert compact["properties"]["id"]["enum"] == ["wind"]
    assert set(compact["properties"]["params"]["items"]["properties"]["name"]["enum"]) == WIND_PARAMS


def test_llm_wind_survives_sanitize_and_is_pinned():
    reply = {**WATCH, "wind": {"id": "wind", "params": {"speedMs": 4.0}}}
    r = _direct("windy", reply)
    assert r.source.startswith("llm"), r.source
    assert r.script["wind"]["params"]["speedMs"] == 4.0 and "speedMs" in r.script["wind"]["pinned"]


def test_malformed_wind_is_dropped_by_sanitize():
    p, cat = _p("pocket_watch"), Catalog.load()
    job = make_job("windy", p, cat, seed=0, duration=10)
    for bad in ({"id": "gale", "params": {}}, "windy", {"id": "wind", "params": "fast"}, {"id": "wind", "params": {}, "gust": 1}):
        s, issues = sanitize({**WATCH, "wind": bad}, job, cat, p)
        assert "wind" not in s and ("llm_key_dropped", "wind") in {(i.code, i.path) for i in issues}


def test_per_effect_wind_and_field_key_are_still_dropped():
    reply = {**WATCH, "field": {"id": "wind"}, "effects": [{"id": "haze_volume", "params": {"windSpeed": 9}}]}
    r = _direct("", reply)
    assert "field" not in r.script
    assert all("windSpeed" not in e["params"] for e in r.script.get("effects", []))


def test_llm_still_cannot_write_realism():
    p, cat = _p("pocket_watch"), Catalog.load()
    reply = {**WATCH, "realism": [{"id": "tyre_contact", "params": {}}]}
    r = _direct("", reply)
    from engine.realism import realism_defaults
    assert r.script.get("realism", []) == (realism_defaults(p, cat, r.script) or [])


def test_windy_is_now_delivered_not_unsupported():
    r = _direct("windy", {**WATCH, "wind": {"id": "wind", "params": {"speedMs": 6}}})
    assert "wind.breeze" not in {u["capability"] for u in r.script.get("unsupported", [])}
    assert "wind.breeze" in Catalog.load().capabilities(_p("pocket_watch"))
