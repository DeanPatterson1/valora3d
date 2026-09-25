"""Review chunk5 #12: a prompt case's `models`, synthetic subjects and direction `pins` reach the director runs of
run_director_eval, not only its checker cases. Offline: a refusing FakeProvider (the fallback path)."""
import json

import pytest

from engine.director.llm import FakeProvider
from harness import director_eval as de

REFUSE = lambda cid: FakeProvider([{"stop_reason": "refusal", "text": ""}])  # noqa: E731


def _set(tmp_path, monkeypatch, prompts):
    d = tmp_path / "prompts"
    d.mkdir()
    (d / "t.json").write_text(json.dumps({"prompts": prompts, "markerSets": {}}), encoding="utf-8")
    monkeypatch.setattr(de, "PROMPTS", d)


def _scripts(tmp_path, run_id):
    return {p.name.split(".")[0]: json.loads(p.read_text(encoding="utf-8"))
            for p in (tmp_path / "out" / run_id).glob("*.script.json")}


@pytest.mark.parametrize("name", ["can", "bottle", "bare_tube"])
def test_the_synthetic_subjects_resolve(name):
    p = de._profile(name)
    assert p.longest > 0


def test_a_cases_models_choose_where_it_runs(tmp_path):
    s = de.run_director_eval("v1", prompt_ids=["roll_in", "topple"], provider_factory=REFUSE,
                             out_root=tmp_path / "out", run_id="m")
    assert sorted(c["case"] for c in s["cases"]) == ["bottle__topple__0", "can__roll_in__0"], s["cases"]
    assert s["metrics"]["errors"] == 0, s["cases"]
    # an explicit model list still filters: the can case does not run on a list without the can
    s = de.run_director_eval("v1", models=["sneaker"], prompt_ids=["roll_in", "empty"], provider_factory=REFUSE,
                             out_root=tmp_path / "out", run_id="m2")
    assert [c["case"] for c in s["cases"]] == ["sneaker__empty__0"]


def test_direction_pins_reach_the_director_run(tmp_path, monkeypatch):
    # noir: a known mood the dice never roll (rare), so four seeds all landing on it can only be the pin. Worlds:
    # studio_cyc is today the only value of the world axis, so a world pin cannot prove anything here
    _set(tmp_path, monkeypatch, [{"id": "pinned", "prompt": "luxury", "pins": {"mood": "noir", "world": "studio_cyc"}},
                                 {"id": "free", "prompt": "luxury"}])
    s = de.run_director_eval("t", models=["sports_car"], provider_factory=REFUSE, runs=4,
                             out_root=tmp_path / "out", run_id="p")
    assert s["metrics"]["errors"] == 0, s["cases"]
    got = _scripts(tmp_path, "p")
    pinned = [v for k, v in got.items() if "__pinned__" in k]
    assert len(pinned) == 4
    for sc in pinned:                                      # every seed: the pinned axes, in the script's direction
        assert sc["direction"]["id"].split("/")[:2] == ["studio_cyc", "noir"], sc["direction"]
        assert sc["world"]["id"] == "studio_cyc"
    free = [v["direction"]["id"].split("/")[1] for k, v in got.items() if "__free__" in k]
    assert len(free) == 4 and "noir" not in free, free      # the unpinned case is still rolled


def test_the_v1_pinned_cases_run_pinned(tmp_path):
    s = de.run_director_eval("v1", prompt_ids=["drive_studio"], provider_factory=REFUSE,
                             out_root=tmp_path / "out", run_id="v")
    assert [c["case"] for c in s["cases"]] == ["sports_car__drive_studio__0"] and s["metrics"]["errors"] == 0
    sc = _scripts(tmp_path, "v")["sports_car__drive_studio__0"]
    assert sc["world"]["id"] == "studio_cyc"


def test_a_pin_the_subject_cannot_take_is_an_error_not_a_silent_roll(tmp_path, monkeypatch):
    _set(tmp_path, monkeypatch, [{"id": "bad", "prompt": "luxury", "pins": {"world": "no_such_world"}}])
    s = de.run_director_eval("t", models=["sports_car"], provider_factory=REFUSE, out_root=tmp_path / "out", run_id="b")
    assert len(s["cases"]) == 1 and "no_such_world" in s["cases"][0]["error"], s["cases"]
