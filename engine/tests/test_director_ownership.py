import json

from engine.catalog import Catalog
from engine.director.axes import axis_values
from engine.director.job import make_job
from engine.director.llm import FakeProvider
from engine.director.pipeline import direct
from engine.director.rulebook import EXAMPLES_DIR
from engine.director.sanitize import sanitize
from engine.realism import realism_defaults
from engine.tests.test_director_package import _p

WATCH = json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8"))["script"]


def test_llm_cannot_write_realism_or_fields_wind_only_via_schema_pipeline_still_owns_realism():
    from engine.tests.dice_seeds import phase4_catalog
    p, cat = _p("pocket_watch"), phase4_catalog()   # the phase-4 menu: about the reply, not the grown dice
    hostile = {**WATCH, "realism": [{"id": "tyre_contact", "params": {}}],
               "wind": {"id": "wind", "params": {"speedMs": 14}}, "field": {"id": "wind"}}
    r = direct("luxury", p, provider=FakeProvider([hostile]), seed=11, duration=10, catalog=cat)
    clean = direct("luxury", p, provider=FakeProvider([WATCH]), seed=11, duration=10, catalog=cat)
    # Delivered by the LLM path, not by the fallback (a fallback would pass the checks below vacuously).
    for res in (r, clean):
        assert res.source.startswith("llm") and not res.source.startswith("fallback") and res.firstPassOk
        assert res.rounds[0]["ok"] and "error" not in res.rounds[0]
    assert r.source == clean.source
    # The sanitizer stripped each LLM-written field and recorded it as a repair.
    assert {"owned_field_overwritten", "llm_key_dropped"} <= set(r.rounds[0]["repaired"])
    assert not {"owned_field_overwritten", "llm_key_dropped"} & set(clean.rounds[0]["repaired"])
    job = make_job("luxury", p, cat, seed=11, duration=10)
    s, issues = sanitize(hostile, job, cat, p)
    got = {(i.code, i.path, i.severity) for i in issues}
    assert {("owned_field_overwritten", "realism", "repaired"), ("llm_key_dropped", "field", "repaired")} <= got
    assert ("llm_key_dropped", "wind", "repaired") not in got   # a schema-valid wind is the model's (Task 58)
    assert "field" not in s and s["wind"] == hostile["wind"] and "tyre_contact" not in {x["id"] for x in s.get("realism", [])}
    # Phase 5 Task 58 (H3): wind reaches the script only through the schema path; resolve_wind pins what the
    # model set (14 m/s, the top of the block's range) and fills the rest; `field` never lands.
    from engine.physics.applies import resolve_wind
    want = {**r.script, "wind": hostile["wind"]}
    want.pop("realism", None)
    resolve_wind(want, cat, [], given=hostile["wind"])
    assert "field" not in r.script and r.script["wind"] == want["wind"]
    assert r.script["wind"]["params"]["speedMs"] == 14 and r.script["wind"]["pinned"] == ["speedMs"]
    assert r.script.get("realism", []) == clean.script.get("realism", [])        # pipeline-owned, as without the LLM's
    assert "tyre_contact" not in {x["id"] for x in r.script.get("realism", [])}
    want = {x["id"] for x in realism_defaults(p, cat, r.script) or []}
    assert {x["id"] for x in r.script.get("realism", [])} == want              # the pipeline's own resolution


def test_turntable_never_rolled_negative_control():
    p, cat = _p("pocket_watch"), Catalog.load()
    fmt = {"aspect": "9:16", "durationS": 10, "fps": 30}
    assert "turntable" not in axis_values(p, cat, fmt)["opener"]
    assert "turntable" not in axis_values(p, cat, fmt, rollable=False)["opener"]
