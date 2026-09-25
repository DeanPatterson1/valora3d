"""Phase 5 Task 56: the checker frames a moving subject with engine/motion_path (fixture motion test_glide)."""
import copy
import json
import shutil
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.compiler.timeline import camera_keys
from engine.director.rulebook import EXAMPLES_DIR
from engine.motion_path import IDENTITY, SubjectPose, is_moving
from engine.profile import SubjectProfile
from engine.tests.realism_catalog import catalog_with_fixtures
from engine.tests.test_director_package import _p

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def glide_catalog(tmp_path_factory):
    return catalog_with_fixtures(tmp_path_factory.mktemp("glide"))


@pytest.fixture
def watch():
    return _p("pocket_watch")


def glide_script(camera="low_hero_push", distance=4.0, azimuth=None, world="test_street", metres=3.0, target=None,
                 **cam):
    s = json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))
    s["world"] = {"id": world, "params": {}}
    s["subject"]["motion"] = {"id": "test_glide", "params": {"metres": metres}}
    params = {"distance": distance, **cam}
    if azimuth is not None:
        params["azimuthDeg"] = azimuth
    s["shots"] = [{"startS": 0, "endS": 10, "camera": {"id": camera, "params": params}, "focus": "subject"}]
    if target is not None:
        s["shots"][0]["target"] = target
    return s


def _frozen_scripts():
    out = []
    for f in sorted(EXAMPLES_DIR.glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        out.append(doc.get("script", doc))
    out.append(json.loads((FIX / "script_valid.json").read_text(encoding="utf-8")))
    return out


def test_static_scripts_check_exactly_as_before(tmp_path):
    """static now has a path.py (the identity pose): every example script and the valid fixture give a
    byte-identical CheckResult against a catalog whose static block has no path.py."""
    cat = Catalog.load()
    root = tmp_path / "blocks"
    shutil.copytree(cat.root, root, ignore=shutil.ignore_patterns("__pycache__"))
    (root / "motion" / "static" / "path.py").unlink()
    old = Catalog.load(root)
    for name in ("pocket_watch", "sports_car", "mid_century_lounge_chair"):
        p = _p(name)
        for s in _frozen_scripts():
            a, b = check(copy.deepcopy(s), p, cat), check(copy.deepcopy(s), p, old)
            assert not is_moving(a.script, p, cat)
            assert a.ok == b.ok and a.script == b.script
            assert [i.to_dict() for i in a.issues] == [i.to_dict() for i in b.issues]
            assert all(i.code != "subject_left_frame" for i in a.issues)


def test_a_glide_that_stays_framed_passes(glide_catalog):
    r = check(glide_script(camera="arc_orbit", distance=6.0, metres=0.5), _p("sports_car"), glide_catalog)
    assert r.ok, [i.to_dict() for i in r.issues if i.severity == "error"]


def test_moving_subject_leaving_an_anchor_frame_is_repaired_or_rejected(glide_catalog, watch):
    s = glide_script(camera="low_hero_push", distance=1.3)   # tight, so a 3 m glide leaves frame
    r = check(s, watch, glide_catalog)
    codes = {i.code for i in r.issues}
    assert "camera_distance_adjusted" in codes or "subject_left_frame" in codes
    assert "framing_unfixable" not in codes


def test_camera_inside_a_moving_subject_is_caught(glide_catalog):
    car = _p("sports_car")
    s = glide_script(camera="low_hero_push", distance=1.2, azimuth=90.0, metres=6.0)  # the glide drives through the camera
    r = check(s, car, glide_catalog)
    assert not r.ok or any(i.code == "camera_distance_adjusted" for i in r.issues)


def test_path_leaving_the_world_is_an_error(glide_catalog, watch):
    s = glide_script(world="studio_cyc", metres=40.0)   # studio driveLaneM 0 -> no travel allowed
    r = check(s, watch, glide_catalog)
    assert "path_through_world" in {i.code for i in r.issues if i.severity == "error"} and not r.ok


def test_travel_inside_the_lane_is_allowed(glide_catalog, watch):
    r = check(glide_script(world="test_street", metres=20.0, distance=8.0), watch, glide_catalog)
    assert "path_through_world" not in {i.code for i in r.issues}


def test_a_motion_with_a_distance_param_is_capped_not_rejected(tmp_path, watch):
    cat = catalog_with_fixtures(tmp_path)
    mf = Path(cat.root) / "motion" / "test_glide" / "block.json"
    m = json.loads(mf.read_text(encoding="utf-8"))
    m["distanceParam"] = "metres"
    mf.write_text(json.dumps(m), encoding="utf-8")
    cat = Catalog.load(cat.root)
    r = check(glide_script(world="test_street", metres=45.0, distance=8.0), watch, cat)
    capped = [i for i in r.issues if i.code == "motion_travel_capped"]
    assert capped and capped[0].severity == "repaired"
    assert r.script["subject"]["motion"]["params"]["metres"] <= 30.0 + 1e-9
    assert "path_through_world" not in {i.code for i in r.issues}


def test_bad_distance_param_is_a_catalog_error(tmp_path):
    from engine.catalog import CatalogError
    cat = catalog_with_fixtures(tmp_path)
    mf = Path(cat.root) / "motion" / "test_glide" / "block.json"
    m = json.loads(mf.read_text(encoding="utf-8"))
    m["distanceParam"] = "nope"
    mf.write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(CatalogError, match="distanceParam"):
        Catalog.load(cat.root)


def test_detail_shot_aim_follows_a_glide(glide_catalog, watch):
    """Amendment (Task 56): focus distance and the detail target use the posed subject at each frame."""
    s = glide_script(camera="macro_detail", distance=0.6, metres=0.05, target={"detail": 0}, move="push")
    r = check(s, watch, glide_catalog)
    keys = [k for k in camera_keys(r.script, watch, glide_catalog) if 1 <= k.frame <= 300]
    first, last = keys[0], keys[-1]
    d = watch.detailPoints[0]["point"]
    assert first.target[0] == pytest.approx(d[0], abs=1e-6)
    assert last.target[0] == pytest.approx(d[0] + 0.05, abs=1e-3)       # the live target glided with it
    # an anchor camera aims at the mid-shot pose (a push looks straight at it), so its aim stays put
    assert first.pose.target == pytest.approx(last.pose.target, abs=1e-9)
    assert first.pose.target[0] == pytest.approx(d[0] + 0.025, abs=2e-3)


def test_static_timeline_keys_are_unchanged(glide_catalog, watch):
    s = check(json.loads((FIX / "script_valid.json").read_text(encoding="utf-8")), watch, glide_catalog).script
    old = Catalog.load()
    assert camera_keys(s, watch, glide_catalog) == camera_keys(s, watch, old)


def test_identity_pose_is_the_rest_pose():
    assert IDENTITY == SubjectPose()
