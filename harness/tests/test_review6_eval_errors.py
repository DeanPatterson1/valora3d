"""Review 6 #9 on harness/director_eval.py: only the expected director rejection of a checker case is
checker-only; a genuine failure (bug, write failure, unknown pin) stays an error, and rejections are not errors."""
import json

from engine.director.llm import FakeProvider
from harness import director_eval as de

REFUSE = lambda cid: FakeProvider([{"stop_reason": "refusal", "text": ""}])  # noqa: E731


# ---- #9: only the expected rejection is checker-only ---------------------------------------------------------
def test_an_expected_rejection_is_checker_only_and_not_an_error(tmp_path):
    s = de.run_director_eval("v1", models=["sports_car"], prompt_ids=["street_giant"], provider_factory=REFUSE,
                             out_root=tmp_path, run_id="giant")
    row = s["cases"][0]
    assert row.get("checkerOnly") and "error" not in row and row["expectCheck"]["met"]
    assert s["metrics"]["checkerOnly"] == 1 and s["metrics"]["errors"] == 0


def test_a_director_fallback_refusal_is_an_expected_rejection(tmp_path, monkeypatch):
    from engine.director.fallback import FallbackError

    def refuse(*a, **k):
        raise FallbackError("subject_size_unsupported at world")
    monkeypatch.setattr(de, "direct", refuse)
    s = de.run_director_eval("v1", models=["sports_car"], prompt_ids=["street_giant"], provider_factory=REFUSE,
                             out_root=tmp_path, run_id="fb")
    row = s["cases"][0]
    assert row.get("checkerOnly") and "error" not in row
    assert s["metrics"]["errors"] == 0


def test_an_unexpected_exception_on_a_checker_case_is_an_error(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise KeyError("programming bug")
    monkeypatch.setattr(de, "pinned_direction", boom)
    s = de.run_director_eval("v1", models=["sports_car"], prompt_ids=["street_giant"], provider_factory=REFUSE,
                             out_root=tmp_path, run_id="boom")
    row = s["cases"][0]
    assert not row.get("checkerOnly") and "KeyError" in row["error"]
    assert row["expectCheck"]["met"]                        # the checker verdict is still recorded
    assert s["metrics"]["errors"] == 1 and s["metrics"]["checkerOnly"] == 0


def test_an_output_write_failure_on_a_checker_case_is_an_error(tmp_path, monkeypatch):
    def ok(*a, **k):
        return None, None
    monkeypatch.setattr(de, "pinned_direction", ok)
    monkeypatch.setattr(de, "_case_metrics", lambda *a, **k: {})

    class Res:
        script = {}
    monkeypatch.setattr(de, "direct", lambda *a, **k: Res())
    real = de.Path.write_text

    def fail(self, *a, **k):
        if self.name.endswith(".script.json"):
            raise OSError("disk full")
        return real(self, *a, **k)
    monkeypatch.setattr(de.Path, "write_text", fail)
    s = de.run_director_eval("v1", models=["sports_car"], prompt_ids=["street_giant"], provider_factory=REFUSE,
                             out_root=tmp_path, run_id="w")
    row = s["cases"][0]
    assert not row.get("checkerOnly") and "OSError" in row["error"] and s["metrics"]["errors"] == 1


def test_an_unknown_pin_on_a_checker_case_is_an_error_not_a_rejection(tmp_path, monkeypatch):
    d = tmp_path / "prompts"
    d.mkdir()
    case = {"id": "typo", "prompt": "neon street at night", "pins": {"world": "no_such_world"},
            "subjectScaleM": 9.0, "expectCheck": "subject_size_unsupported"}
    (d / "t.json").write_text(json.dumps({"prompts": [case], "markerSets": {}}), encoding="utf-8")
    monkeypatch.setattr(de, "PROMPTS", d)
    s = de.run_director_eval("t", models=["sports_car"], provider_factory=REFUSE, out_root=tmp_path / "o", run_id="t")
    row = s["cases"][0]
    assert not row.get("checkerOnly") and "no_such_world" in row["error"] and s["metrics"]["errors"] == 1
