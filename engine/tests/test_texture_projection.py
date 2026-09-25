"""Metric world-space PBR projection without UVs (realism audit #14) and stochastic anti-tiling (audit
"texture repetition"). The node builder (engine/blender/env_assets.pbr_sampler) realises exactly these frames."""
import math

import pytest

from engine.texture_projection import (ANTI_TILE_ROT_DEG, ANTI_TILE_SCALE, cross, dot, face_frame, projection_frame,
                                       rotated_frame, uv_of)

AXES = [(0, 0, 1), (0, 0, -1), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0.3, 0.2, 0.93), (0.9, -0.3, 0.2)]


@pytest.mark.parametrize("n", AXES)
def test_every_face_gets_a_right_handed_frame_of_its_own(n):
    t, b = projection_frame(n)
    assert dot(t, t) == pytest.approx(1) and dot(b, b) == pytest.approx(1) and dot(t, b) == pytest.approx(0)
    assert dot(cross(t, b), n) > 0          # normal maps light the face the right way round, never mirrored
    ft, fb = face_frame(n, t, b)            # the decode frame: tangent to the face, orthonormal, same handedness
    ln = math.sqrt(dot(n, n))
    assert abs(dot(ft, n)) < 1e-9 and abs(dot(fb, n)) < 1e-9 and dot(ft, fb) == pytest.approx(0, abs=1e-9)
    assert dot(cross(ft, fb), n) / ln == pytest.approx(1.0)


def test_vertical_faces_are_not_projected_from_above():
    for n in [(1, 0, 0), (0, -1, 0)]:
        t, b = projection_frame(n)
        assert b == (0, 0, 1)                # texture 'up' is world up on a wall/kerb face: metric, unstretched


def test_uv_is_metric_and_follows_the_frame():
    p, tile = (2.0, -1.5, 0.3), 3.0
    for n in AXES[:6]:
        t, b = projection_frame(n)
        u, v = uv_of(p, n, tile)
        assert u == pytest.approx(dot(p, t) / tile) and v == pytest.approx(dot(p, b) / tile)


def test_rotated_frame_matches_the_rotated_uv():
    """uv2 = R(theta) uv * s: the world direction of +u2 / +v2 is the rotated frame, so a normal map sampled at
    uv2 is lit consistently with the first sample."""
    t, b = projection_frame((0, 0, 1))
    th = math.radians(ANTI_TILE_ROT_DEG)
    t2, b2 = rotated_frame(t, b, th)
    p = (0.4, 0.7, 0.0)
    eps = 1e-6
    for d, want in ((t2, (1, 0)), (b2, (0, 1))):
        q = tuple(pi + eps * di for pi, di in zip(p, d))
        (u0, v0), (u1, v1) = (uv_of(x, (0, 0, 1), 1.0, rot=th, scale=1.0) for x in (p, q))
        assert ((u1 - u0) / eps, (v1 - v0) / eps) == pytest.approx(want, abs=1e-5)


def test_anti_tiling_second_sample_never_realigns():
    assert 20 < ANTI_TILE_ROT_DEG < 70 and 0.5 < ANTI_TILE_SCALE < 0.9   # an irrational-ish turn and scale
