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


def _moving(t):                          # drives +x at 2 m/s while it turns 2 rad/s
    from engine.motion_path import SubjectPose
    return SubjectPose(offset=(2.0 * t, 0.0, 0.0), yaw=2.0 * t)


def test_a_detached_drip_leaves_the_moving_subject():                                  # review chunk3 #5
    from engine.motion_path import apply
    p = _p("sports_car")
    em = [([p.boundsMax[0], p.center[1], 0.6], 2.0, 0.25)]
    evs = D.drip_events(em, _moving, p, 6.0)
    assert evs and all(e["t0"] < e["td"] < e["tl"] for e in evs)
    ev = next(e for e in evs if e["td"] > 0.5)
    assert ev["pd"] == pytest.approx(apply(em[0][0], _moving(ev["td"]), p))       # lets go where the emitter is
    t = ev["td"] + 0.25
    state, size, pos = D.drip_at(ev, t)
    assert state == "fall" and size == 1.0
    carried = apply(em[0][0], _moving(t), p)                                       # where a carried drip would be
    assert math.dist(pos[:2], carried[:2]) > 0.05                                  # it does not ride along
    later = D.drip_at(ev, t + 0.05)[2]                                             # straight line in plan view
    assert [later[i] - pos[i] for i in range(2)] == pytest.approx([ev["vd"][i] * 0.05 for i in range(2)])
    want = [ev["pd"][i] + ev["vd"][i] * 0.25 for i in range(3)]
    want[2] -= 0.5 * D.G * 0.25 ** 2
    assert pos == pytest.approx(tuple(want))                                       # ballistic from the detach state
    assert D.drip_at(ev, ev["tl"] + 1e-3)[0] == "gone" and D.drip_at(ev, ev["t0"] - 1e-3)[0] == "wait"
    assert D.drip_at(ev, (ev["t0"] + ev["td"]) / 2, attached=(1.0, 2.0, 3.0))[2] == (1.0, 2.0, 3.0)   # hangs on


def test_drip_events_on_a_still_subject_are_the_periodic_cycles():
    from engine.motion_path import IDENTITY
    p = _p("sports_car")
    em = [([p.boundsMax[0], p.center[1], 0.4], 2.0, 0.3)]
    evs = D.drip_events(em, lambda t: IDENTITY, p, 10.0)
    for t in (0.1, 1.3, 4.7, 9.9):
        old = D.drip_state(t, 2.0, 0.3, 0.4)
        new = [D.drip_at(e, t) for e in evs]
        live = [n for n in new if n[0] in ("swell", "fall")]
        if old[0] == "gone":
            assert not live
        else:
            assert len(live) == 1 and live[0][0] == old[0] and live[0][1] == pytest.approx(old[1])
            if old[0] == "fall":
                assert live[0][2][2] == pytest.approx(0.4 - old[2])
