"""Runner bookkeeping without Blender: compile_scene is replaced by a stub that writes a tiny case."""
import json

from harness import run as runner
from harness.tests.test_score import _write_case


def test_a_failing_case_is_recorded_not_skipped(tmp_path, monkeypatch):
    def fake_compile(script, profile, model, out_dir, **kw):
        if "pocket_watch" in str(model):
            raise RuntimeError("Blender compile failed (exit 1)")
        _write_case(out_dir, [16, 70])
        return {}

    monkeypatch.setattr(runner, "compile_scene", fake_compile)
    s = runner.run_suite("v0", models=["toycar", "pocket_watch"], scripts=["t3_attempt"], tier="keyframes",
                         key_limit=2, out_root=tmp_path, run_id="r1")
    by = {c["case"]: c for c in s["cases"]}
    ok = by["toycar__t3_attempt"]
    assert (ok["tier"], ok["blocking"]) == ("T1", ["T1-X2"])  # the synthetic case's flat background
    assert "Blender compile failed" in by["pocket_watch__t3_attempt"]["error"]
    md = (tmp_path / "r1" / "summary.md").read_text()
    assert "pocket_watch__t3_attempt" in md and "ERROR" in md and "pass rate" in md
    assert json.loads((tmp_path / "r1" / "toycar__t3_attempt" / "check.json").read_text())["ok"] is True
    assert json.loads((tmp_path / "r1" / "summary.json").read_text())["cases"][1]["error"]
    assert (tmp_path / "r1" / "toycar__t3_attempt" / "contact_sheet.png").is_file()  # one sheet per case
