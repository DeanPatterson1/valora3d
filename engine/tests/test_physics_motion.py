import math

import pytest

from engine.physics import events, settle, suspension, wheel_spin

FPS = 30


def _slide_then_stop():
    """1 m/s along +y for 30 frames, then parked (positions per frame, frame 1 first)."""
    return [(0.0, min(i, 30) / FPS, 0.0) for i in range(60)]


def test_a_stop_is_found_with_its_deceleration_and_direction():
    got = events.stops(_slide_then_stop(), FPS, longest=4.0)
    assert len(got) == 1 and got[0]["frame"] == 32
    assert got[0]["decelMs2"] == pytest.approx(3.75) and got[0]["dir"] == [0.0, 1.0]


def test_standing_still_or_creeping_is_not_a_stop():
    assert events.stops([(0.0, 0.0, 0.0)] * 60, FPS, 4.0) == []
    creep = [(0.0, i * 0.001, 0.0) for i in range(60)] + [(0.0, 0.059, 0.0)] * 10
    assert events.stops(creep, FPS, 4.0) == []          # 3 cm/s < 2% of 4 m per second


def test_a_drop_lands_once_with_its_impact_speed():
    h = 0.5
    t_land = math.sqrt(2 * h / 9.81)
    pos = [(0.0, 0.0, max(0.0, h - 0.5 * 9.81 * (i / FPS) ** 2)) for i in range(40)]
    got = events.landings(pos, FPS, longest=0.3)
    assert len(got) == 1 and abs((got[0]["frame"] - 1) / FPS - t_land) <= 1.5 / FPS
    assert 2.0 <= got[0]["impactMs"] <= 3.2               # sqrt(2 g h) = 3.13, sampled a frame early


def test_overshoot_peaks_at_amp_and_is_gone_after_settle():
    xs = [settle.overshoot(i / 1000, 0.05, 0.3) for i in range(1000)]
    assert max(xs) == pytest.approx(0.05, rel=0.01) and xs[0] == 0.0
    assert all(abs(x) <= 0.04 * 0.05 for x in xs[300:])


def test_squash_starts_squashed_and_preserves_volume():
    assert settle.squash_z(0.0, 0.92, 0.3) == pytest.approx(0.92)
    assert settle.squash_z(0.5, 0.92, 0.3) == pytest.approx(1.0, abs=0.004)
    sz = settle.squash_z(0.0, 0.92, 0.3)
    assert sz * settle.squash_xy(sz) ** 2 == pytest.approx(1.0)
    assert settle.squash_z(0.0, 1.0, 0.3) == 1.0            # rigid subjects never squash


def test_suspension_class_params_and_settle_after_a_stop():
    assert suspension.ride_hz("sport") == 1.9 and suspension.ride_hz("unknown") == 1.3
    assert suspension.static_sag(0.35, 0.015) == pytest.approx(0.00525)
    p0 = suspension.pitch_after_stop(0.0, 6.0, 1.9, 0.4)
    assert p0 == pytest.approx(math.radians(6.0 / 9.81))
    assert abs(suspension.pitch_after_stop(1.5, 6.0, 1.9, 0.4)) < 0.01 * p0   # 1-2 bounces, then still
    assert suspension.heave_after_landing(0.0, 3.0, 1.9, 0.4, 0.05) == 0.0
    assert min(suspension.heave_after_landing(i / 100, 3.0, 1.9, 0.4, 0.05) for i in range(100)) >= -0.05


def test_wheel_angle_rolls_without_slip_about_the_axle():
    pos = [(0.0, i / 30, 0.0) for i in range(31)]            # 1 m along +y
    a = wheel_spin.wheel_angles(pos, [0.0] * 31, (1.0, 0.0, 0.0), 0.5)
    assert a[-1] == pytest.approx(-2.0)                      # right-hand rule about +x: rolling forward is negative
    side = [(i / 30, 0.0, 0.0) for i in range(31)]           # sliding along the axle: no roll
    assert wheel_spin.wheel_angles(side, [0.0] * 31, (1.0, 0.0, 0.0), 0.5)[-1] == pytest.approx(0.0)
    assert wheel_spin.slip(a, pos, 0.5) == pytest.approx(0.0, abs=1e-9)
