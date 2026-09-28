"""Phase 6 Task 101 (debris_float): the pure analytic float (RB-07, METHODS M-KIN)."""
import math

import pytest

from engine.physics import debris as D
from engine.tests.test_director_package import _p


def _params(**kw):
    return {"count": 20, "sizeFrac": 0.05, "pieces": "pebbles", **kw}


@pytest.mark.parametrize("name", ["pocket_watch", "sneaker", "sports_car"])
def test_layout_is_exact_seeded_and_in_the_rb07_ranges(name):
    p = _p(name)
    lay = D.layout(_params(), p, seed=11, duration_s=6.0)
    assert len(lay) == 20 and lay == D.layout(_params(), p, seed=11, duration_s=6.0)
    for piece in lay:
        speed = math.hypot(*piece["velocity"])
        assert D.DRIFT_FRAC[0] * p.longest - 1e-12 <= speed <= D.DRIFT_FRAC[1] * p.longest + 1e-12
        assert D.SPIN_DEG_S[0] <= abs(piece["spinDegS"]) <= D.SPIN_DEG_S[1]
        assert 0.0 <= piece["phase"] < 2 * math.pi
        assert D.SIZE_JITTER[0] * 0.05 * p.longest - 1e-12 <= piece["size"] <= D.SIZE_JITTER[1] * 0.05 * p.longest + 1e-12
    assert len({round(x["phase"], 9) for x in lay}) == 20             # every piece has its own phase


@pytest.mark.parametrize("name", ["pocket_watch", "sneaker", "sports_car"])
@pytest.mark.parametrize("count", [5, 60])
def test_no_path_goes_through_the_subject_or_the_floor(name, count):
    p = _p(name)
    lay = D.layout(_params(count=count, sizeFrac=0.15), p, seed=3, duration_s=8.0)
    assert D.path_through_subject(lay, p, 8.0) == 0
    for piece in lay:
        for k in range(D.SAMPLES):
            t = 8.0 * k / (D.SAMPLES - 1)
            assert D.position(piece, t)[2] - piece["size"] / 2 >= 0.0


def test_path_through_subject_catches_a_bad_path():
    p = _p("sneaker")
    lay = D.layout(_params(count=5), p, seed=1, duration_s=4.0)
    bad = dict(lay[0], origin=list(p.center), velocity=[0.0, 0.0, 0.0])
    assert D.path_through_subject([bad] + lay[1:], p, 4.0) == 1


def test_pieces_keep_apart():
    p = _p("sneaker")
    lay = D.layout(_params(count=60, sizeFrac=0.1), p, seed=5, duration_s=8.0)
    for k in range(D.SAMPLES):
        t = 8.0 * k / (D.SAMPLES - 1)
        pos = [D.position(x, t) for x in lay]
        for i in range(len(lay)):
            for j in range(i + 1, len(lay)):
                assert math.dist(pos[i], pos[j]) >= (lay[i]["size"] + lay[j]["size"]) / 2


def test_rotation_is_a_unit_quaternion_turning_at_the_spin_rate():
    p = _p("sneaker")
    x = D.layout(_params(count=5), p, seed=2, duration_s=4.0)[0]
    q0, q1 = D.rotation(x, 0.0), D.rotation(x, 1.0)
    assert abs(sum(v * v for v in q0) - 1) < 1e-9
    dot = abs(sum(a * b for a, b in zip(q0, q1)))
    assert math.degrees(2 * math.acos(min(1.0, dot))) == pytest.approx(abs(x["spinDegS"]), abs=1e-6)
