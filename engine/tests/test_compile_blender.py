import json
from pathlib import Path

import pytest

from engine.compiler.run import compile_scene
from engine.profile import SubjectProfile
from engine.tests.conftest import requires_blender

pytestmark = [pytest.mark.blender, requires_blender]
FIX = Path(__file__).parent / "fixtures"
MODELS = Path(__file__).resolve().parents[2] / "assets-in" / "models"


def _profile(name):
    return SubjectProfile.from_dict(json.loads((FIX / "profiles" / f"{name}.json").read_text(encoding="utf-8")))


def _script(name="script_valid.json"):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("model", ["toycar", "pocket_watch"])
def test_subject_is_placed_exactly_where_the_profile_says(model, tmp_path):
    glb = MODELS / model / f"{model}.glb"
    if not glb.exists():
        pytest.skip("model not present")
    prof = _profile(model)
    res = compile_scene(_script(), prof, glb, tmp_path, render=False, build_blocks=False)
    lo, hi = res["placedBounds"][:3], res["placedBounds"][3:]
    tol = 1e-4 * max(prof.sizeM) + 1e-6
    assert lo == pytest.approx(prof.boundsMin, abs=tol) and hi == pytest.approx(prof.boundsMax, abs=tol)
    assert lo[2] == pytest.approx(0.0, abs=tol)


def test_unit_scaled_subject_is_scaled_and_placed(tmp_path):
    # Every reference model has scaleFactor 1.0, so without this the scale and source-centre
    # terms of the placement formula would never be exercised.
    from engine.ingest.run import ingest
    from engine.tests.blender_fixtures import make_glb
    glb = make_glb("scaled", tmp_path / "scaled.glb")
    prof = ingest(glb, workdir=tmp_path / "w")
    assert prof.scaleFactor == 0.001 and prof.sourceCenter[0] == pytest.approx(30.0)
    res = compile_scene(_script(), prof, glb, tmp_path / "c", render=False, build_blocks=False)
    tol = 1e-4 * max(prof.sizeM) + 1e-6
    assert res["placedBounds"] == pytest.approx(prof.boundsMin + prof.boundsMax, abs=tol)


def test_failing_script_never_reaches_blender(tmp_path):
    from engine.compiler.run import CheckFailed
    bad = _script()
    bad["world"]["id"] = "moon"
    with pytest.raises(CheckFailed):
        compile_scene(bad, _profile("toycar"), MODELS / "toycar" / "toycar.glb", tmp_path)
    assert not (tmp_path / "job.json").exists()
