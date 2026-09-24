import json

import pytest

from engine.tests.conftest import requires_blender
from harness.run import run_suite

pytestmark = [pytest.mark.blender, requires_blender]


def test_one_case_end_to_end(tmp_path):
    summary = run_suite("v0", models=["toycar"], scripts=["t3_attempt"], tier="keyframes", key_limit=3,
                        out_root=tmp_path, run_id="smoke")
    case = tmp_path / "smoke" / "toycar__t3_attempt"
    rep = json.loads((case / "report.json").read_text())
    items = rep["items"]
    assert len(json.loads((case / "render_log.json").read_text())["frames"]) == 3
    # key_limit=3 keeps a detail frame, so T3-03's M half is measured, never n/a
    assert items["T3-03"]["status"] in ("pass", "fail") and "M=na" not in items["T3-03"]["detail"]
    for iid in ("B-01", "B-02", "B-05", "T1-X1", "T1-X2", "T1-X3"):  # baseline measured on 3 frames
        assert items[iid]["status"] in ("pass", "fail"), iid
    assert items["T1-X1"]["status"] == "pass"  # five cut shots, no turntable
    assert rep["denseGaps"] == ["B-03", "T3-12", "T3-17"]
    # A T1 result names what holds it there; anything higher is provisional (V items are unmeasured).
    assert rep["blocking"] if rep["tier"] == "T1" else rep["provisional"] is True
    assert (case / "contact_sheet.png").is_file()
    assert (tmp_path / "smoke" / "summary.md").read_text().count("toycar__t3_attempt") >= 1
    assert summary["cases"][0]["case"] == "toycar__t3_attempt"
