import sys

from engine.catalog import Catalog

BUILDABLE = ("world", "lighting", "motion", "effect", "grade", "realism", "field")


def test_every_buildable_block_has_a_build_py_that_loads_without_bpy():
    cat = Catalog.load()
    for kind in BUILDABLE:
        for bid in cat.ids(kind):
            assert callable(cat.load_builder(kind, bid)), f"{kind}/{bid}"
    assert "bpy" not in sys.modules  # build.py must import bpy inside build()


def test_every_camera_has_a_path_and_a_move_primitive():
    cat = Catalog.load()
    for bid in cat.ids("camera"):
        assert callable(cat.load_camera_path(bid))
        assert cat.get("camera", bid).get("move"), bid  # T3-11
