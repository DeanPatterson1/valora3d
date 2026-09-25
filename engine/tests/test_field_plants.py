"""golden_field plant variants and clumping (engine/worlds/field_plants.py), pure."""
import random

import pytest

from engine.worlds import field_plants as P


def _islands(n, polys):
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for q in polys:
        for v in q[1:]:
            parent[find(v)] = find(q[0])
    return {find(i) for i in range(n)}


def test_six_to_ten_variants_that_share_the_field():
    assert 6 <= len(P.VARIANTS) <= 10
    assert sum(v[1] for v in P.VARIANTS) == pytest.approx(1.0)
    counts = [0] * len(P.VARIANTS)
    rng = random.Random(0)
    for _ in range(20000):
        counts[P.variant(rng.random())] += 1
    for (name, share, *_), c in zip(P.VARIANTS, counts):
        assert c / 20000 == pytest.approx(share, abs=0.02), name


def test_blade_widths_are_real_grass_widths():
    for name, _, (w0, w1), *_ in P.VARIANTS:
        assert 0.0015 <= w0 <= w1 <= 0.006, name


def test_colours_mix_green_straw_and_brown():
    assert {v[5] for v in P.VARIANTS} >= {P.GREEN, P.STRAW, P.BROWN}


@pytest.mark.parametrize("seed", range(60))
def test_every_plant_is_one_island_rooted_at_the_ground(seed):
    rng = random.Random(seed)
    x, y, h = rng.uniform(-5, 5), rng.uniform(-5, 5), rng.uniform(0.15, 0.6)
    v, p, u, c = P.blade(x, y, rng.uniform(0, 360), h, rng.uniform(0, 0.35), rng.random())
    assert len(u) == len(v) and len(c) == len(p)
    assert len(_islands(len(v), p)) == 1
    lowest = min(range(len(v)), key=lambda i: v[i][2])
    assert v[lowest][2] == 0.0 and u[lowest] == 0.0
    assert max(u) == 1.0 and all(0.0 <= a <= 1.0 for a in u)
    assert all(q < len(v) for poly in p for q in poly)


def test_heights_follow_the_layout_with_jitter():
    hs = []
    for i in range(2000):
        pick = (i + 0.5) / 2000
        v, *_ = P.blade(0.0, 0.0, 0.0, 0.4, 0.2, pick)
        hs.append(max(z for *_, z in v))
    assert min(hs) < 0.4 * 0.35 and max(hs) > 0.4 * 0.95             # weeds low, seed heads at the top
    assert 0.2 < sorted(hs)[len(hs) // 2] < 0.36
    assert max(hs) <= 0.4 + 1e-9                                        # the layout's height (and sight cut) holds


def test_seed_heads_carry_a_seed_class_poly():
    i = next(k for k, v in enumerate(P.VARIANTS) if v[6] == "seed")
    lo = sum(v[1] for v in P.VARIANTS[:i])
    v, p, u, c = P.blade(0.0, 0.0, 0.0, 0.4, 0.1, lo + 0.5 * P.VARIANTS[i][1])
    assert P.SEED in c and len(v) == 8


def test_a_trampled_blade_stays_lying_down():
    v, *_ = P.blade(0.0, 0.0, 0.0, 0.02, 10.0, 0.5)
    assert max(z for *_, z in v) <= 0.02 + 1e-9
    assert max(abs(x) for x, *_ in v) > 0.1


def test_clumps_leave_gaps_at_real_scales():
    pts = [(i * 0.05, j * 0.05) for i in range(120) for j in range(120)]
    d = [P.clump(x, y, 7) for x, y in pts]
    assert all(0.0 <= a <= 1.0 for a in d)
    keep = sum(1 for a in d if a >= P.CLUMP_KEEP) / len(d)
    assert 0.45 < keep < 0.8
    assert P.clump(1.0, 2.0, 7) == P.clump(1.0, 2.0, 7) and P.clump(1.0, 2.0, 7) != P.clump(1.0, 2.0, 8)
