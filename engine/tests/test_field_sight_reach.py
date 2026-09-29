"""golden_field: the subject stays visible. A plant whose ROOT stands beside a camera's sight line but whose crown
reaches into it is cut like one on the line (sight_cap reach), and a small product's wedge aims mid-height."""
import math

import pytest

from engine.tests.test_director_package import _p
from engine.worlds import field_layout as F


def _cam(p, dx=1.2, dy=0.6, z=0.05):
    cx, cy, _ = p.center
    return (cx + dx, cy + dy, z)


def test_reach_widens_every_corridor_and_the_wedge():
    p = _p("sneaker")
    cam = _cam(p, 2.5, 1.2)
    lines = F._sight_lines(p, [cam])
    half_w = max(F.SIGHT_W_MIN, F.SIGHT_W_K * p.longest)
    cx, cy, _ = p.center
    # a point half way to the subject, just outside the 0.25 m corridor (and outside the wedge)
    ax, ay = cam[0] + (cx - cam[0]) / 2, cam[1] + (cy - cam[1]) / 2
    nx, ny = -(cy - cam[1]), cx - cam[0]
    n = math.hypot(nx, ny)
    x, y = ax + nx / n * (half_w + 0.12), ay + ny / n * (half_w + 0.12)
    assert F.sight_cap(x, y, lines, half_w) == math.inf
    assert F.sight_cap(x, y, lines, half_w, reach=0.2) < math.inf      # its crown spans 0.2 m: it is cut


def test_reach_never_raises_a_cap():
    p = _p("sneaker")
    lines = F._sight_lines(p, [_cam(p)])
    half_w = max(F.SIGHT_W_MIN, F.SIGHT_W_K * p.longest)
    cx, cy, _ = p.center
    for i in range(200):
        x, y = cx + 3.0 * math.cos(i), cy + 3.0 * math.sin(i * 1.7)
        assert F.sight_cap(x, y, lines, half_w, reach=0.15) <= F.sight_cap(x, y, lines, half_w) + 1e-12


def test_a_small_product_aims_the_wedge_higher_than_a_car():
    assert F.wedge_aim_k(_p("sneaker")) == F.SMALL_AIM_K
    assert F.wedge_aim_k(_p("sports_car")) == F.WEDGE_AIM_K
    assert F.WEDGE_AIM_K < F.wedge_aim_k(_p("mid_century_lounge_chair")) <= F.SMALL_AIM_K


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_no_crown_reaches_the_line_of_sight_to_a_small_products_middle(seed):
    """Independent of sight_cap: for every blade, weed and static tuft, the height at the point of the camera ->
    subject-middle ray nearest its root must clear the plant, unless the crown stays out of the wedge."""
    p = _p("sneaker")
    cam = _cam(p, 1.0, -0.5, 0.06)
    lay = F.layout(p, seed=seed, cameras=[cam])
    (cx, cy), hx, hy = F._frame(p)
    mid = p.boundsMin[2] + 0.5 * (p.boundsMax[2] - p.boundsMin[2])
    bad = 0
    for x, y, _, h, lean, *_ in lay["blades"]:
        dx, dy = cx - cam[0], cy - cam[1]
        t = ((x - cam[0]) * dx + (y - cam[1]) * dy) / (dx * dx + dy * dy)
        if not 0.0 < t < 1.0:
            continue
        lateral = math.hypot(x - (cam[0] + t * dx), y - (cam[1] + t * dy))
        ray_z = cam[2] + t * (mid - cam[2])
        crown = F.BLADE_W + lean * h
        if lateral - crown <= hx * 0.5 and h > ray_z + 0.05:      # the ray's own footprint, half the subject wide
            bad += 1
    assert bad == 0


def test_a_camera_in_the_grass_keeps_the_ground_ahead_of_its_lens_low():
    p = _p("sneaker")
    cam = _cam(p, 2.5, 1.2, 0.08)
    lines = F._sight_lines(p, [cam])
    cx, cy, _ = p.center
    ux, uy = (cx - cam[0]), (cy - cam[1])
    n = math.hypot(ux, uy)
    ux, uy = ux / n, uy / n
    x, y = cam[0] + 0.5 * ux + 0.4 * uy, cam[1] + 0.5 * uy - 0.4 * ux    # 0.64 m ahead, well off the sight corridor
    assert F.sight_cap(x, y, lines, 0.25) < 0.08 + F.NEAR_CAM_SLOPE * 0.7
    bx, by = cam[0] - 0.5 * ux, cam[1] - 0.5 * uy                       # behind the lens: unseen, untouched
    assert F.sight_cap(bx, by, lines, 0.25) == math.inf
    high = F._sight_lines(p, [(cam[0], cam[1], 1.6)])                    # a camera above the grass keeps no lens clearing
    assert not any(l[0] == "near" for l in high)
