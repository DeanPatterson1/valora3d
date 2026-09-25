import json

import pytest

from engine.director.llm import FakeProvider, LLMError, RecordingProvider

FIXTURE = "engine/tests/fixtures/director/watch_luxury_ok.json"


def test_fake_replays_scripts_text_stops_and_errors():
    p = FakeProvider([{"shots": []}, "not json", {"stop_reason": "refusal", "text": ""},
                      {"error": "boom", "retryable": True}])
    kw = dict(system="S", messages=[{"role": "user", "content": "u"}], schema={}, max_tokens=10)
    assert json.loads(p.generate(**kw).text) == {"shots": []}
    assert p.generate(**kw).text == "not json"
    assert p.generate(**kw).stop_reason == "refusal"
    with pytest.raises(LLMError) as e:
        p.generate(**kw)
    assert e.value.retryable
    with pytest.raises(LLMError):
        p.generate(**kw)  # out of replies
    assert len(p.calls) == 5 and p.calls[0]["messages"][0]["content"] == "u"


def test_fixture_file_loads_and_is_the_example_script():
    p = FakeProvider.from_fixture(FIXTURE)
    got = json.loads(p.generate(system="", messages=[], schema={}, max_tokens=1).text)
    ex = json.loads(open("engine/director/examples/watch_luxury.json", encoding="utf-8").read())["script"]
    assert got["shots"] and got == ex


def test_recording_provider_writes_replies_never_the_system_text(tmp_path):
    out = tmp_path / "rec.json"
    rec = RecordingProvider(FakeProvider([{"shots": []}]), out)
    rec.generate(system="SECRET RULEBOOK", messages=[], schema={}, max_tokens=1)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["replies"] == [{"text": '{"shots": []}', "stop_reason": "end_turn"}]
    assert "SECRET RULEBOOK" not in out.read_text(encoding="utf-8")
    assert len(data["recorded"][0]["rulebookSha"]) == 12


def test_recorded_file_replays_through_fake(tmp_path):
    out = tmp_path / "rec.json"
    RecordingProvider(FakeProvider([{"shots": [1]}, {"stop_reason": "refusal", "text": ""}]), out).generate(
        system="S", messages=[], schema={}, max_tokens=1)
    p = FakeProvider.from_fixture(out)
    assert json.loads(p.generate(system="", messages=[], schema={}, max_tokens=1).text) == {"shots": [1]}
