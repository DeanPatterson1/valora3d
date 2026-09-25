"""Art pass 2026-09-25: golden_field and night_street built from pinned CC0 assets (photo sky, photoscanned
tufts, far grass, tree stands; facade kit, room cards, lantern posts, far street) and still building their
procedural selves with an empty library. Compile only (no render)."""
import pytest

from engine.compiler.run import compile_scene
from engine.tests.conftest import requires_blender
from engine.tests.test_blocks_phase5_blender import _glb, field_script, street_script
from engine.tests.test_director_package import _p

pytestmark = [pytest.mark.blender, requires_blender]


def _library(library, tmp_path, monkeypatch):
    from engine.assets import LIBRARY, LIBRARY_ENV
    if library == "empty":
        monkeypatch.setenv(LIBRARY_ENV, str(tmp_path / "no_assets"))
    elif not (LIBRARY / "polyhaven" / "magalies_field_sunset_4k.hdr").exists():
        pytest.skip("art-pass assets not fetched (docs/superpowers/plans/world-assets-wishlist.md)")


@pytest.mark.parametrize("library", ["pinned", "empty"])
def test_golden_field_photo_set_and_its_fallback(library, tmp_path, monkeypatch):
    _library(library, tmp_path, monkeypatch)
    p = _p("sports_car")
    res = compile_scene(field_script("golden", wind=3.0), p, _glb("sports_car"), tmp_path / "c", render=False,
                        skip_kinds=("grade",), realism_probe=[1])
    f = res["field"]
    pinned = library == "pinned"
    assert (f["hdri"], f["photoGround"], f["farGrass"], f["farMeadow"]) == (pinned,) * 4
    assert f["horizonRing"] is (not pinned) and (f["tufts"] > 0) is pinned and (f["trees"] > 0) is pinned
    assert f["bladeRootSwayMax"] == pytest.approx(0.0, abs=1e-6)
    assert [o["name"] for o in res["objects"] if o["foliage"]] == ["valora_field_blades"]   # ONE swaying mesh
    assert [o["name"] for o in res["objects"] if o["ground"]] == ["valora_field_ground"]
    assert res["realismProbe"]["1"]["foliageInSubject"] == 0
    assert f["foliageVerts"] <= 2_300_000                    # the probe walks every foliage edge
    assert all(o["block"] == "world/golden_field" for o in res["objects"] if o["name"].startswith("valora_field"))


@pytest.mark.parametrize("library", ["pinned", "empty"])
def test_night_street_kit_set_and_its_fallback(library, tmp_path, monkeypatch):
    _library(library, tmp_path, monkeypatch)
    p = _p("sports_car")
    res = compile_scene(street_script("night"), p, _glb("sports_car"), tmp_path / "c", render=False,
                        skip_kinds=("grade",))
    st = res["street"]
    pinned = library == "pinned"
    assert (st["photoSky"], st["facadeKit"], st["pavingMaps"]) == (pinned,) * 3
    assert (st["kitPieces"] > 0, st["rooms"] > 0, st["farBlocks"] > 0) == (pinned,) * 3
    assert st["lampModels"] == (st["lampPosts"] if pinned else 0)
    lights = [o for o in res["objects"] if o["type"] == "LIGHT" and o["block"] == "world/night_street"]
    assert len(lights) == st["lamps"]                        # far lanterns and signs glow, they are not lights
    assert st["windowsLit"] <= (st["rooms"] if pinned else 10 ** 6)
    assert st["neonAllEmissive"] is True and st["camerasInsideProps"] == 0 and st["propVertsInExclusion"] == 0
    assert res["clearance"]["violations"] == []
    assert all(o["block"] is not None for o in res["objects"] if o["name"].startswith("valora_street"))
