import os
from pathlib import Path
import pytest
from engine.ingest.run import BLENDER, ingest

MODELS = Path(__file__).resolve().parents[2] / "assets-in" / "models"

pytestmark = pytest.mark.skipif(not os.path.exists(BLENDER), reason="Blender not installed")


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
