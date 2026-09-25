"""Task 91: py -m harness look, the budgeted look-check (no rendering in tests)."""
import json
from pathlib import Path

import pytest

from harness import look
from harness.budget import BudgetExceeded

FIX = Path(__file__).resolve().parents[2] / "engine" / "tests" / "fixtures" / "script_t3.json"


def test_more_than_three_frames_is_refused():
    with pytest.raises(BudgetExceeded):
        look.run_look(FIX, "sports_car", frames=4, dry_run=True)


def test_dry_run_lists_the_times_and_renders_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(look, "compile_scene", lambda *a, **k: pytest.fail("a dry run rendered"))
    r = look.run_look(FIX, "sports_car", frames=2, at=[1.0, 4.5], dry_run=True, out_root=tmp_path)
    assert r["dryRun"] and r["times"] == [1.0, 4.5]
    fps = json.loads(FIX.read_text(encoding="utf-8"))["format"]["fps"]
    assert r["frames"] == [round(1.0 * fps) + 1, round(4.5 * fps) + 1]
    assert not any(tmp_path.iterdir())


def test_default_times_spread_over_the_clip():
    r = look.run_look(FIX, "sports_car", frames=3, dry_run=True)
    dur = json.loads(FIX.read_text(encoding="utf-8"))["format"]["durationS"]
    assert len(r["times"]) == 3 and all(0 <= t < dur for t in r["times"]) and r["times"] == sorted(r["times"])


def test_at_must_match_frames():
    with pytest.raises(ValueError):
        look.run_look(FIX, "sports_car", frames=1, at=[1.0, 2.0], dry_run=True)


def test_reservation_happens_before_the_render(monkeypatch, tmp_path):
    seen = {}

    def fake_compile(script, profile, glb, out, *, tier, frames, **k):
        seen["used"], seen["tier"], seen["frames"] = look.LAST_BUDGET.used, tier, list(frames)
        beauty = Path(out) / "beauty"
        beauty.mkdir(parents=True)
        for f in frames:
            (beauty / f"{f:04d}.png").write_bytes(b"png")
        return {"renderLog": {"device": "CPU", "frames": [{"frame": f, "seconds": 2.0} for f in frames], "totalSeconds": 4.1}}

    monkeypatch.setattr(look, "compile_scene", fake_compile)
    r = look.run_look(FIX, "sports_car", frames=2, at=[1.0, 2.0], out_root=tmp_path)
    assert seen == {"used": 2, "tier": "preview", "frames": r["frames"]}
    meta = json.loads((Path(r["out"]) / "look.json").read_text(encoding="utf-8"))
    assert meta["scriptSha"] == r["scriptSha"] and meta["times"] == [1.0, 2.0] and len(meta["pngs"]) == 2
    assert meta["gpuSeconds"] == 4.1 and meta["device"] == "CPU"
    assert Path(r["out"]).parent == tmp_path and Path(r["out"]).name == r["scriptSha"][:16]


def test_a_failing_render_does_not_refund(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise RuntimeError("blender died")

    monkeypatch.setattr(look, "compile_scene", boom)
    with pytest.raises(RuntimeError):
        look.run_look(FIX, "sports_car", frames=3, out_root=tmp_path)
    assert look.LAST_BUDGET.used == 3 and look.LAST_BUDGET.left == 0


def test_cli_dry_run(capsys):
    from harness.__main__ import main
    assert main(["look", "--script", str(FIX), "--profile", "sports_car", "--frames", "1", "--dry-run"]) == 0
    assert "frame" in capsys.readouterr().out
