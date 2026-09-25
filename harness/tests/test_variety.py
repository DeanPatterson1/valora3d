from engine.director.llm import FakeProvider
from harness.variety import run_variety

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
