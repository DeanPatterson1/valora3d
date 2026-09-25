"""Task 69: weather probe verdicts (pure, synthetic numbers)."""
from engine.physics import probes as P


def test_no_particles_in_subject():
    lo, hi = (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)
    pts = {1: [(2.0, 2.0, 2.0)] * 999 + [(0.5, 0.5, 0.5)], 2: [(-1.0, 0.5, 0.5)] * 1000}
    ok, share = P.no_particles_in_subject(pts, {1: (lo, hi), 2: (lo, hi)})
    assert ok and share == 1 / 2000
    ok, share = P.no_particles_in_subject({1: [(0.5, 0.5, 0.5)] * 3 + [(2.0, 0.0, 0.0)]}, {1: (lo, hi)})
    assert not ok and share == 0.75
    assert P.no_particles_in_subject({1: []}, {1: (lo, hi)}) == (True, 0.0)


def test_velocity_present():
    assert P.velocity_present({"rain": True, "snow": True}) is True
    assert P.velocity_present({"rain": True, "snow": False}) is False
    assert P.velocity_present({}) is None


def test_streak_length_within_40_percent():
    # 6.5 m/s, 180 deg at 30 fps -> 0.108 m; at 500 px/m that is 54 px
    assert P.streak_ok(54.0, 6.5, 0.5, 30, 500.0) and P.streak_ok(33.0, 6.5, 0.5, 30, 500.0)
    assert not P.streak_ok(30.0, 6.5, 0.5, 30, 500.0) and not P.streak_ok(80.0, 6.5, 0.5, 30, 500.0)
    assert not P.streak_ok(10.0, 0.0, 0.5, 30, 500.0)
