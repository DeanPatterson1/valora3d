"""Foliage LOD by projected size (engine/worlds/foliage_lod.py), pure."""
import pytest

from engine.worlds import foliage_lod as F


def test_projected_px_is_pinhole_height_on_the_long_side():
    # 0.2 m tall at 10 m, 36 mm sensor, 50 mm lens, 1920 px long side: 0.2 * (50/36*1920) / 10
    px = F.projected_px((10.0, 0.0, 0.0), 0.2, [(0.0, 0.0, 0.0)], [50.0])
    assert px == pytest.approx(0.2 * 50.0 / 36.0 * 1920 / 10.0)


def test_the_nearest_longest_lens_wins():
    cams, lenses = [(0.0, 0.0, 0.0), (9.0, 0.0, 0.0)], [24.0, 85.0]
    near = F.projected_px((10.0, 0.0, 0.0), 0.2, cams, lenses)
    assert near == pytest.approx(0.2 * 85.0 / 36.0 * 1920 / 1.0)


def test_missing_lenses_default_to_50mm():
    assert F.projected_px((5.0, 0.0, 0.0), 0.3, [(0.0, 0.0, 0.0)], []) == pytest.approx(
        F.projected_px((5.0, 0.0, 0.0), 0.3, [(0.0, 0.0, 0.0)], [50.0]))


def test_no_camera_means_full_detail():
    assert F.projected_px((5.0, 0.0, 0.0), 0.3, [], []) == float("inf")
    assert F.pick(float("inf")) == 0


def test_a_camera_inside_the_tuft_is_clamped_not_infinite():
    assert F.projected_px((0.0, 0.0, 0.0), 0.3, [(0.0, 0.0, 0.0)], [50.0]) < float("inf")


def test_pick_walks_the_bands_from_full_detail_down():
    assert F.pick(F.FULL_PX + 1) == 0
    assert F.pick(F.FULL_PX - 1) == 1
    assert F.pick(F.MID_PX - 1) == 2
    assert F.pick(0.0) == 2
    assert [F.pick(x) for x in (500, 100, 40, 10, 1)] == sorted(F.pick(x) for x in (500, 100, 40, 10, 1))
