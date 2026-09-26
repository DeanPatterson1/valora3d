"""Display-referred sensor grain on the finished 8-bit frame AFTER AgX (realism audit #20), at the clean-sensor
strength of critique mat-v2 #1 (round 9: 0.7-1.5) code values of luminance std-dev on 0-255 in a flat region, low chroma."""
import numpy as np
import pytest

from engine.film_grain import CHROMA_SHARE, apply_grain, sigma_for

LUMA = np.array([0.2126, 0.7152, 0.0722])


def _flat(v, h=256, w=256):
    return np.full((h, w, 3), v, np.float64)


def _delivered(img):
    """The written frame: 8-bit code values."""
    return np.round(img * 255.0)


def test_amount_zero_is_identity():
    img = np.random.default_rng(0).random((32, 32, 3))
    assert np.array_equal(apply_grain(img, 0.0, seed=1, frame=1), img)


@pytest.mark.parametrize("v", [0.02, 0.1, 0.3, 0.5, 0.7, 0.9])
def test_camera_grain_is_a_sensors_code_value_or_so_of_luma_std_dev_in_any_flat_region(v):
    """Round 9: 0.7-1.5 code values (was 0.5-1.0; the owner read the frames as perfectly clean pixels)."""
    out = _delivered(apply_grain(_flat(v), 0.5, seed=3, frame=1))
    sd = (out @ LUMA).std()
    assert 0.7 <= sd <= 1.5, sd


def test_chroma_is_low():
    out = apply_grain(_flat(0.3), 0.5, seed=3, frame=1) * 255.0
    y = out @ LUMA
    chroma = out - y[..., None]                      # per-channel departure from the luma
    assert chroma.std() < 0.5 * y.std()
    assert CHROMA_SHARE <= 0.3


def test_shadows_carry_a_little_more_than_highlights():
    assert sigma_for(0.5, 0.0) > sigma_for(0.5, 1.0) >= 0.5
    assert sigma_for(0.5, 0.0) <= 1.5                                 # round 9: a sensor, not a clean render


def test_same_seed_and_frame_same_grain_new_frame_new_grain():
    img = _flat(0.3, 64, 48)
    a, b = apply_grain(img, 0.5, seed=7, frame=10), apply_grain(img, 0.5, seed=7, frame=10)
    c, d = apply_grain(img, 0.5, seed=7, frame=11), apply_grain(img, 0.5, seed=8, frame=10)
    assert np.array_equal(a, b) and not np.array_equal(a, c) and not np.array_equal(a, d)


def test_grain_is_zero_mean_and_stays_in_range():
    out = apply_grain(_flat(0.5), 0.5, 5, 3)
    assert abs(out.mean() - 0.5) < 0.001 and out.min() >= 0.0 and out.max() <= 1.0
    edge = apply_grain(_flat(0.0, 64, 48), 1.0, 5, 3)
    assert edge.min() >= 0.0
