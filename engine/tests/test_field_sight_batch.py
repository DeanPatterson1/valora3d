"""golden_field build time: the batched sight cut (field_layout.sight_caps) is bit-identical to the scalar sight_cap it
replaced, and a whole layout built through it equals one built point by point.

The moving shots of a site job put ~60 distinct camera positions (x ~7 sight lines each) in front of ~350k plants; the
scalar cut was O(plants x lines) in pure Python (build:world:golden_field 160-200 s for the sports car). sight_caps
prunes each line by bounding box and runs the rest in numpy; a comparison within 1e-9 of a hypot() threshold is handed
back to the scalar function, so the result never depends on numpy's last ulp."""
import json
import math
import random

import numpy as np
import pytest

from engine.tests.test_director_package import _p
from engine.worlds import field_layout as F


def _cams(p, seed, n):
    rng = random.Random(seed)
    cx, cy, _ = p.center
    span = max(p.longest, 0.3)
    return [(cx + rng.uniform(-4, 4) * span, cy + rng.uniform(-4, 4) * span, rng.choice([0.03, 0.08, 0.3, 0.9, 1.6]))
            for _ in range(n)]


def _flat(d):
    return json.dumps(d, sort_keys=True, default=list)


@pytest.mark.parametrize("name", ["sneaker", "sports_car", "mid_century_lounge_chair"])
@pytest.mark.parametrize("seed", [1, 2])
def test_batched_cap_equals_scalar_cap_for_every_point(name, seed):
    p = _p(name)
    lines = F._sight_lines(p, _cams(p, seed, 14))
    half_w = max(F.SIGHT_W_MIN, F.SIGHT_W_K * p.longest)
    rng = random.Random(seed + 100)
    cx, cy, _ = p.center
    span = max(p.longest, 0.3)
    n = 3000
    xs = np.array([cx + rng.uniform(-5, 5) * span for _ in range(n)])
    ys = np.array([cy + rng.uniform(-5, 5) * span for _ in range(n)])
    reach = np.array([rng.choice([0.0, 0.012, 0.1, 0.4]) * rng.random() for _ in range(n)])
    tk = np.array([rng.choice([1.0, 1.0, 0.7, 1.4]) for _ in range(n)])
    got = F.sight_caps(xs, ys, lines, half_w, tk, reach)
    ref = np.array([F.sight_cap(float(x), float(y), lines, half_w, float(k), float(r))
                    for x, y, k, r in zip(xs, ys, tk, reach)])
    assert np.isfinite(ref).any() and not np.isfinite(ref).all()      # the sample exercises both branches
    assert np.array_equal(got, ref)


def test_batched_cap_on_the_thresholds_themselves():
    """Points placed exactly on a corridor's edge, at the tyre-tuft radius and at the lens-clearing radius: the ulp
    band where numpy's hypot and math.hypot may part ways. Still identical."""
    p = _p("sports_car")
    cam = (p.center[0] + 3.1, p.center[1] + 1.7, 0.2)
    lines = F._sight_lines(p, [cam])
    half_w = max(F.SIGHT_W_MIN, F.SIGHT_W_K * p.longest)
    pts = []
    for line in lines:
        if line[0] == "wedge":
            continue
        if line[0] == "near":
            (ax, ay), _, (bx, by) = line[1], line[2], line[3]
            ux, uy = (bx - ax), (by - ay)
            m = math.hypot(ux, uy)
            for a in np.linspace(0, math.tau, 24):
                pts.append((ax + F.NEAR_CAM_R_M * math.cos(a), ay + F.NEAR_CAM_R_M * math.sin(a), 0.0))
            continue
        (ax, ay), _, (bx, by), _ = line[:4]
        hw = line[4] if len(line) > 4 else half_w
        m = math.hypot(bx - ax, by - ay)
        nx, ny = -(by - ay) / m, (bx - ax) / m
        for t in np.linspace(0.05, 0.95, 40):
            for reach in (0.0, 0.05):
                pts.append((ax + t * (bx - ax) + nx * (hw + reach), ay + t * (by - ay) + ny * (hw + reach), reach))
        for a in np.linspace(0, math.tau, 24):
            pts.append((bx + F.TYRE_TUFT_R_M * math.cos(a), by + F.TYRE_TUFT_R_M * math.sin(a), 0.0))
    xs, ys, rs = (np.array(v) for v in zip(*pts))
    tk = np.full(len(pts), 0.7)
    assert np.array_equal(F.sight_caps(xs, ys, lines, half_w, tk, rs),
                          np.array([F.sight_cap(float(x), float(y), lines, half_w, 0.7, float(r))
                                    for x, y, r in zip(xs, ys, rs)]))


def test_no_lines_or_no_points():
    assert F.sight_caps([], [], [("near", (0, 0), 0.1, (1, 1))], 0.25).shape == (0,)
    assert np.array_equal(F.sight_caps([0.5], [0.5], [], 0.25), [math.inf])


def _scalar_caps(xs, ys, lines, half_w, tyre_k=1.0, reach=0.0):
    n = len(xs)
    tk = np.broadcast_to(np.asarray(tyre_k, dtype=float), (n,))
    rc = np.broadcast_to(np.asarray(reach, dtype=float), (n,))
    return np.array([F.sight_cap(float(x), float(y), lines, half_w, float(tk[i]), float(rc[i]))
                     for i, (x, y) in enumerate(zip(xs, ys))])


@pytest.mark.parametrize("name,seed,crop,track", [("sneaker", 1, "grass", False), ("sneaker", 2, "wheat", True),
                                                  ("sneaker", 3, "wildflowers", False),
                                                  ("sports_car", 4, "grass", False)])
def test_layout_with_batched_cuts_equals_layout_with_scalar_cuts(monkeypatch, name, seed, crop, track):
    """Same kept / removed blades, tufts, weeds and cover plants, same heights and transforms, same cut count."""
    p = _p(name)
    cams = _cams(p, seed, 3)
    cx, cy, _ = p.center
    kw = dict(grass_height_m=0.45, crop=crop, track=track, cameras=cams, hero=(cx + 2, cy - 1, 0.3), sun=(0.4, 0.3, 0.86))
    fast = F.layout(p, seed, **kw)
    monkeypatch.setattr(F, "sight_caps", _scalar_caps)
    slow = F.layout(p, seed, **kw)
    assert fast["sightCut"] > 0 or name == "sports_car"
    assert _flat(fast) == _flat(slow)


def test_tuft_sites_with_batched_cuts_equal_scalar_cuts(monkeypatch):
    from engine.blocks.world.golden_field import build as B
    rr = random.Random(5)
    protos = [{"h": rr.uniform(0.15, 0.6), "r": 0.05, "co": [(0, 0, 0)] * rr.randint(60, 300), "tiny": k >= 4}
              for k in range(6)]
    p = _p("sports_car")
    cams = _cams(p, 9, 6)
    cx, cy, _ = p.center
    lay = F.layout(p, 3, 0.45, "grass", False, cams, (cx + 2, cy - 1, 0.3), (0.4, 0.3, 0.86))
    fast = B._tuft_sites(lay, protos, "dusk", cams, seed=3, wind_deg=30.0)
    monkeypatch.setattr(F, "sight_caps", _scalar_caps)
    slow = B._tuft_sites(lay, protos, "dusk", cams, seed=3, wind_deg=30.0)
    assert len(fast) > 100 and json.dumps(fast) == json.dumps(slow)
