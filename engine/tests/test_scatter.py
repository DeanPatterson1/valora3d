"""Phase 6 Task 100 (rigid_scatter): the pure spawn layout, real piece sizes, the pile cap and the key helpers."""
import math

import pytest

from engine.physics import scatter as S
from engine.physics.sim_facts import pile_zone
from engine.tests.test_director_package import _p


def test_piece_sizes_are_real_and_never_scale_with_the_subject():
    assert S.piece_size_m("beans") == 0.015 and S.piece_size_m("coffee_beans") == 0.011
    assert S.piece_size_m("ice") == 0.025 and S.piece_size_m("gems") == 0.012
    assert S.piece_size_m("coins") == 0.024 and S.piece_size_m("pills") == 0.012
    assert S.piece_size_m("candies") == 0.018 and S.piece_size_m("pebbles") == 0.02
    assert set(S.PIECE_SIZE_M) == set(S.PIECES)
    with pytest.raises(KeyError):
        S.piece_size_m("marbles")


def _params(**kw):
    return {"pieces": "beans", "count": 150, "zone": "onto", "timeScale": 0.5, "drop": 0.8, **kw}


def test_zone_areas():
    p = _p("sneaker")
    r = S.RADIUS_FRAC * p.longest
    assert S.zone_area(p, "onto") == pytest.approx(math.pi * r * r)
    z = pile_zone(p)
    assert S.zone_area(p, "around") == pytest.approx(math.pi * (z["outerM"] ** 2 - z["innerM"] ** 2))
    assert S.zone_area(p, "behind") == pytest.approx(S.zone_area(p, "around") * S.BEHIND_HALF_DEG / 180.0)


def test_count_is_capped_so_the_pile_covers_at_most_60_percent_of_the_zone():
    watch, shoe = _p("pocket_watch"), _p("sneaker")
    cap = S.count_for(_params(count=500), watch)
    assert cap == math.floor(S.PILE_COVER * S.zone_area(watch, "onto") / 0.015 ** 2)
    assert cap < 30                                    # a watch takes a small handful of real-size beans
    assert S.count_for(_params(count=150), shoe) == 150   # under the cap: exactly what was asked
    assert S.count_for(_params(count=500), shoe) == math.floor(S.PILE_COVER * S.zone_area(shoe, "onto") / 0.015 ** 2)
    assert S.count_for(_params(count=500, pieces="coins"), shoe) < S.count_for(_params(count=500), shoe)


def test_the_bake_time_cap_bounds_the_count():
    assert S.estimate_s(150, 124) == pytest.approx(57.5, rel=0.02)     # the measured points the model is fit to
    assert S.estimate_s(300, 124) == pytest.approx(155.9, rel=0.05)   # both laws pass near it
    assert S.estimate_s(500, 124) == pytest.approx(581.1, rel=0.05)
    for frames in (60, 124, 240):
        n = S.cost_cap(frames)
        assert S.estimate_s(n, frames) <= S.BAKE_CAP_S * S.COST_SAFETY < S.estimate_s(n + 1, frames)
    shoe = _p("sneaker")
    assert S.count_for(_params(count=500, pieces="coffee_beans"), shoe, frames=240) == S.cost_cap(240) < 300
    assert S.count_for(_params(count=150), shoe, frames=240) == 150


@pytest.mark.parametrize("zone", S.ZONES)
@pytest.mark.parametrize("name", ["sneaker", "pocket_watch", "sports_car"])
def test_spawn_is_exact_non_overlapping_and_never_inside_the_subject(zone, name):
    p = _p(name)
    prm = _params(zone=zone, count=300)
    pts = S.spawn(prm, p, seed=7, behind=(0.0, 1.0))
    assert len(pts) == S.count_for(prm, p)
    d = S.min_spacing(prm["pieces"])
    for i in range(len(pts)):                          # non-overlapping (bounding spheres, jitter included)
        for j in range(i + 1, len(pts)):
            assert math.dist(pts[i], pts[j]) >= d - 1e-12
    for x, y, z in pts:                                # outside bounds x 1.1 (the checker's margin)
        inside = (abs(x - p.center[0]) <= p.half[0] * 1.1 and abs(y - p.center[1]) <= p.half[1] * 1.1
                  and z <= p.boundsMax[2] * 1.1)
        assert not inside
        assert z >= p.boundsMax[2] * (1 + S.SPAWN_MARGIN) + prm["drop"] * p.sizeM[2] - 1e-9


def test_spawn_zones_land_where_they_say():
    p = _p("sneaker")
    c = p.center
    onto = S.spawn(_params(zone="onto"), p, seed=3)
    assert all(math.hypot(x - c[0], y - c[1]) <= S.RADIUS_FRAC * p.longest + 1e-9 for x, y, _ in onto)
    z = pile_zone(p)
    around = S.spawn(_params(zone="around"), p, seed=3)
    assert all(z["innerM"] - 1e-9 <= math.hypot(x - c[0], y - c[1]) <= z["outerM"] + 1e-9 for x, y, _ in around)
    behind = S.spawn(_params(zone="behind"), p, seed=3, behind=(0.0, 1.0))
    for x, y, _ in behind:                             # a wedge centred on +Y (away from the camera)
        ang = math.degrees(math.atan2(x - c[0], y - c[1]))
        assert abs(ang) <= S.BEHIND_HALF_DEG + 1e-9


def test_spawn_is_seeded():
    p = _p("sneaker")
    assert S.spawn(_params(), p, seed=5) == S.spawn(_params(), p, seed=5)
    assert S.spawn(_params(), p, seed=5) != S.spawn(_params(), p, seed=6)


def test_jitter_is_seeded_and_in_range():
    j = S.size_jitter(9, 200)
    assert j == S.size_jitter(9, 200) and len(j) == 200
    assert all(S.JITTER[0] <= v <= S.JITTER[1] for v in j)


def test_quaternions_are_made_sign_continuous_for_linear_keys():
    rows = [[0, 0, 0, 1, 0, 0, 0], [0, 0, 0, -0.99, 0.1, 0, 0], [0, 0, 0, 0.98, -0.2, 0, 0]]
    out = S.continuous_quats(rows)
    assert out[1][3:] == [0.99, -0.1, 0, 0] and out[2][3:] == [0.98, -0.2, 0, 0]
    assert out[0] == rows[0]


def test_row_rounding():
    assert S.row((0.1234567, 1.0, 2.0), (1.0, 0.0, 0.0, 0.0)) == [0.12346, 1.0, 2.0, 1.0, 0.0, 0.0, 0.0]
