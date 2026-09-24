import pytest
from engine.easing import EASINGS, ease, settle


@pytest.mark.parametrize("name", EASINGS)
def test_easings_hit_endpoints_and_are_monotone(name):
    assert ease(name, 0.0) == 0.0 and abs(ease(name, 1.0) - 1.0) < 1e-12
    vals = [ease(name, i / 100) for i in range(101)]
    assert all(b >= a - 1e-12 for a, b in zip(vals, vals[1:]))


def test_ease_clamps_and_rejects_unknown():
    assert ease("in_out_cubic", -1) == 0.0 and ease("in_out_cubic", 2) == 1.0
    with pytest.raises(ValueError):
        ease("bounce", 0.5)


def test_settle_finishes_early_and_holds():
    assert settle(0.8, 0.2) == 1.0 and settle(1.0, 0.2) == 1.0
    assert abs(settle(0.4, 0.2) - 0.5) < 1e-12
    assert settle(0.3, 0.0) == 0.3


@pytest.mark.parametrize("bad", [-0.01, 0.51, 1.0, -1.0])
def test_settle_rejects_out_of_range_frac(bad):
    with pytest.raises(ValueError):
        settle(0.5, bad)
