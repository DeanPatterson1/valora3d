import json
import math
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
    assert res["built"] == ["world:studio_cyc", "field:wind", "motion:static", "lighting:softbox_three_point",
                            "realism:contact_ground"]


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


T3_ATTEMPT = Path(__file__).resolve().parents[2] / "harness" / "suites" / "v0" / "t3_attempt.json"
REFERENCE_MODELS = sorted(p.stem for p in (FIX / "profiles").glob("*.json"))


@pytest.mark.parametrize("model", REFERENCE_MODELS)
def test_t3_attempt_compiles_on_every_reference_model(model, tmp_path):
    """The harness's known-good script must pass Blender's camera-clearance guard on every
    reference subject. It failed 'detail target hidden' on 8 of 9 (2026-09-24): ingest picked
    detail points inside wheel arches, cavities and under ledges, and aimed the macro camera
    along a cluster-mean normal that could point through the part."""
    glb = MODELS / model / f"{model}.glb"
    if not glb.exists():
        pytest.skip(f"{model} not present")
    res = compile_scene(json.loads(T3_ATTEMPT.read_text(encoding="utf-8")), _profile(model), glb, tmp_path,
                        render=False, skip_kinds=("grade",))
    assert res["clearance"]["violations"] == [] and res["clearance"]["detailKeys"] >= 90


def test_play_clip_moves_the_subject_over_the_video(tmp_path):
    from engine.ingest.run import ingest
    from engine.tests.blender_fixtures import make_glb
    glb = make_glb("rigged", tmp_path / "rigged.glb")
    prof = ingest(glb, workdir=tmp_path / "w")
    s = json.loads(T3_ATTEMPT.read_text(encoding="utf-8"))
    s["subject"]["motion"] = {"id": "play_clip", "params": {"clip": 0, "speed": 1.0}}
    # Phase math: the clip spans frames 1-24 (23 frames) at the 24 fps it imported at; the video is 30 fps,
    # so one pass takes 23 * 30 / 24 = 28.75 video frames. The swing ends 90 degrees from where it starts
    # (not seamless), so mode auto plays it forwards then backwards: period 57.5 frames. Frames 10 and
    # 125 = 10 + 2 * 57.5 are the same phase; 40 (pass 1, reversed) and 280 (pass 9, reversed, 0.70 in)
    # are not, and neither is 1.
    frames = [1, 10, 40, 125, 280]
    res = compile_scene(s, prof, glb, tmp_path / "out", tier="keyframes", frames=[1], render=False, probe=frames)
    b = {f: res["probe"][str(f)]["subjectBounds"] for f in frames}
    assert b[1] != b[40] and b[40] != b[280]   # the clip plays and keeps moving to the end of the video
    assert b[10][0] + b[10][1] == pytest.approx(b[125][0] + b[125][1], abs=1e-5)  # one period later: same pose


def test_static_motion_holds_the_ingest_pose_all_video(tmp_path):
    """Review 2026-09-25: an imported action left active played once and held its LAST pose, so a
    'static' subject rendered a pose ingest never measured. rest_animation holds the frame-1 pose."""
    from engine.ingest.run import ingest
    from engine.tests.blender_fixtures import make_glb
    glb = make_glb("rigged", tmp_path / "rigged.glb")
    prof = ingest(glb, workdir=tmp_path / "w")
    s = json.loads(T3_ATTEMPT.read_text(encoding="utf-8"))
    assert s["subject"]["motion"]["id"] == "static"
    res = compile_scene(s, prof, glb, tmp_path / "out", tier="keyframes", frames=[1], render=False,
                        probe=[1, 40, 280])
    placed = res["placedBounds"]
    for f in (1, 40, 280):
        got = res["probe"][str(f)]["subjectBounds"]
        assert got[0] + got[1] == pytest.approx(placed, abs=1e-6), f


def test_play_clip_index_matches_ingest_when_a_pose_stub_comes_first(tmp_path):
    """A 1-frame pose stub ahead of the real clip: ingest drops it (engine.clips.clip_kept) and so must
    play_clip, or 'clip 0' would play the stub and the subject would never move."""
    from engine.ingest.run import ingest
    from engine.tests.blender_fixtures import make_glb
    glb = make_glb("two_actions", tmp_path / "two.glb")
    prof = ingest(glb, workdir=tmp_path / "w")
    assert [(c["index"], c["nameHint"], c["seamless"]) for c in prof.animationClips] == [(0, "Swing", False)]
    s = json.loads(T3_ATTEMPT.read_text(encoding="utf-8"))
    s["subject"]["motion"] = {"id": "play_clip", "params": {"clip": 0, "mode": "loop"}}
    res = compile_scene(s, prof, glb, tmp_path / "out", tier="keyframes", frames=[1], render=False,
                        probe=[1, 15])
    assert res["probe"]["1"]["subjectBounds"] != res["probe"]["15"]["subjectBounds"]


def _walker_script(prof):
    """t3_attempt on the walker. The cube has no detail points, so its macro shots aim at the surface point
    facing the camera (targets.surface_point): the bbox centre would sit inside the solid cube."""
    assert not prof.detailPoints
    return json.loads(T3_ATTEMPT.read_text(encoding="utf-8"))


def test_a_root_motion_walk_loops_in_place_without_a_jump(tmp_path):
    """Independent review P1: seamless() leaves location channels out, so a walk whose root travels reads as
    seamless and auto loops it; without the root's travel taken out each cycle would teleport it back 1 m.
    Ingest records rootMotion; play_clip loops it in place, keeping the vertical bob."""
    from engine.clips import CLIP_MAP_VERSION
    from engine.ingest.run import ingest
    from engine.tests.blender_fixtures import make_glb
    glb = make_glb("walker", tmp_path / "walker.glb")
    prof = ingest(glb, workdir=tmp_path / "w")
    [clip] = prof.animationClips
    assert clip["rootMotion"] is True and clip["seamless"] is True and clip["clipMapVersion"] == CLIP_MAP_VERSION
    swing = ingest(make_glb("rigged", tmp_path / "rigged.glb"), workdir=tmp_path / "r")
    assert swing.animationClips[0]["rootMotion"] is False               # limbs move, the root stays
    s = _walker_script(prof)
    s["subject"]["motion"] = {"id": "play_clip", "params": {"clip": 0}}
    # the clip spans frames 1-25 at 24 fps; at 30 fps one pass is 30 video frames: seams at 31, 61, 91
    frames = [1, 16, 30, 31, 61, 91]
    res = compile_scene(s, prof, glb, tmp_path / "out", tier="keyframes", frames=[1], render=False, probe=frames)
    b = {f: res["probe"][str(f)]["subjectBounds"] for f in frames}
    mid = {f: [(lo + hi) / 2 for lo, hi in zip(b[f][0][:2], b[f][1][:2])] for f in frames}
    scale = prof.scaleFactor
    for f in frames:                                                     # stays where it started
        assert math.dist(mid[f], mid[1]) < 1e-3 * scale, (f, mid[f], mid[1])
    assert math.dist(mid[31], mid[30]) < 1e-3 * scale                    # no jump at the seam
    assert b[16][0][2] - b[1][0][2] > 0.02 * scale                       # the bob is kept


def test_an_in_place_walk_is_centred_and_framed_on_its_in_place_bounds(tmp_path):
    """A root-motion clip loops in place, so ingest's posed bounds (placement centre, framing size) are
    measured in place too: bounds over the 1 m travel would park the walker half its travel off-centre
    and frame a box 6x its width. The subject's centre sits on the placement origin (XY 0,0) all loop."""
    from engine.ingest.run import ingest
    from engine.tests.blender_fixtures import make_glb
    glb = make_glb("walker", tmp_path / "walker.glb")
    prof = ingest(glb, workdir=tmp_path / "w")
    assert prof.animationClips[0]["rootMotion"] is True
    size = max(prof.sizeM)
    assert prof.sizeM[0] < 1.5 * prof.sizeM[1], prof.sizeM              # the travel is not in the box
    s = _walker_script(prof)
    s["subject"]["motion"] = {"id": "play_clip", "params": {"clip": 0, "mode": "loop"}}
    last = int(s["format"]["durationS"] * s["format"]["fps"])
    frames = [1, last // 2, last]
    res = compile_scene(s, prof, glb, tmp_path / "out", tier="keyframes", frames=[1], render=False, probe=frames)
    for f in frames:
        lo, hi = res["probe"][str(f)]["subjectBounds"]
        mid = [(a + b) / 2 for a, b in zip(lo[:2], hi[:2])]
        assert math.hypot(*mid) < 0.05 * size, (f, mid, size)


def test_a_walk_played_once_stays_inside_the_volume_it_was_framed_on(tmp_path):
    """Gap after 32a7801: a root-motion clip played once (or ping-ponged) is not taken in place, so it walks out
    of the in-place box ingest measured. The checker and compiler frame the box swept along the clip's travel
    (rootTravelM x the share of a pass played): the subject stays inside it at every probe frame. The macro
    shots, with no detail point, aim at the cube's surface and pass Blender's camera clearance."""
    from engine.clips import swept_profile
    from engine.ingest.run import ingest
    from engine.targets import resolve_target
    from engine.tests.blender_fixtures import make_glb
    glb = make_glb("walker", tmp_path / "walker.glb")
    prof = ingest(glb, workdir=tmp_path / "w")
    clip = prof.animationClips[0]
    assert clip["rootMotion"] is True and math.hypot(*clip["rootTravelM"]) > 0.5 * max(prof.sizeM)
    size = max(prof.sizeM)
    s = _walker_script(prof)
    s["subject"]["motion"] = {"id": "play_clip", "params": {"clip": 0, "mode": "once"}}
    for shot in s["shots"]:
        if shot["camera"]["id"] == "macro_detail":
            tgt = resolve_target(shot, prof, [])
            near = min(math.dist(tgt.point, q) for q in prof.surfaceSamples)
            assert tgt.source == "surface" and near < 0.01 * size, (tgt, near)
    framed = swept_profile(prof, {**s, "subject": {**s["subject"], "motion": {
        "id": "play_clip", "params": {"clip": 0, "mode": "once", "speed": 1.0, "offsetS": 0.0}}}})
    assert framed is not prof and max(framed.sizeM) > 1.5 * size
    last = int(s["format"]["durationS"] * s["format"]["fps"])
    frames = [1, 8, 16, 24, 30, last // 2, last]
    res = compile_scene(s, prof, glb, tmp_path / "out", tier="keyframes", frames=[1], render=False, probe=frames)
    assert not res["clearance"]["violations"]
    job = json.loads((tmp_path / "out" / "job.json").read_text(encoding="utf-8"))
    assert job["profile"]["boundsMax"] == framed.boundsMax and job["profile"]["boundsMin"] == framed.boundsMin
    tol = 0.02 * size
    moved = False
    for f in frames:
        lo, hi = res["probe"][str(f)]["subjectBounds"]
        assert all(a >= b - tol for a, b in zip(lo, framed.boundsMin)), (f, lo, framed.boundsMin)
        assert all(a <= b + tol for a, b in zip(hi, framed.boundsMax)), (f, hi, framed.boundsMax)
        moved |= any(a < b - tol for a, b in zip(lo, prof.boundsMin)) or             any(a > b + tol for a, b in zip(hi, prof.boundsMax))
    assert moved   # the walk really leaves the in-place box, so the sweep is what keeps it framed


def test_valora_motion_keys_equal_the_pure_subject_pose(tmp_path):
    """Phase 5 Task 56: the compiler keys valora_motion from engine.motion_path.subject_pose, so the
    evaluated transform at frames 1, mid and last maps placed points exactly as the pure pose does."""
    from engine.motion_path import apply, subject_pose
    from engine.tests.realism_catalog import catalog_with_fixtures
    glb = MODELS / "pocket_watch" / "pocket_watch.glb"
    if not glb.exists():
        pytest.skip("model not present")
    prof, cat = _profile("pocket_watch"), catalog_with_fixtures(tmp_path / "cat")
    s = _script()
    s["world"] = {"id": "test_street", "params": {}}
    s["subject"]["motion"] = {"id": "test_glide", "params": {"metres": 0.04, "yawDeg": 60.0}}
    s = check(s, prof, cat).script
    frames = [1, 150, 300]
    res = compile_scene(s, prof, glb, tmp_path / "c", render=False, catalog=cat,
                        skip_kinds=("lighting", "effect", "realism", "grade"), probe=frames)
    fps = s["format"]["fps"]
    pts = [tuple(prof.boundsMin), tuple(prof.boundsMax), (0.01, -0.02, 0.05)]
    for f in frames:
        m = res["probe"][str(f)]["motionMatrix"]
        pose = subject_pose(s, prof, cat, (f - 1) / fps)
        for p in pts:
            got = [sum(m[r][c] * v for c, v in enumerate(p)) + m[r][3] for r in range(3)]
            assert got == pytest.approx(list(apply(p, pose, prof)), abs=1e-5), (f, p)
    assert res["probe"]["300"]["motionMatrix"] != res["probe"]["1"]["motionMatrix"]
    assert not res["clearance"]["violations"]
