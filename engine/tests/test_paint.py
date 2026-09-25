"""Art pass round 4: the compile job's paint override (engine/paint.py host side, engine/blender/paint.py)."""
import pytest

from engine.paint import FINISHES, PaintError, validate_paint
from engine.tests.conftest import requires_blender


def test_no_paint_means_no_override():
    assert validate_paint(None) is None


@pytest.mark.parametrize("finish", FINISHES)
def test_a_clean_paint_is_normalised_to_linear_floats(finish):
    p = validate_paint({"color": "#0A0A0B", "finish": finish})
    assert p["color"] == "#0a0a0b" and p["finish"] == finish
    assert all(isinstance(c, float) and 0.0 <= c < 0.01 for c in p["linear"])


def test_finish_defaults_to_gloss_and_white_is_linear_one():
    assert validate_paint({"color": "#ffffff"}) == {"color": "#ffffff", "linear": [1.0, 1.0, 1.0], "finish": "gloss"}


@pytest.mark.parametrize("bad", [
    "#000000", ["#000000"], {}, {"finish": "gloss"}, {"color": "000000"}, {"color": "#00000"},
    {"color": "#0000000"}, {"color": "#GG0000"}, {"color": "red"}, {"color": 0x000000},
    {"color": "#000000\n"}, {"color": "#000000; import os"}, {"color": " #000000"},
    {"color": "#000000", "finish": "chrome"}, {"color": "#000000", "finish": None},
    {"color": "#000000", "finish": "gloss", "extra": 1}, {"color": "#000000", "__class__": "x"},
    {"color": None}])
def test_hostile_paint_is_refused(bad):
    with pytest.raises(PaintError):
        validate_paint(bad)


@pytest.mark.blender
@requires_blender
def test_paint_override_rebuilds_the_paint_material_and_only_it(tmp_path):
    from engine.compiler.run import compile_scene
    from engine.tests.test_blocks_phase5_blender import T3, _glb
    from engine.tests.test_director_package import _p
    import copy
    glb = _glb("sports_car")
    s = copy.deepcopy(T3)
    base = compile_scene(s, _p("sports_car"), glb, tmp_path / "a", render=False, skip_kinds=("grade",))
    assert "paint" not in base and base["uploadMaterials"]["before"] == base["uploadMaterials"]["after"]
    res = compile_scene(s, _p("sports_car"), glb, tmp_path / "b", render=False, skip_kinds=("grade",),
                        paint={"color": "#0a0a0b", "finish": "gloss"})
    rep = res["paint"]
    assert rep["materials"] == ["mv-body-paint"] and rep["finish"] == "gloss"
    sh = rep["shaders"]["valora_paint_gloss"]
    assert sh["baseColor"] == pytest.approx(validate_paint({"color": "#0a0a0b"})["linear"], abs=1e-5)
    assert (sh["metallic"], sh["specular"], sh["coat"]) == (0.0, 0.15, 1.0)
    assert sh["coatNormal"] is True and sh["baseLinked"] is False
    assert res["uploadMaterials"]["before"] != res["uploadMaterials"]["after"]    # the override is the change
