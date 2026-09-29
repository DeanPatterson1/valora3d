"""golden_field, small product: every plant class stays out of the sight line of a camera down in the grass.
Regression for the 2026-09-29 raycast finding (seed 1-3 sneaker sheets): moss and clover (COVER_KINDS nominal
height <= 0.06 m) skipped the sight cut, so a camera 0.03 m off the ground saw the shoe through a wall of cover
(0-15% of the shoe's upper body visible). Pure geometry, no Blender: each plant is a vertical cylinder (its
crown radius x its height) and a target point is hidden when a camera -> point ray passes through one."""
import math

import pytest

from engine.tests.test_director_package import _p
from engine.worlds import field_layout as F

MIN_VISIBLE = 0.6


def _plants(lay):
    """(x, y, crown radius, height) for every plant class the layout emits."""
    out = [(x, y, F.BLADE_W + lean * h, h) for x, y, _, h, lean, *_ in lay["blades"] + lay["floor"]]
    out += [(x, y, 0.5 * w, h + 0.5 * w) for x, y, _, h, w in lay["farGrass"]]   # tilted by lodge(): the edge lifts
    nominal = {**{k: v[0] for k, v in F.FLORA.items()}, **{k: v[0] for k, v in F.COVER_KINDS.items()}}
    for kind, pts in lay["flora"].items():
        h0 = nominal[kind]
        out += [(x, y, F.FLORA_REACH_K * h0 * s, h0 * s) for x, y, _, s in pts]
    return out


def _visible_share(p, plants, cam):
    lo, hi = p.boundsMin, p.boundsMax
    pts = [(lo[0] + (hi[0] - lo[0]) * i / 4, lo[1] + (hi[1] - lo[1]) * j / 2, lo[2] + (hi[2] - lo[2]) * (0.5 + 0.5 * k / 3))
           for i in range(5) for j in range(3) for k in range(4)]
    seen = 0
    for px, py, pz in pts:
        dx, dy, dz = px - cam[0], py - cam[1], pz - cam[2]
        L2 = dx * dx + dy * dy
        hit = False
        for x, y, r, h in plants:
            t = ((x - cam[0]) * dx + (y - cam[1]) * dy) / L2
            if not 0.0 < t < 0.97:
                continue
            if math.hypot(x - (cam[0] + t * dx), y - (cam[1] + t * dy)) <= r and cam[2] + t * dz < h:
                hit = True
                break
        seen += not hit
    return seen / len(pts)


@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize("az,z", [(20.0, 0.03), (50.0, 0.03), (-100.0, 0.05), (20.0, 0.17)])
def test_a_low_camera_sees_the_small_products_upper_body(seed, az, z):
    p = _p("sneaker")
    cx, cy, _ = p.center
    cam = (cx + 0.75 * math.cos(math.radians(az)), cy + 0.75 * math.sin(math.radians(az)), z)
    lay = F.layout(p, seed=seed, cameras=[cam])
    share = _visible_share(p, _plants(lay), cam)
    assert share >= MIN_VISIBLE, f"seed {seed} az {az} z {z}: only {share:.0%} of the shoe's upper body is visible"


def test_the_low_cover_kinds_obey_the_sight_cut():
    p = _p("sneaker")
    cx, cy, _ = p.center
    cam = (cx + 0.75, cy + 0.2, 0.03)
    lay = F.layout(p, seed=1, cameras=[cam])
    lines = lay["sightLines"]
    for kind in ("moss", "clover"):
        h0 = F.COVER_KINDS[kind][0]
        for x, y, _, s in lay["flora"][kind]:
            assert h0 * s <= F.sight_cap(x, y, lines, lay["sightHalfW"], reach=F.FLORA_REACH_K * h0 * s) + 1e-9
