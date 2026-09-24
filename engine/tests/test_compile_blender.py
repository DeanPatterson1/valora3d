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


from engine.catalog import Catalog
from engine.checker import check
from engine.compiler.timeline import camera_keys
from engine.geometry import box_corners, project


def test_blender_camera_projects_exactly_like_the_checker(tmp_path):
    prof, cat = _profile("toycar"), Catalog.load()
    s = check(_script(), prof, cat).script
    frames = [1, 75, 150, 151, 300]  # includes both sides of the cut
    res = compile_scene(s, prof, MODELS / "toycar" / "toycar.glb", tmp_path, render=False,
                        skip_kinds=("world", "motion", "lighting", "effect", "grade"), probe=frames)
    keys = {k.frame: k for k in camera_keys(s, prof, cat)}
    corners = box_corners(prof.boundsMin, prof.boundsMax)
    for f in frames:
        got = res["probe"][str(f)]["corners"]
        for c, g in zip(corners, got):
            x, y, _ = project(keys[f].pose, c, s["format"]["aspect"])
            assert g[0] == pytest.approx((x + 1) / 2, abs=1e-3) and g[1] == pytest.approx((y + 1) / 2, abs=1e-3), f
        assert res["probe"][str(f)]["lens"] == pytest.approx(keys[f].pose.lens_mm)
        assert res["probe"][str(f)]["focus"] == pytest.approx(keys[f].focusM, rel=1e-4)
    assert res["shutter"] == 0.5 and res["frameEnd"] == 300


def test_studio_scene_has_cyc_and_three_softboxes(tmp_path):
    prof = _profile("toycar")
    res = compile_scene(_script(), prof, MODELS / "toycar" / "toycar.glb", tmp_path, render=False,
                        skip_kinds=("grade",))
    names = {o["name"]: o for o in res["objects"]}
    assert "valora_cyc" in names
    for n in ("valora_key", "valora_fill", "valora_rim"):
        assert names[n]["type"] == "LIGHT" and names[n]["visibleCamera"] is False
    assert res["built"] == ["world:studio_cyc", "motion:static", "lighting:softbox_three_point"]


from engine.geometry import point_in_box  # noqa: E402

RIG_PREFIXES = ("valora_overhead", "valora_strip_", "valora_accent_", "valora_rim", "valora_negfill_")


def test_t3_scene_builds_reflection_rig_and_haze(tmp_path):
    prof = _profile("toycar")
    res = compile_scene(_script("script_t3.json"), prof, MODELS / "toycar" / "toycar.glb", tmp_path,
                        render=False, skip_kinds=("grade",))
    objs = {o["name"]: o for o in res["objects"]}
    assert "valora_overhead" in objs and any(n.startswith("valora_strip_") for n in objs)
    assert any(n.startswith("valora_negfill_") for n in objs)
    for o in res["objects"]:
        if o["name"].startswith(("valora_overhead", "valora_strip_", "valora_accent_", "valora_rim")):
            assert not point_in_box(o["location"], prof.boundsMin, prof.boundsMax, 0.10), o["name"]
        if o["name"].startswith(RIG_PREFIXES):  # V-L01: seen in reflections, never by the camera
            assert o["visibleCamera"] is False and o["visibleGlossy"] is True, o["name"]
    lo, hi = res["hazeDomain"]
    for p in res["cameraPositions"]:
        assert all(l <= v <= h for v, l, h in zip(p, lo, hi))
