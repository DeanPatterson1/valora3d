"""Round 12 realism layers, pure: the field's patchy meadow (bare ground, species drifts, lodged patches), the
wheels' way in and the ragged cut at the tyres; the night street's mixed lamp generations and the lamp the car is
parked under; the night camera's starburst; the committed scripts' round-12 values."""
import json
import math
from pathlib import Path

import pytest

from engine.catalog import Catalog
from engine.tests.test_director_package import _p
from engine.worlds import field_layout as F

ROOT = Path(__file__).parents[2]


def _grid(fn, n=70, step=0.23):
    return [fn(i * step, j * step) for i in range(n) for j in range(n)]


def test_the_meadow_is_patchy_at_several_scales_and_pure():
    v = _grid(lambda x, y: F.meadow(x, y, 7))
    assert all(0.0 <= a <= 1.0 for a in v)
    assert min(v) < F.BARE_HI and max(v) > F.MEADOW_HEIGHT[2]            # bare ground and full stands both occur
    assert F.meadow(1.3, 2.1, 7) == F.meadow(1.3, 2.1, 7) != F.meadow(1.3, 2.1, 8)
    h = [F.meadow_height(a) for a in v]
    assert min(h) == pytest.approx(F.MEADOW_HEIGHT[0]) and max(h) == pytest.approx(1.0)


def test_bare_ground_and_a_thinner_foreground_drop_plants():
    assert not F.meadow_drop(0.3, 0.4, 7, 0.9)                            # lush, far from a camera: kept
    pts = [(i * 0.011, j * 0.013) for i in range(60) for j in range(60)]
    bare = sum(F.meadow_drop(x, y, 7, 0.0) for x, y in pts) / len(pts)
    assert bare == pytest.approx(F.BARE_DROP, abs=0.06)
    fore = sum(F.meadow_drop(x, y, 7, 0.9, F.FORE_FLOOR) for x, y in pts) / len(pts)
    assert fore == pytest.approx(F.FORE_THIN, abs=0.06)


def test_species_drift_and_lodged_patches_lie_downwind():
    s = _grid(lambda x, y: F.species(x, y, 7))
    assert min(s) < 0.15 and max(s) > 0.85
    tilts = _grid(lambda x, y: F.lodge(x, y, 7, 90.0, (x * 7.13 + y * 3.71) % 1.0))
    assert all(0.0 <= t <= F.LODGE_DEG[1] for t, _ in tilts)
    lodged = [(t, d) for t, d in tilts if t >= F.LODGE_DEG[0]]
    assert lodged and all(abs(d - 90.0) <= 35.0 + 1e-9 for _, d in lodged)
    assert sum(1 for t, _ in tilts if t > F.TILT_DEG) < 0.4 * len(tilts)    # most of the meadow stands


def test_the_wheels_way_in_trails_behind_the_rear_axle():
    p = _p("sports_car")
    tracks = F.wheel_tracks(p)
    assert len(tracks) == 2
    big = max(p.wheels, key=lambda w: w["radius"])["contact"][1]            # the rear (bigger) tyres' side
    for (sx, sy), (bx, by), hw, L in tracks:
        assert math.copysign(1, by) == math.copysign(1, big) and abs(bx) < 1e-9
        assert F.TRACK_LEN_M[0] <= L <= F.TRACK_LEN_M[1] and hw > 0.1
        assert F.track_press(sx + 0.3 * bx, sy + 0.3 * by, tracks, 7) < 0.6
        assert F.track_press(sx + (L + 0.5) * bx, sy + (L + 0.5) * by, tracks, 7) == 1.0
    assert F.wheel_tracks(_p("mid_century_lounge_chair")) == []


def test_the_cut_at_the_tyres_is_ragged_and_only_there():
    p = _p("sports_car")
    cx, cy, _ = p.center
    cam = (cx + 3.0, cy - 5.0, 0.8)
    lines = F._sight_lines(p, [cam])
    half_w = max(F.SIGHT_W_MIN, F.SIGHT_W_K * p.longest)
    w = p.wheels[0]["contact"]
    near = (cam[0] + 0.92 * (w[0] - cam[0]), cam[1] + 0.92 * (w[1] - cam[1]))
    a, b = F.sight_cap(*near, lines, half_w), F.sight_cap(*near, lines, half_w, 1.6)
    assert b > a
    mid = (0.5 * (cam[0] + cx), 0.5 * (cam[1] + cy))                        # far from the body: unchanged
    assert F.sight_cap(*mid, lines, half_w, 1.6) == F.sight_cap(*mid, lines, half_w)
    k = _grid(lambda x, y: F.tyre_tuft(x, y, 7), n=30, step=0.03)
    assert F.TYRE_TUFT[0] - 1e-9 <= min(k) < 0.8 and max(k) > 1.2


def test_the_street_mixes_lamp_generations():
    from engine.blocks.world.night_street import build as N
    picks = [N.lamp_source(i / 200.0) for i in range(200)]
    ks = {k for k, _, _ in picks}
    assert len(ks) == len(N.LAMP_SOURCES) and min(ks) < 2500 < 3500 < max(ks)
    assert any(t != (1.0, 1.0, 1.0) and t[1] > t[0] for _, t, _ in picks)   # a tired lamp, a little green
    assert min(o for _, _, o in picks) < 0.6


def test_the_car_is_parked_under_a_lamp_that_stays_out_of_shot():
    from engine.geometry import project
    from engine.tests.test_round11_realism import _hook
    from engine.worlds import street_layout as S
    p = _p("sports_car")
    hero = _hook(p, Catalog.load(), azimuthDeg=-78)
    lay = S.layout(p, 5, hero=hero, aspect="9:16", cameras=[tuple(hero.position)])
    at = S.hero_lamp(p, lay, hero, "9:16")
    assert at is not None and at == S.hero_lamp(p, lay, hero, "9:16")
    tx, ty, d = project(hero, at, "9:16")
    assert d <= 0 or abs(tx) > 1.0 or abs(ty) > 1.0
    assert math.hypot(at[0] - p.center[0], at[1] - p.center[1]) < 8.0
    assert S.hero_lamp(p, lay, None, "9:16") is None


def test_the_night_camera_adds_a_faint_starburst_on_emitters_only():
    from engine.grade_plan import CAPTURE
    f = CAPTURE["night"]["flare"]
    assert f["type"] == "Streaks" and f["threshold"] > CAPTURE["night"]["glow"]["threshold"] and f["strength"] < 0.1
    assert "flare" not in CAPTURE["day"]


def test_round12_scripts_carry_their_values():
    load = lambda s: json.loads((ROOT / "harness" / "realism" / f"{s}.json").read_text(encoding="utf-8"))  # noqa
    fg = load("field_golden")
    assert fg["shots"][0]["camera"]["params"]["fstop"] == 2.8 and fg["lighting"]["params"]["fillRatio"] == 0.6
    sn = load("street_night")
    assert sn["world"]["params"]["neonAmount"] == 0.0     # round 13 replaced the r12 rig with practicals_only
    assert sn["grade"]["params"]["grain"] == 0.8
