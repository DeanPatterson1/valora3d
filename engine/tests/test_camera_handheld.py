"""Task 82: handheld_operator (port of render-studio film_camera._operate, made pure), pure."""
import cmath
import math

import pytest

from engine.camera_context import ShotContext
from engine.checker import check
from engine.director.axes import _opener_ok
from engine.easing import ease, settle
from engine.geometry import _basis
from engine.tests.camera_helpers import CAT, bearing_rate, defaults, path_module, sample, script_with
from engine.tests.test_director_package import _p

HAND = sample("handheld_operator")
MOD = path_module("handheld_operator")


def _ctx(seconds=3.0):
    return ShotContext(seconds)


def _base(prm, p, u):
    """The Task 82 base path, written out: an arc at distance x radius, height heightFrac x height."""
    cx, cy, cz = p.center
    k = ease(prm["easing"], settle(u, prm["settleFrac"]))
    d = p.radius * prm["distance"] * ((1.0 - prm["pushFrac"] * k) if prm["path"] == "walk_in" else 1.0)
    az = math.radians(prm["azimuthDeg"] + (prm["arcDeg"] * k if prm["path"] == "walk_arc" else 0.0))
    z = max(0.03, prm["heightFrac"] * p.sizeM[2])
    return (cx + d * math.cos(az), cy + d * math.sin(az), z), (cx, cy, cz)


@pytest.mark.parametrize("path", ["walk_arc", "walk_in", "stand"])
@pytest.mark.parametrize("u", [0.0, 0.5, 1.0])
def test_zero_shake_is_exactly_the_base_path(path, u):
    p = _p("sports_car")
    prm = {**defaults("handheld_operator"), "shake": 0.0, "path": path}
    pose = HAND(prm, p, u, ctx=_ctx())
    pos, tgt = _base(prm, p, u)
    bob = MOD.bob_m(prm, p, u * 3.0) if path != "stand" else 0.0
    assert pose.position == pytest.approx((pos[0], pos[1], pos[2] + bob), abs=1e-12)
    assert pose.target == pytest.approx(tgt, abs=1e-12) and pose.roll == 0.0


def test_stand_without_shake_is_a_still_camera():
    p = _p("pocket_watch")
    prm = {**defaults("handheld_operator"), "shake": 0.0, "path": "stand"}
    poses = {HAND(prm, p, k / 50, ctx=_ctx()) for k in range(51)}
    assert len(poses) == 1


def test_same_seed_same_path_other_seed_differs():
    p = _p("sneaker")
    prm = defaults("handheld_operator")
    a = [HAND(prm, p, k / 30, ctx=_ctx()) for k in range(31)]
    assert a == [HAND(prm, p, k / 30, ctx=_ctx()) for k in range(31)]
    b = [HAND({**prm, "noiseSeed": 4242.0}, p, k / 30, ctx=_ctx()) for k in range(31)]
    assert a != b
    assert HAND({**prm, "noiseSeed": 7.4}, p, 0.3, ctx=_ctx()) == HAND({**prm, "noiseSeed": 7.0}, p, 0.3, ctx=_ctx())


@pytest.mark.parametrize("model", ["sports_car", "pocket_watch"])
@pytest.mark.parametrize("shake", [0.35, 1.0])
def test_the_shake_amplitude_bound_holds(model, shake):
    """<= 1.5 deg rotation and <= 2 cm x radius translation (METHODS R5), on top of the base path + bob."""
    p = _p(model)
    prm = {**defaults("handheld_operator"), "shake": shake}
    for seed in (0.0, 1.0, 999.0):
        q = {**prm, "noiseSeed": seed}
        for k in range(301):
            u = k / 300
            pose = HAND(q, p, u, ctx=_ctx(6.0))
            base, tgt = _base(q, p, u)
            bob = MOD.bob_m(q, p, u * 6.0)
            dev = math.dist(pose.position, (base[0], base[1], base[2] + bob))
            assert dev <= 0.02 * p.radius * shake + 1e-12
            assert abs(math.degrees(pose.roll)) <= 1.5 * shake + 1e-9
            f0, _, _ = _basis(type(pose)(tuple(base), tgt, pose.lens_mm))
            f1, _, _ = _basis(pose)
            ang = math.degrees(math.acos(max(-1.0, min(1.0, sum(a * b for a, b in zip(f0, f1))))))
            assert ang <= 1.5 * shake + 1e-6 + math.degrees(math.atan2(0.02 * p.radius * shake + abs(bob),
                                                                       math.dist(base, tgt)))


def test_the_footfall_peak_lies_in_the_step_band():
    """A DFT of camera z (256 samples over an 8 s walk, the slow drift below 1 Hz set aside) peaks at the step
    rate, which lies in 1.6-2.0 Hz for every seed."""
    p = _p("sports_car")
    secs, n = 8.0, 256
    for seed in (0.0, 3.0, 17.0, 60000.0):
        prm = {**defaults("handheld_operator"), "noiseSeed": seed}
        f_step = MOD.step_hz(prm)
        assert 1.6 <= f_step <= 2.0
        z = [HAND(prm, p, k / (n - 1), ctx=_ctx(secs)).position[2] for k in range(n)]
        mean = sum(z) / n
        dt = secs / (n - 1)
        best = max(range(1, n // 2), key=lambda j: abs(sum((z[k] - mean) * cmath.exp(-2j * math.pi * j * k / n)
                                                          for k in range(n))) if j / (n * dt) >= 1.0 else -1)
        f_peak = best / (n * dt)
        assert abs(f_peak - f_step) <= 1.0 / (n * dt) + 1e-9, (seed, f_peak, f_step)
        assert 1.6 - 1.0 / (n * dt) <= f_peak <= 2.0 + 1.0 / (n * dt)


def test_bearing_rate_cap_hook_rule_and_checker():
    for model in ("sports_car", "pocket_watch"):
        assert bearing_rate("handheld_operator", _p(model)) <= 80.0
    assert _opener_ok(CAT.get("camera", "handheld_operator"))
    r = check(script_with("handheld_operator", {}, world="rain_courtyard", lighting="hdri_only"), _p("sports_car"), CAT)
    assert r.ok, [(i.code, i.message) for i in r.issues if i.severity == "error"]


def test_the_base_path_settles_still():
    p = _p("sports_car")
    prm = {**defaults("handheld_operator"), "shake": 0.0, "path": "walk_in", "settleFrac": 0.2}
    eps = 1e-4
    for u in (0.0, 1.0):
        a = _base(prm, p, max(0.0, u - eps))[0]
        b = _base(prm, p, min(1.0, u + eps))[0]
        assert math.dist(a, b) < 1e-7


def test_the_shot_length_comes_from_the_context():
    """Footfalls run in real seconds: the same u in a longer shot is a later moment."""
    p = _p("sports_car")
    prm = defaults("handheld_operator")
    assert HAND(prm, p, 0.5, ctx=_ctx(2.0)) != HAND(prm, p, 0.5, ctx=_ctx(6.0))
    assert HAND(prm, p, 0.5) == HAND(prm, p, 0.5, ctx=_ctx(3.0))          # no context: 3 s (DEFAULT_SHOT_S)


def test_every_call_site_binds_the_shot_length():
    """camera_sampler binds ctx for a shotContext camera; the compiler's keys use it (a 6 s shot's mid-frame is
    the 3 s moment, not the context-free 1.5 s one)."""
    from engine.camera_context import camera_sampler
    from engine.compiler.timeline import camera_keys
    from engine.script import validate_and_repair
    p = _p("sports_car")
    s = script_with("handheld_operator", {}, world="rain_courtyard", lighting="hdri_only")
    s["shots"][2]["startS"], s["shots"][2]["endS"] = 3.5, 5.5
    s = validate_and_repair(s, CAT)[0]
    sh = s["shots"][2]
    bound = camera_sampler(CAT, sh)
    prm = sh["camera"]["params"]
    assert bound(prm, p, 0.4) == HAND(prm, p, 0.4, ctx=ShotContext(2.0, 3.5))
    assert camera_sampler(CAT, s["shots"][0]) is CAT.load_camera_path("low_hero_push")    # others: unchanged
    keys = [k for k in camera_keys(s, p, CAT) if k.shot == 2 and float(k.frame).is_integer()]
    fps = s["format"]["fps"]
    from engine.compiler.timeline import shot_u
    k = keys[len(keys) // 2]
    u = shot_u(sh, (k.frame - 1) / fps, fps)
    assert k.pose == HAND(prm, p, u, ctx=ShotContext(2.0, 3.5))
