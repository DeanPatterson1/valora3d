import numpy as np

from harness.metrics import Frame
from harness.physics import ph01_c, ph02_c, seam_ratio


def _frame(strip_dark):
    rgb = np.full((100, 60, 3), 0.5, np.float32)
    mask = np.zeros((100, 60), bool)
    mask[30:70, 20:40] = True
    rgb[70:75, 20:40] = 0.5 / strip_dark
    return Frame(frame=1, t=0.0, shot=0, lens=50.0, fstop=4.0, rgb=rgb, mask=mask, gloss=mask & False, mist=None)


def test_seam_ratio_reads_the_contact_shadow():
    assert abs(seam_ratio(_frame(2.0)) - 2.0) < 1e-3       # the strip under the subject is half as bright
    assert abs(seam_ratio(_frame(1.0)) - 1.0) < 1e-3       # no seam


def test_score_case_reports_physics_in_its_own_section(tmp_path):
    import json

    from engine.catalog import Catalog
    from harness.score import score_case, write_report
    from harness.tests.test_score import FIX, TH, SubjectProfile, _write_case
    prof = SubjectProfile.from_dict(json.loads((FIX / "profiles" / "toycar.json").read_text()))
    _write_case(tmp_path, [16, 70])
    (tmp_path / "compile.json").write_text(json.dumps({"realismProbe": {"16": {"minZ": 0.0, "tyres": {}}}}))
    sc = score_case(tmp_path, prof, Catalog.load(), TH)
    assert set(sc["physics"]) == {"PH-01", "PH-02", "PH-05", "PH-06", "PH-08", "PH-08s", "PH-07s", "W-01"}
    assert "PH-01" not in sc["items"] and sc["physics"]["PH-05"]["status"] == "na"      # no weather: no verdict
    assert sc["physics"]["PH-08"]["status"] == "na" and sc["physics"]["W-01"]["status"] == "pass"
    # grounded by the probe [C], but the flat synthetic floor has no seam under the subject [M]
    assert sc["physics"]["PH-02"]["status"] == "fail" and sc["physics"]["PH-02"]["value"] == [1.0]
    write_report(tmp_path, sc)
    md = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "## Physics (research/physics/BLOCKS.md §6)" in md and "| PH-02 | C+M | fail |" in md
    assert "| W-01 | S | pass |" in md


def test_c_halves_read_the_realism_probe():
    realism = [{"id": "contact_ground", "params": {"sinkMm": 0.0}},
               {"id": "tyre_contact", "params": {"patchLenFrac": 0.45}}]
    wheels = [{"radius": 0.35}]
    good = {"1": {"minZ": 0.0, "tyres": {"0": {"minZ": 0.0, "flatLenM": 0.157, "flatN": 5}}}}   # want 0.1575
    bad = {"1": {"minZ": 0.004, "tyres": {"0": {"minZ": 0.0, "flatLenM": 0.02, "flatN": 1}}}}
    assert ph01_c(good, realism, wheels) == ("pass", None) and ph01_c(bad, realism, wheels)[0] == "fail"
    assert ph02_c(good, realism)[0] == "pass" and ph02_c(bad, realism)[0] == "fail"
    assert ph01_c({}, realism, wheels)[0] == "unmeasured"
    assert ph01_c(good, realism[:1], wheels)[0] == "na"


def test_ph01_reads_its_patch_tolerance_from_the_thresholds():
    # review item 12: PH-01 patchTol lives in harness/thresholds.json, not only in engine/physics/probes
    import json
    from pathlib import Path
    th = json.loads((Path(__file__).resolve().parents[1] / "thresholds.json").read_text(encoding="utf-8"))
    realism = [{"id": "tyre_contact", "params": {"patchLenFrac": 0.45}}]
    wheels = [{"radius": 0.35}]
    long_ = {"1": {"minZ": 0.0, "tyres": {"0": {"minZ": 0.0, "flatLenM": 0.1575 * 1.3, "flatN": 5}}}}   # +30%
    assert ph01_c(long_, realism, wheels, th["PH-01"]["patchTol"])[0] == "fail"          # 0.2 in the file
    assert ph01_c(long_, realism, wheels, 0.35)[0] == "pass"
