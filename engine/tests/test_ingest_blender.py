import os
from pathlib import Path
import pytest
from engine.ingest.run import BLENDER, ingest

MODELS = Path(__file__).resolve().parents[2] / "assets-in" / "models"

pytestmark = [pytest.mark.blender, pytest.mark.skipif(not os.path.exists(BLENDER), reason="Blender not installed")]


@pytest.mark.parametrize("glb", ["pocket_watch/pocket_watch.glb", "toycar/toycar.glb"])
def test_ingest_real_models(glb, tmp_path):
    path = MODELS / glb
    if not path.exists():
        pytest.skip(f"{glb} not present")
    p = ingest(path, workdir=tmp_path)
    assert 0.02 <= p.longest <= 30
    assert p.boundsMin[2] == 0.0
    assert p.polyCount > 0
    assert p.materials, "expected at least one classified material"


def test_textured_materials_are_read_not_defaulted(tmp_path):
    # Both models drive material values through textures (glTF metallicRoughness /
    # emissive maps). Reading socket defaults instead of the textures classified the
    # watch's metal body as matte and the toy car's body as emissive (plan review 2026-09-24).
    watch = MODELS / "pocket_watch/pocket_watch.glb"
    car = MODELS / "toycar/toycar.glb"
    if not (watch.exists() and car.exists()):
        pytest.skip("models not present")
    w = ingest(watch, workdir=tmp_path / "w")
    assert w.materials[0]["class"] == "metal", w.materials
    c = ingest(car, workdir=tmp_path / "c")
    assert not any(m["class"] == "emissive" and m["share"] > 0.2 for m in c.materials), c.materials


def _run_in_blender(expr):
    import subprocess
    from engine.ingest.run import EXTRACT
    code = (f"import importlib.util, sys\n"
            f"spec = importlib.util.spec_from_file_location('bx', r'{EXTRACT}')\n"
            f"bx = importlib.util.module_from_spec(spec); spec.loader.exec_module(bx)\n" + expr)
    return subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                           "--python-expr", code], capture_output=True, text=True, timeout=300)


def test_image_mean_refuses_huge_images_and_bounds_use_foreach_get():
    # A >4096^2 texture would allocate a multi-GB float buffer just to average it;
    # untrusted uploads must not get to do that. Importing the extractor must not run it.
    proc = _run_in_blender(
        "import bpy\n"
        "big = bpy.data.images.new('big', 4097, 4096)\n"
        "small = bpy.data.images.new('small', 64, 64)\n"
        "small.pixels.foreach_set([0.5] * (64 * 64 * 4))\n"
        "assert bx._image_mean(big, None) is None\n"
        "assert abs(bx._image_mean(small, 0) - 0.5) < 1e-2  # byte image: 128/255\n"
        "bpy.ops.mesh.primitive_cube_add(size=2, location=(1, 2, 3))\n"
        "o = bpy.context.object\n"
        "lo, hi = bx._mesh_bounds(o.data)\n"
        "assert list(lo) == [-1, -1, -1] and list(hi) == [1, 1, 1], (lo, hi)\n"
        "print('BX-OK')\n")
    assert proc.returncode == 0 and "BX-OK" in proc.stdout, proc.stdout[-1500:] + proc.stderr[-1500:]


from engine.tests.blender_fixtures import make_glb


def test_rigged_subject_uses_posed_bounds(tmp_path):
    # At rest the 0.2 m cube sits on the bone at z 0.7-0.9. By frame 24 the bone has swung
    # 90 degrees and carried the cube out to |y| ~ 0.8. Rest-only bounds would frame a
    # 0.2 m-wide subject and the render would cut the swing off (phase-1 final review).
    p = ingest(make_glb("rigged", tmp_path / "rigged.glb"), workdir=tmp_path / "w")
    assert p.boundsPosed is True
    assert p.sizeM[1] > 0.6, p.sizeM


@pytest.mark.xfail(strict=True, reason="detectors land in Tasks 7-8")
def test_details_glb_yields_samples_targets_and_an_emissive_detail(tmp_path):
    p = ingest(make_glb("details", tmp_path / "d.glb"), workdir=tmp_path / "w")
    assert p.glossShare > 0.9
    assert any(t["kind"] == "top" for t in p.reflectionTargets)
    em = [d for d in p.detailPoints if d["kind"] == "emissive"]
    assert em, p.detailPoints
    # The lamp was modelled at Blender (0.3, -0.501, 0.8); placement centres XY, so check
    # the side (-y face) and the height rather than exact x.
    assert em[0]["point"][1] < -0.4 and abs(em[0]["point"][2] - 0.8) < 0.08
    assert len(p.parts) == 2
