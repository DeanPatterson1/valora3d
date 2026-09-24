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
    assert rep["tier"] in ("T1", "T2", "T3", "T4") and "items" in rep
    assert (tmp_path / "smoke" / "summary.md").read_text().count("toycar__t3_attempt") >= 1
    assert summary["cases"][0]["case"] == "toycar__t3_attempt"
