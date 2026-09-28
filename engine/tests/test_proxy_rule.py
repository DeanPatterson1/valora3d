"""Phase 6 Task 97: the collision-shell voxel rules (pure). Every number is (eng; METHODS R5/R6) and sits in the
calibration register until T97's Blender test measures coverage and watertightness on 4 subjects."""
import pytest

from engine.physics.proxy import PURPOSES, max_hulls, max_tris, proxy_key, thickness_m, voxel_m
from engine.tests.test_director_package import _p


def test_voxel_rules_on_a_pocket_watch_clamp_to_the_floors():
    p = _p("pocket_watch")                                    # longest 0.0756 m
    assert voxel_m(p, "shell") == 0.001                       # 0.006 x 0.0756 = 0.00045 -> floor 1 mm
    assert voxel_m(p, "liquid") == 0.0008                     # 0.004 x 0.0756 = 0.0003 -> floor 0.8 mm
    assert voxel_m(p, "bullet") == 0.002                      # 0.01 x 0.0756 = 0.00076 -> floor 2 mm
    assert voxel_m(p, "bullet_hull") == 0.002


def test_voxel_rules_on_a_sports_car_scale_with_longest():
    p = _p("sports_car")
    assert p.longest == pytest.approx(4.5713, abs=1e-4)
    assert voxel_m(p, "shell") == pytest.approx(0.006 * p.longest)
    assert voxel_m(p, "liquid") == pytest.approx(0.004 * p.longest)
    assert voxel_m(p, "bullet") == pytest.approx(0.01 * p.longest)


def test_the_ceilings_bind_on_a_huge_subject():
    class Big:
        longest = 30.0
    assert (voxel_m(Big, "shell"), voxel_m(Big, "liquid"), voxel_m(Big, "bullet")) == (0.05, 0.03, 0.08)


def test_thickness_is_one_shell_voxel_and_the_triangle_caps():
    p = _p("sports_car")
    assert thickness_m(p) == voxel_m(p, "shell")
    assert (max_tris("shell"), max_tris("liquid"), max_tris("bullet"), max_tris("bullet_hull")) == (20000, 60000, 20000, 20000)
    assert max_hulls() == 16


def test_unknown_purpose_raises():
    with pytest.raises(ValueError):
        voxel_m(_p("sneaker"), "cloth")
    assert set(PURPOSES) == {"shell", "liquid", "bullet", "bullet_hull"}


def test_the_proxy_cache_key_is_a_store_key_and_changes_with_every_input():
    k = proxy_key("m" * 64, "shell", 0.001)
    assert k.startswith("proxy-") and ":" not in k and len(k) <= 128
    assert k == proxy_key("m" * 64, "shell", 0.001)
    assert len({k, proxy_key("n" * 64, "shell", 0.001), proxy_key("m" * 64, "liquid", 0.001),
                proxy_key("m" * 64, "shell", 0.002), proxy_key("m" * 64, "shell", 0.001, blender="5.2.0")}) == 5


def test_a_blender_without_grid_nodes_refuses_before_touching_the_mesh(monkeypatch):
    """No Solidify + voxel Remesh fallback: it took one Blender to 20 GB of RAM on the sports car. A Blender
    without the 5.0 grid nodes is refused with a gate code before any copy of the upload is made."""
    import sys
    import types

    import engine.blender.collision_proxy as cp
    fake = types.SimpleNamespace(types=types.SimpleNamespace(), app=types.SimpleNamespace(version_string="4.2.0"))
    monkeypatch.setitem(sys.modules, "bpy", fake)

    def boom(_meshes):
        raise AssertionError("the mesh was copied before the refusal")
    monkeypatch.setattr(cp, "_joined_copy", boom)
    with pytest.raises(cp.ProxyUnsupported) as e:
        cp.build_shell([], _p("sports_car"), "shell")
    assert e.value.code == cp.NEEDS_GRID_NODES == "proxy_needs_grid_nodes"
    assert "4.2.0" in str(e.value)


def test_the_proxy_builder_has_no_remesh_path():
    from pathlib import Path

    import engine.blender.collision_proxy as cp
    src = Path(cp.__file__).read_text(encoding="utf-8")
    assert '"REMESH"' not in src and '"SOLIDIFY"' not in src
