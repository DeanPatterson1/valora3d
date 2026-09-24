import json
from pathlib import Path

import numpy as np
from PIL import Image

from engine.catalog import Catalog
from engine.craft_rules import ItemResult
from engine.profile import SubjectProfile
from harness.items import ITEMS
from harness.score import merge, score_case, tier_reached, write_report

FIX = Path(__file__).resolve().parents[2] / "engine" / "tests" / "fixtures"
TH = json.loads((Path(__file__).resolve().parents[1] / "thresholds.json").read_text())


def _all(status="pass", **over):
    return {i["id"]: ItemResult(i["id"], over.get(i["id"], status)) for i in ITEMS}


def test_everything_passing_but_no_sim_is_t3():
    r = _all(**{"T4-03": "fail"})
    assert tier_reached(r) == {"tier": "T3", "provisional": False, "blocking": ["T4-03"]}


def test_a_baseline_or_t1_signature_failure_caps_at_t1():
    assert tier_reached(_all(**{"B-02": "fail"}))["tier"] == "T1"
    assert tier_reached(_all(**{"T1-X3": "fail"}))["tier"] == "T1"


def test_tiers_are_cumulative():
    assert tier_reached(_all(**{"T2-07": "fail"}))["tier"] == "T1"
    assert tier_reached(_all(**{"T3-06": "fail"}))["tier"] == "T2"


def test_unmeasured_items_make_the_result_provisional_not_failing():
    r = tier_reached(_all(**{"T3-10": "unmeasured", "T4-03": "fail"}))
    assert r["tier"] == "T3" and r["provisional"] is True


def _s(**st):
    return [ItemResult(k.replace("_", "-"), v) for k, v in st.items()]


def test_merge_s_plus_m_fails_if_either_half_fails():
    r = merge(_s(T2_07="pass"), {"T2-07": ItemResult("T2-07", "fail")})
    assert r["T2-07"].status == "fail"
    r = merge(_s(T2_07="fail"), {"T2-07": ItemResult("T2-07", "pass")})
    assert r["T2-07"].status == "fail"


def test_merge_s_plus_m_is_unmeasured_when_a_half_is_missing_or_unmeasured():
    assert merge(_s(T3_03="pass"), {})["T3-03"].status == "unmeasured"
    assert merge(_s(T3_03="pass"), {"T3-03": ItemResult("T3-03", "unmeasured")})["T3-03"].status == "unmeasured"


def test_merge_s_plus_m_is_na_only_when_both_halves_are():
    assert merge(_s(T3_03="na"), {"T3-03": ItemResult("T3-03", "na")})["T3-03"].status == "na"
    assert merge(_s(T3_03="na"), {"T3-03": ItemResult("T3-03", "pass")})["T3-03"].status == "pass"


def test_merge_covers_the_registry_with_s_fallbacks_and_v_unmeasured():
    r = merge(_s(T2_08="pass", T3_01="fail"), {})
    assert set(r) == {i["id"] for i in ITEMS}
    assert r["T2-08"].status == "pass" and r["T3-01"].status == "fail"  # S fallback / script cut times
    assert r["T2-09"].status == "unmeasured" and r["B-04"].status == "pass"
    assert r["B-01"].status == "unmeasured"  # an M item nobody measured is never a pass


def _write_case(d, frames):
    (d / "beauty").mkdir(parents=True)
    (d / "passes").mkdir()
    H, W = 256, 144
    mask = np.zeros((H, W), np.uint8)
    mask[64:192, 30:114] = 255
    for f in frames:
        rgb = np.full((H, W, 3), 60, np.uint8)
        rgb[mask > 0] = 150
        Image.fromarray(rgb).save(d / "beauty" / f"{f:04d}.png")
        Image.fromarray(mask).save(d / "passes" / f"mask_{f:04d}.png")
        Image.fromarray(mask).save(d / "passes" / f"gloss_{f:04d}.png")
        mist = np.tile(np.linspace(0, 65535, H, dtype=np.uint16)[:, None], (1, W))
        Image.fromarray(mist).save(d / "passes" / f"mist_{f:04d}.png")
    (d / "render_log.json").write_text(json.dumps({"frames": [{"frame": f} for f in frames]}))


def test_score_case_on_a_tiny_synthetic_case(tmp_path):
    from harness.frames import load_frames
    prof = SubjectProfile.from_dict(json.loads((FIX / "profiles" / "toycar.json").read_text()))
    script = json.loads((FIX / "script_t3.json").read_text())
    cat = Catalog.load()
    _write_case(tmp_path, [16, 70])
    fr = load_frames(tmp_path, script, cat)
    assert [(f.frame, f.shot, f.lens) for f in fr] == [(16, 0, 40.0), (70, 1, 100.0)]
    assert fr[0].mask.sum() == 128 * 84 and 0.0 <= fr[0].mist.min() and fr[0].mist.max() <= 1.0
    sc = score_case(tmp_path, script, prof, cat, TH)
    assert set(sc["items"]) == {i["id"] for i in ITEMS}
    assert sc["items"]["B-01"]["status"] == "pass" and sc["tier"] in ("T1", "T2", "T3")
    write_report(tmp_path, sc)
    rep = json.loads((tmp_path / "report.json").read_text())
    assert rep["tier"] == sc["tier"]
    md = (tmp_path / "report.md").read_text()
    fails = [ln for ln in md.splitlines() if "| fail |" in ln]
    assert fails and md.index(fails[0]) < md.index("| pass |")  # failing items first
