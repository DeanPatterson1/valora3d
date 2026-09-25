import json

from engine.catalog import Catalog
from engine.director.axes import axis_values
from engine.director.llm import FakeProvider
from engine.director.pipeline import direct
from engine.director.rulebook import EXAMPLES_DIR
from engine.realism import realism_defaults
from engine.tests.test_director_package import _p

WATCH = json.loads((EXAMPLES_DIR / "watch_luxury.json").read_text(encoding="utf-8"))["script"]


def test_llm_cannot_write_realism_wind_or_fields_pipeline_still_owns_realism():
    p, cat = _p("pocket_watch"), Catalog.load()
    hostile = {**WATCH, "realism": [{"id": "tyre_contact", "params": {}}],
               "wind": {"id": "wind", "params": {"speedMs": 14}}, "field": {"id": "wind"}}
    r = direct("luxury", p, provider=FakeProvider([hostile]), seed=11, duration=10)
    clean = direct("luxury", p, provider=FakeProvider([WATCH]), seed=11, duration=10)
    # The checker resolves wind itself (phase-3.5 H3: system-owned `wind`); the LLM's 14 m/s never lands.
    assert "field" not in r.script and r.script.get("wind") == clean.script.get("wind")
    assert (r.script.get("wind") or {}).get("params", {}).get("speedMs") != 14
    assert r.script.get("realism", []) == clean.script.get("realism", [])        # pipeline-owned, as without the LLM's
    assert "tyre_contact" not in {x["id"] for x in r.script.get("realism", [])}
    want = {x["id"] for x in realism_defaults(p, cat, r.script) or []}
    assert {x["id"] for x in r.script.get("realism", [])} == want              # the pipeline's own resolution


def test_turntable_never_rolled_negative_control():
    p, cat = _p("pocket_watch"), Catalog.load()
    fmt = {"aspect": "9:16", "durationS": 10, "fps": 30}
    assert "turntable" not in axis_values(p, cat, fmt)["opener"]
    assert "turntable" not in axis_values(p, cat, fmt, rollable=False)["opener"]
