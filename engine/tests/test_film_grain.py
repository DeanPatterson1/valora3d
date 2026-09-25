"""Display-referred sensor grain (realism audit #20): render-studio's ffmpeg GRAIN_FILTER (pipeline.py:152:
noise=alls=13:allf=t+u, maskedmerge through lutyuv y=clip(250-1.35*val,45,250), u=v=110) applied to the
finished 8-bit frame AFTER AgX, not scene-linear before the view transform."""
import numpy as np
import pytest

from engine.film_grain import FILM_STRENGTH, apply_grain, strength_for


def _flat(v, h=64, w=48):
    return np.full((h, w, 3), v, np.float64)


def test_amount_zero_is_identity():
    img = np.random.default_rng(0).random((32, 32, 3))
    assert np.array_equal(apply_grain(img, 0.0, seed=1, frame=1), img)


def test_film_amount_matches_alls_13():
    assert strength_for(0.5) == pytest.approx(FILM_STRENGTH) and FILM_STRENGTH == 13


def test_same_seed_and_frame_same_grain_new_frame_new_grain():
    img = _flat(0.3)
    a, b = apply_grain(img, 0.5, seed=7, frame=10), apply_grain(img, 0.5, seed=7, frame=10)
    c, d = apply_grain(img, 0.5, seed=7, frame=11), apply_grain(img, 0.5, seed=8, frame=10)
    assert np.array_equal(a, b) and not np.array_equal(a, c) and not np.array_equal(a, d)


def test_shadows_carry_the_grain_highlights_stay_clean():
    luma = lambda im: im @ np.array([0.2126, 0.7152, 0.0722])      # noqa: E731
    dark, bright = apply_grain(_flat(0.05), 0.5, 3, 1), apply_grain(_flat(0.95), 0.5, 3, 1)
    sd, sb = (luma(dark) - 0.05).std(), (luma(bright) - 0.95).std()
    assert sd > 4.0 * sb                    # luma mask 250 vs 45 (chroma keeps its flat 110, as ffmpeg did)
    # uniform +-13/255 x mask 250/255 at black: std = 13 x 250/255 / sqrt(3) / 255 ~ 0.0289 on luma
    assert 0.02 < sd < 0.04


def test_grain_is_zero_mean_and_stays_in_range():
    out = apply_grain(_flat(0.5, 256, 256), 0.5, 5, 3)
    assert abs(out.mean() - 0.5) < 0.003 and out.min() >= 0.0 and out.max() <= 1.0
    edge = apply_grain(_flat(0.0), 1.0, 5, 3)
    assert edge.min() >= 0.0
