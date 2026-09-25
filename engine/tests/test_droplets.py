"""Task 66: droplets and drips (pure)."""
import dataclasses
import math

import pytest

from engine.catalog import Catalog
from engine.physics import droplets as D
from engine.physics import shape
from engine.tests.test_director_package import _p


def test_a_drip_swells_falls_and_is_gone():
    period, h = 2.0, 0.3
    assert D.drip_state(0.0, period, 0.0, h)[0] == "swell"
    s, size, _ = D.drip_state(0.5 * D.HANG_FRAC * period, period, 0.0, h)
    assert s == "swell" and 0 < size < 1
    t_land = D.HANG_FRAC * period + D.fall_time(h)
    s, size, drop = D.drip_state(t_land - 1e-3, period, 0.0, h)
    assert s == "fall" and drop == pytest.approx(h, rel=0.02)          # the fall ends at z = 0 at sqrt(2h/g)
    assert D.drip_state(t_land + 1e-3, period, 0.0, h)[0] == "gone"
    assert D.fall_time(h) == pytest.approx(math.sqrt(2 * h / 9.81))
    assert D.drip_state(0.3, period, 0.1, h) == D.drip_state(0.3 + period, period, 0.1, h)    # periodic


def test_up_facing_zone_selects_only_up_facing_samples():
    p = _p("pocket_watch")
    up = D.zone_samples(p, "up_facing")
    assert up and all(s["n"][2] > shape.UP_DOT for s in up)
    assert len(D.zone_samples(p, "all")) > len(up)


def test_a_subject_without_up_facing_surface_is_blocked():
    from engine.catalog import _has
    p = _p("pocket_watch")
    ring = [[0.03 * math.cos(a / 40 * 2 * math.pi), 0.03 * math.sin(a / 40 * 2 * math.pi), z / 10 * 0.05]
            for a in range(40) for z in range(11)]                          # a bare vertical tube: no up faces
    tube = dataclasses.replace(p, surfaceSamples=ring)
    assert len(shape.up_facing(shape.samples(tube))) < 8 and not _has(tube, "upFacing") and _has(p, "upFacing")
    from engine.weather_rules import _missing
    assert _missing(tube, Catalog.load().get("effect", "droplets")) == ["upFacing"]


def test_drip_emitters_are_seeded_low_edges():
    p = _p("sports_car")
    a, b = D.drip_emitters(p, 0.5, 7), D.drip_emitters(p, 0.5, 7)
    assert a == b and 0 < len(a) <= D.MAX_DRIPS // 2
    lows = {tuple(s["p"]) for s in shape.low_edges(shape.samples(p))}
    assert all(tuple(e[0]) in lows and e[1] > D.fall_time(e[0][2]) for e in a)


def test_bead_density_covers_a_share_of_the_surface():
    assert D.bead_density(1.5, 1.0) * math.pi * 0.00075 ** 2 == pytest.approx(D.COVER)
