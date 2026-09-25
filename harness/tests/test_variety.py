import numpy as np
import pytest
from PIL import Image

from engine.director.llm import FakeProvider
from harness.variety import MAX_FRAMES_TOTAL, frame_distance, make_renderer, run_variety

REFUSE = lambda cid: FakeProvider([{"stop_reason": "refusal", "text": ""}] * 3)  # noqa: E731


def test_variety_report_offline(tmp_path):
    s = run_variety(models=["pocket_watch", "sports_car"], prompt_ids=["empty", "luxury"], runs=5,
                    provider_factory=REFUSE, out_root=tmp_path, run_id="t")
    m = s["metrics"]
    assert m["groups"] == 4 and m["errors"] == 0
    for g in s["groups"]:        # memory on: no repeat before the viable pool is used up (sports_car+luxury: 4)
        assert g["exactRepeats"] == max(0, g["runs"] - min(h["viable"] for h in g["honesty"])), g["model"]
    assert m["meanDirectionDistance"]["value"] > 0 and m["meanScriptDistance"]["value"] > 0
    assert all(g["tierRegressions"] == 0 for g in s["groups"])            # paired, per case, per group
    assert m["frameDistance"]["n"] == 0 and (tmp_path / "t" / "summary.md").exists()
    g = next(c for c in s["groups"] if c["prompt"] == "luxury" and c["model"] == "pocket_watch")
    assert all(d["axes"]["mood"] == "premium_dark" for d in g["directions"])
    assert g["baselineSource"] == ["frozen"] * 5                             # compared with the frozen fixture
    assert len(g["honesty"]) == 5 and all(h["pins"] == {"mood": "premium_dark"} and "viable" in h
                                         for h in g["honesty"])
    assert {h["seed"] for h in g["honesty"]} == set(range(5))


def test_markers_reach_the_honesty_block(tmp_path):
    s = run_variety(models=["pocket_watch"], prompt_ids=["markers_details"], runs=2, provider_factory=REFUSE,
                    out_root=tmp_path, run_id="mk")
    assert s["groups"][0]["baselineSource"] == ["phase3_default"] * 2 and len(s["groups"][0]["honesty"]) == 2


def test_hold_direction_proves_layer_one(tmp_path):
    s = run_variety(models=["pocket_watch"], prompt_ids=["empty"], runs=3, hold_direction=True,
                    provider_factory=REFUSE, out_root=tmp_path, run_id="h")
    g = s["groups"][0]
    assert len({d["id"] for d in g["directions"]}) == 1 and g["meanScriptDistance"] > 0


def test_single_run_reports_without_crashing(tmp_path):
    s = run_variety(models=["pocket_watch"], prompt_ids=["empty"], runs=1, provider_factory=REFUSE,
                    out_root=tmp_path, run_id="one")
    assert s["groups"][0]["meanDirectionDistance"] is None
    assert "n/a" in (tmp_path / "one" / "summary.md").read_text(encoding="utf-8")


def _png(path, rgb):
    Image.fromarray(np.full((64, 36, 3), rgb, dtype=np.uint8)).save(path)
    return path


def test_frame_distance(tmp_path):
    a, b = _png(tmp_path / "a.png", (10, 10, 10)), _png(tmp_path / "b.png", (240, 240, 240))
    assert frame_distance(a, a) == 0.0 and 0.5 < frame_distance(a, b) <= 1.0


def test_budget_cannot_exceed_three():
    assert MAX_FRAMES_TOTAL == 3
    with pytest.raises(ValueError):
        make_renderer("x", budget=4)


def test_a_failed_render_consumes_its_reservation(tmp_path, monkeypatch):
    calls = []

    def boom(script, profile, glb, out_dir, **kw):
        calls.append(1)
        raise RuntimeError("Blender crashed")

    import harness.variety as hv
    monkeypatch.setattr(hv, "compile_scene", boom)
    run_variety(models=["pocket_watch", "sneaker", "toycar"], prompt_ids=["empty"], runs=3, provider_factory=REFUSE,
                out_root=tmp_path, run_id="f", render=make_renderer(tmp_path / "frames"))
    assert len(calls) == MAX_FRAMES_TOTAL          # three attempts in total, then nothing more


def test_total_frames_per_invocation_never_exceed_three(tmp_path, monkeypatch):
    calls = []

    def fake_compile(script, profile, glb, out_dir, **kw):
        assert kw["tier"] == "keyframes" and len(kw["frames"]) == 1
        calls.append(kw["frames"][0])
        (out_dir / "beauty").mkdir(parents=True, exist_ok=True)
        _png(out_dir / "beauty" / f"{kw['frames'][0]:04d}.png", (script["seed"] % 255, 0, 0))
        return {}

    import harness.variety as hv
    monkeypatch.setattr(hv, "compile_scene", fake_compile)
    s = run_variety(models=["pocket_watch", "sneaker"], prompt_ids=["empty"], runs=5, provider_factory=REFUSE,
                    out_root=tmp_path, run_id="r", render=make_renderer(tmp_path / "frames"))
    assert len(calls) <= MAX_FRAMES_TOTAL                      # 2 groups x 5 runs asked; 3 frames rendered
    rendered = [g["frameDistance"] for g in s["groups"] if g["frameDistance"] is not None]
    assert len(rendered) == 1 and rendered[0] > 0              # one group got 3 runs x 1 frame


def test_harness_variety_cli_offline(tmp_path, capsys):
    import json

    from harness.__main__ import main
    rc = main(["variety", "--models", "pocket_watch", "--prompt-ids", "empty", "--runs", "2",
               "--out-root", str(tmp_path), "--run-id", "cli"])
    m = json.loads(capsys.readouterr().out)
    assert rc == 0 and m["groups"] == 1 and m["tierRegressions"] == 0
    assert (tmp_path / "cli" / "summary.json").exists()


def test_harness_variety_cli_render_is_capped_and_announced(tmp_path, capsys, monkeypatch):
    """--render with compile_scene stubbed (no Blender): the 3-frame notice, never more than 3 frames."""
    import harness.variety as hv
    from harness.__main__ import main
    calls = []

    def fake_compile(script, profile, glb, out_dir, **kw):
        calls.append(1)
        (out_dir / "beauty").mkdir(parents=True, exist_ok=True)
        _png(out_dir / "beauty" / f"{kw['frames'][0]:04d}.png", (len(calls) * 60, 0, 0))
        return {}
    monkeypatch.setattr(hv, "compile_scene", fake_compile)
    rc = main(["variety", "--models", "pocket_watch", "--prompt-ids", "empty", "--runs", "5", "--render",
               "--out-root", str(tmp_path), "--run-id", "r"])
    out = capsys.readouterr().out
    assert rc == 0 and "rendering at most 3 frames in total (keyframes tier)" in out and len(calls) == 3


def test_harness_variety_cli_has_no_budget_flag():
    from harness.__main__ import main
    with pytest.raises(SystemExit):
        main(["variety", "--frames", "10"])


def test_paired_gains_never_cancel_losses(tmp_path, monkeypatch):
    """Two runs lose a tier against their own baseline and two gain one: the gate must count 2, not 0
    (paired per case, never a net of gains against losses)."""
    import harness.variety as hv
    run_tiers = iter(["T3", "T1", "T3", "T1"])
    monkeypatch.setattr(hv, "script_tier", lambda *a, **k: next(run_tiers))
    monkeypatch.setattr(hv, "baseline_case", lambda *a, **k: {"tier": "T2"})
    s = run_variety(models=["pocket_watch"], prompt_ids=["empty"], runs=4, provider_factory=REFUSE,
                    out_root=tmp_path, run_id="pairs")
    g = s["groups"][0]
    assert g["tiers"] == ["T3", "T1", "T3", "T1"] and g["baselineTiers"] == ["T2"] * 4
    assert g["tierRegressions"] == 2 and s["metrics"]["tierRegressions"] == 2
