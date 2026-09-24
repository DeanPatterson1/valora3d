import json
from pathlib import Path

import pytest

from engine.catalog import Catalog, CatalogError
from engine.checker import check
from engine.compiler.context import block_seed, hero_pose
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"
CAT = Catalog.load()
CAR = SubjectProfile.from_dict(json.loads((FIX / "profile_car.json").read_text()))


def _write(root, kind, bid, build_src=None):
    d = root / kind / bid
    d.mkdir(parents=True)
    (d / "block.json").write_text(json.dumps({
        "id": bid, "kind": kind, "description": "x", "params": {}, "subjectSizeM": [0.1, 1.0],
        "aspects": ["9:16"], "costWeight": 1.0, "tags": {"mood": [], "energy": [], "palette": []},
        "tierMax": "T2"}))
    if build_src is not None:
        (d / "build.py").write_text(build_src)


def test_load_builder(tmp_path):
    _write(tmp_path, "world", "w", "def build(ctx):\n    return 'built'\n")
    assert Catalog.load(tmp_path).load_builder("world", "w")(None) == "built"


@pytest.mark.parametrize("bid", ["nope", "../world/w", "", "a/b"])
def test_load_builder_rejects_unknown_or_unsafe(tmp_path, bid):
    _write(tmp_path, "world", "w", "def build(ctx):\n    pass\n")
    with pytest.raises(CatalogError):
        Catalog.load(tmp_path).load_builder("world", bid)


def test_load_builder_missing_file_or_function(tmp_path):
    _write(tmp_path, "world", "a")
    _write(tmp_path, "world", "b", "x = 1\n")
    cat = Catalog.load(tmp_path)
    with pytest.raises(CatalogError, match="build.py"):
        cat.load_builder("world", "a")
    with pytest.raises(CatalogError, match="build"):
        cat.load_builder("world", "b")


def test_block_seed_is_deterministic_and_per_block():
    assert block_seed(7, "lighting", "reflection_rig") == block_seed(7, "lighting", "reflection_rig")
    assert block_seed(7, "lighting", "reflection_rig") != block_seed(8, "lighting", "reflection_rig")
    assert block_seed(7, "lighting", "reflection_rig") != block_seed(7, "effect", "haze_volume")


def test_hero_pose_is_mid_last_hero_shot():
    s = check(json.loads((FIX / "script_valid.json").read_text()), CAR, CAT).script
    sample = CAT.load_camera_path("arc_orbit")
    assert hero_pose(s, CAR, CAT) == sample(s["shots"][1]["camera"]["params"], CAR, 0.5, None)
