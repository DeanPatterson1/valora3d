import math

import pytest

from engine.physics import sway, wind
from engine.tests.conftest import requires_blender


def test_direction_is_where_the_air_goes_world_azimuth_ccw_from_x():
    x, y, z = wind.vector(90.0, 4.0)
    assert (x, y, z) == pytest.approx((0.0, 4.0, 0.0), abs=1e-9)


@pytest.mark.parametrize("speed,force", [(0.0, 0), (0.8, 1), (3.0, 2), (7.0, 4), (13.0, 6), (20.0, 8), (40.0, 12)])
def test_beaufort(speed, force):
    assert wind.beaufort(speed) == force


def test_gust_envelope_and_calm():
    assert wind.envelope(4.0, 0.3) == pytest.approx((2.8, 5.2))
    assert wind.envelope(4.0, 1.0)[0] == 0.0
    assert wind.is_calm(0.2) and not wind.is_calm(0.8)


def test_bend_grows_with_speed_squared_and_is_capped():
    assert sway.bend_frac(0.0, 0.4) == 0.0
    assert sway.bend_frac(2.0, 0.4) == pytest.approx(0.02 * 4 * 0.68)
    assert sway.bend_frac(14.0, 0.0) == pytest.approx(math.tan(math.radians(25)))
    assert sway.tip_offset(0.5, 0.2, 2.0, 0.4) == pytest.approx(sway.bend_frac(2.0, 0.4) * 0.2 * 0.25)


def test_a_hanging_part_swings_about_its_pivot_without_stretching():
    # review fix (Task 21): a rigid rotation by atan(bend), not a cantilever shear (+10% length at the cap)
    pivot, tip = (0.1, 0.0, 0.4), (0.1, 0.0, 0.25)
    L = math.dist(pivot, tip)
    for speed in (2.0, 5.0, 30.0):
        p = sway.swing_point(tip, pivot, tip, wind.vector(0.0, speed), 0.4)
        assert math.dist(p, pivot) == pytest.approx(L, rel=1e-9)                 # length kept
        assert p[0] > tip[0]                                                      # downwind (+x)
        a, b = [t - q for t, q in zip(tip, pivot)], [t - q for t, q in zip(p, pivot)]
        ang = math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b)) / (L * L)))))
        assert ang == pytest.approx(math.degrees(sway.pivot_angle(speed, 0.4)), abs=1e-6)
    assert sway.pivot_angle(30.0, 0.0) == pytest.approx(math.radians(25.0))       # the cap
    mid = sway.swing_point((0.1, 0.0, 0.325), pivot, tip, wind.vector(0.0, 5.0), 0.4)
    assert math.dist(mid, pivot) == pytest.approx(L / 2, rel=1e-9)
    assert sway.swing_point(tip, pivot, tip, (0.0, 0.0, 0.0), 0.4) == pytest.approx(tip)   # calm: still
    up = sway.swing_point((0.0, 0.0, 0.2), (0.0, 0.0, 0.0), (0.0, 0.0, 0.2), wind.vector(90.0, 5.0), 0.4)
    assert up[1] > 0.0 and math.hypot(*up) == pytest.approx(0.2)                 # a stem leans downwind too


def test_calm_or_barely_moving_air_installs_no_sway():
    # review item 1: zero wind must not install a Scene-Time deformer (every frame would re-evaluate)
    assert sway.peak_speed(4.0, 0.3, 0.2) == pytest.approx(4.0 * (1 + 0.3 + 0.2))
    assert not sway.moves(0.0, 0.3, 0.2, 0.4)                       # studio: still air
    assert not sway.moves(0.3, 0.3, 0.2, 0.4)                       # under half a degree at the gust peak
    assert sway.moves(0.8, 0.3, 0.2, 0.4)                           # the outdoor default breeze
    assert math.degrees(sway.pivot_angle(sway.peak_speed(0.3, 0.3, 0.2), 0.4)) < sway.VISIBLE_DEG


def test_a_bent_blade_keeps_its_length():
    # review item 4: a pure horizontal shear stretched 12 cm blades by up to 39%
    for d in (0.0, 0.01, 0.05, 0.1, 0.119):
        dx, dy, dz = sway.bend_point(0.12, d, 0.0)
        assert math.dist((0.0, 0.0, 0.0), (dx, dy, 0.12 + dz)) == pytest.approx(0.12, abs=1e-9)
        assert dx == pytest.approx(d)
    dx, dy, dz = sway.bend_point(0.12, 0.3, 0.4)                      # past the length: lies flat, same length
    assert math.hypot(dx, dy) == pytest.approx(0.12) and dz == pytest.approx(-0.12)
    assert sway.bend_point(0.0, 0.0, 0.0) == (0.0, 0.0, 0.0)


@pytest.mark.blender
@requires_blender
def test_one_blender_wind_blows_where_the_script_says_and_consumers_agree(tmp_path):
    """Phase 5 Task 59 (H4): valora_wind sampled at 3 points x 3 frames points within 10 deg of the pinned
    +Y wind; the one WIND force field blows along +Y; wind_coherent is recorded (report-only) for the
    consumers present (lawn blades sway, haze wisps drift). Compile only, no render."""
    import json
    from pathlib import Path

    from engine.compiler.run import compile_scene
    from engine.profile import SubjectProfile
    from engine.tests.realism_catalog import catalog_with_fixtures
    fix = Path(__file__).parent / "fixtures"
    glb = Path(__file__).resolve().parents[2] / "assets-in" / "models" / "toycar" / "toycar.glb"
    if not glb.exists():
        pytest.skip("toycar model not present (local-only)")
    prof = SubjectProfile.from_dict(json.loads((fix / "profiles" / "toycar.json").read_text(encoding="utf-8")))
    s = json.loads((fix / "script_realism.json").read_text(encoding="utf-8"))
    s["world"] = {"id": "test_lawn", "params": {}}
    s["wind"] = {"id": "wind", "params": {"directionDeg": 90.0, "speedMs": 5.0}}
    s["effects"] = [{"id": "haze_volume", "params": {}}]
    res = compile_scene(s, prof, glb, tmp_path, render=False, skip_kinds=("grade",),
                        catalog=catalog_with_fixtures(tmp_path / "cat"), realism_probe=[1, 45, 90])
    wc = res["windCoherent"]
    assert wc["field"]["angleDeg"] is not None and wc["field"]["angleDeg"] <= 10.0, wc
    assert wc["field"]["meanWind"][1] > 0
    assert set(wc) >= {"field", "sway", "haze_volume"}, wc                       # every consumer present
    assert all(v["ok"] in (True, False, None) for v in wc.values())               # report-only: recorded
    wf = res["windField"]
    assert wf["type"] == "WIND" and wf["strength"] == pytest.approx(0.8 * 5.0) and 1 <= wf["seed"] <= 128
    assert wf["axis"] == pytest.approx([0.0, 1.0, 0.0], abs=1e-6)
