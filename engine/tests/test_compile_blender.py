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


def test_grade_builds_a_compositor_and_a_valid_look(tmp_path):
    prof = _profile("toycar")
    res = compile_scene(_script("script_t3.json"), prof, MODELS / "toycar" / "toycar.glb", tmp_path, render=False)
    g = res["grade"]
    assert g["viewTransform"] == "AgX" and g["look"] == "AgX - Medium High Contrast"  # premium_dark
    for node in ("exposure", "lgg", "separation_mix", "bloom", "vignette"):
        assert node in g["nodes"], node
    assert g["objectIndexPass"] is True and g["subjectPassIndex"] == 1
    assert res["built"][-1] == "grade:mood_grade"
    assert g["invalidLinks"] == []


T3_PROBE = [1, 60, 61, 105, 106, 165, 166, 210, 211, 256, 300]  # both ends of every shot


def test_haze_domain_faces_are_never_seen_by_the_camera(tmp_path):
    """Every sampled camera ray (a grid over the frame) must hit a camera-visible surface before it
    leaves the haze box; a ray that leaves first shows the box's face as a hard haze edge."""
    prof = _profile("toycar")
    res = compile_scene(_script("script_t3.json"), prof, MODELS / "toycar" / "toycar.glb", tmp_path,
                        render=False, skip_kinds=("grade",), probe=T3_PROBE)
    for f in T3_PROBE:
        pr = res["probe"][str(f)]
        assert pr["rays"] >= 100
        assert pr["hazeFaceRays"] == 0, (f, pr["hazeFaceRays"])


def _hero_frame(tmp, skip=()):
    import numpy as np
    from PIL import Image
    prof = _profile("toycar")
    compile_scene(_script("script_t3.json"), prof, MODELS / "toycar" / "toycar.glb", tmp, tier="keyframes",
                  frames=[256], skip_kinds=skip)
    rgb = np.asarray(Image.open(tmp / "beauty" / "0256.png").convert("RGB"), dtype=np.float32)
    mask = np.asarray(Image.open(next((tmp / "passes").glob("mask*0256*.png"))).convert("L")) > 127
    return rgb.mean(axis=2), mask


def test_haze_is_subtle_atmosphere_not_fog(tmp_path):
    """script_t3 (density 0.2, black cyc, premium_dark) on the hero frame: haze lifts the frame a
    little and leaves the subject's contrast alone. Before the fix it lifted 86/255 to ~200/255.
    The band is an absolute 8-bit lift: haze glows with the lights, not with the floor, so a ratio
    to the haze-off frame moved when the black floor stopped rendering near-white (2026-09-24: the
    old 1.02-1.15 ratio on an 86/255 frame is this same +2..+13 band)."""
    on, mask = _hero_frame(tmp_path / "on")
    off, _ = _hero_frame(tmp_path / "off", skip=("effect",))
    lift = on.mean() - off.mean()
    assert 2.0 <= lift <= 13.0, (on.mean(), off.mean())
    assert mask.any() and on[mask].std() >= 0.85 * off[mask].std()


def test_every_camera_key_clears_the_subject_and_sees_its_detail_target(tmp_path):
    prof = _profile("toycar")
    res = compile_scene(_script("script_t3.json"), prof, MODELS / "toycar" / "toycar.glb", tmp_path,
                        render=False, skip_kinds=("grade",))
    c = res["clearance"]
    assert c["violations"] == []
    assert c["keys"] >= 300 and c["detailKeys"] >= 90
    assert c["minSurfaceM"] > 10 * c["clipStartM"]  # nothing the camera sees is ever clipped
    assert c["maxApertureM"] < 0.25 * c["minSurfaceM"]  # the lens disc stays well clear of geometry


def test_a_detail_target_hidden_behind_the_subject_fails_the_compile(tmp_path):
    """A marker on the car's far flank, shot from the near side: the checker's box test passes
    (the camera is outside the bounds) but the line of sight runs through the body."""
    from engine.compiler.run import CheckFailed
    s = _script("script_t3.json")
    s["markers"] = [{"id": "far", "text": "far-side trim",
                     "anchor": {"space": "placed", "point": [-0.002, 0.018, 0.020], "normal": [0, -1, 0]}}]
    s["shots"][1]["target"] = {"marker": "far"}
    s["shots"][1]["camera"]["params"].update({"move": "push", "azimuthOffsetDeg": 0, "elevationOffsetDeg": 5,
                                              "distance": 1.5})
    with pytest.raises(RuntimeError, match="camera clearance.*detail target hidden"):
        compile_scene(s, _profile("toycar"), MODELS / "toycar" / "toycar.glb", tmp_path, render=False,
                      skip_kinds=("grade",))


def test_the_macro_detail_frame_is_sharp(tmp_path):
    """Frame 94 (shot 2, macro_detail on the toycar): mean gradient of the graded frame. At the
    f/2.8 the director asked (a 36 mm aperture 25 mm from the car) it measured 1.75; stopped down
    for the set's scale, 10.6 (no-DoF reference 11.8), both at 180x320."""
    import numpy as np
    from PIL import Image
    prof = _profile("toycar")
    compile_scene(_script("script_t3.json"), prof, MODELS / "toycar" / "toycar.glb", tmp_path, tier="keyframes",
                  frames=[94])
    a = np.asarray(Image.open(tmp_path / "beauty" / "0094.png").convert("L"), dtype=np.float32)
    grad = np.hypot(np.diff(a, axis=1)[:-1], np.diff(a, axis=0)[:, :-1]).mean()
    assert grad > 5.0, grad
