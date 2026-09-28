"""Phase 6 Task 102 (shatter): seeded Voronoi sites dense near the impact and convex cells by half-space
intersection (pure; METHODS M-FRAC, DS-01)."""
import math

import pytest

from engine.physics import fracture as F

BOX = (0.5, 0.004, 0.3)            # T94's plate: 0.5 m x 0.3 m x 4 mm (width X, thickness Y, height Z)


def test_sites_are_seeded_inside_and_dense_near_the_impact():
    s = F.sites(BOX, 60, impact=(0.1, 0.05), seed=4)
    assert len(s) == 60 and s == F.sites(BOX, 60, impact=(0.1, 0.05), seed=4)
    assert all(abs(x) < BOX[0] / 2 and abs(z) < BOX[2] / 2 for x, _, z in s)
    near = sum(1 for x, _, z in s if math.hypot(x - 0.1, z - 0.05) < 0.06)
    area_share = math.pi * 0.06 ** 2 / (BOX[0] * BOX[2])
    assert near / 60 > 2 * area_share                           # denser than uniform near the impact


@pytest.mark.parametrize("n", [20, 60, 200])
def test_cells_fill_the_box_exactly_with_no_empty_cells(n):
    s = F.sites(BOX, n, impact=(0.0, 0.0), seed=9)
    cells = F.cells(BOX, s)
    assert len(cells) == n
    vols = [F.volume(c) for c in cells]
    assert min(vols) > 0
    assert sum(vols) == pytest.approx(BOX[0] * BOX[1] * BOX[2], rel=1e-6)


def test_every_cell_contains_its_site_and_is_convex():
    s = F.sites(BOX, 30, impact=(-0.1, 0.0), seed=2)
    for site, c in zip(s, F.cells(BOX, s)):
        for face in c["faces"]:                                 # the site is on the inner side of every face
            pts = [c["verts"][i] for i in face]
            n = F.face_normal(pts)
            assert sum((site[k] - pts[0][k]) * n[k] for k in range(3)) < 1e-12
        for v in c["verts"]:                                    # and every vertex is inside the box
            assert all(abs(v[k]) <= BOX[k] / 2 + 1e-9 for k in range(3))


def test_a_cell_is_nearest_to_its_own_site():
    s = F.sites(BOX, 25, impact=(0.0, 0.0), seed=6)
    for i, c in enumerate(F.cells(BOX, s)):
        ctr = F.centroid(c)
        d = [math.dist(ctr, q) for q in s]
        assert d.index(min(d)) == i
