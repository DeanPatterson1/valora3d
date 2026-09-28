"""Phase 6 Task 111 (lane S): the library tool bakes a preset from Mantaflow (the tiny `_probe` preset, seconds)
into a temp library root, keeps only the flat VDB sequence, and pins a manifest row (temp manifest) that
engine/assets.resolve_sequence resolves, with the native facts place_vdb needs. The flame grid is present for a
fire preset and the density sum grows smoothly (sim_stable for gas)."""
import json
import shutil
import sys
from pathlib import Path

import pytest

from engine import assets as A
from engine.physics import gas as G
from engine.tests.conftest import requires_blender

pytestmark = [pytest.mark.blender, requires_blender]

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def baked(tmp_path_factory):
    sys.path.insert(0, str(ROOT / "tools"))
    import bake_vdb_library as L
    tmp = tmp_path_factory.mktemp("vdblib")
    man = tmp / "manifest.json"
    shutil.copy(A.MANIFEST, man)
    row = L.bake_preset("_probe", out_root=tmp / "lib" / "valora_vdb", manifest_path=man)
    return tmp, man, row


def test_the_preset_is_pinned_and_resolves(baked):
    tmp, man, row = baked
    doc = A.load_manifest(man)
    assert doc["assets"]["valora_vdb__probe"] == row
    seq = A.resolve_sequence("valora_vdb__probe", tmp / "lib", doc)
    assert len(seq["files"]) == G.PRESETS["_probe"]["frames"]
    assert [f.name for f in seq["files"]][0] == "fluid_data_0001.vdb"
    assert list((tmp / "lib" / "valora_vdb" / "_probe").glob("*.uni")) == []
    n = seq["native"]
    assert n["baseM"] == [0.5, 0.5, 0.0] and n["fps"] == G.LIBRARY_FPS and n["widthM"] == 1.0
    assert {"density", "flame", "velocity"} <= set(n["grids"])


def test_the_bake_is_stable(baked):
    tmp, _, _ = baked
    rep = json.loads((tmp / "lib" / "valora_vdb" / "_probe" / "bake_report.json").read_text(encoding="utf-8"))
    sums = [s["sum"] for s in rep["stats"]]
    assert all(s["finite"] for s in rep["stats"]) and max(sums) > 0
    assert G.growth_smooth(sums), sums
