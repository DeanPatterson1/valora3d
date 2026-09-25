"""Review chunk 6 (checker items #1, #3, #5)."""
from engine.checker import check
from engine.tests.camera_helpers import CAT, script_with
from engine.tests.test_director_package import _p


def _errors(r):
    return {i.code for i in r.issues if i.severity == "error"}


def test_a_reveal_opener_is_a_bad_hook():
    """#5: reveal_rise starts tight on a detail (framed_from > 0), so it cannot open, even when supplied directly."""
    s = script_with("reveal_rise", {}, index=0)
    s["shots"][0]["purpose"] = "hook"
    r = check(s, _p("sports_car"), CAT)
    assert "seq_bad_hook" in _errors(r)


def test_a_flyby_is_measured_by_the_sweep_cap():
    """#3: follows 'subject' exempts only the camera car that moves with the subject (side/lead/tail). A flyby is
    anchored at the roadside and pans: a 40 km/h pass sweeps its view like any anchor camera, so the cap binds,
    measured with its context-bound sampler."""
    from engine.motion_rules import CAMERA_RATE_CAP_DEG_S, _bearing_rate
    from engine.script import validate_and_repair
    from engine.tests.test_camera_rolling_track import drive_script
    p = _p("sports_car")
    raw = validate_and_repair(drive_script("rolling_track", {"mode": "flyby", "distance": 1.5}), CAT)[0]
    assert _bearing_rate(raw, CAT, p) > CAMERA_RATE_CAP_DEG_S          # the pass really sweeps the view
    r = check(drive_script("rolling_track", {"mode": "flyby", "distance": 1.5}), p, CAT)
    assert "vehicle_speed_cap" in {i.code for i in r.issues}
    assert _bearing_rate(r.script, CAT, p) <= CAMERA_RATE_CAP_DEG_S + 1e-6 or \
        r.script["subject"]["motion"]["params"]["speedKmh"] == CAT.get("motion", "drive")["params"]["speedKmh"]["min"]
    side = check(drive_script("rolling_track", {}), p, CAT)                # the camera car keeps the real speed
    assert side.script["subject"]["motion"]["params"]["speedKmh"] == 40.0


def _excursion(p, us_out):
    """A still camera 4 radii off +x; the subject is in frame except at the progress values in us_out (a dart
    off-screen and back between two of the 12 coarse samples)."""
    from dataclasses import replace
    from engine.geometry import Pose
    cx, cy, cz = p.center

    def sample(params, prof, u, target=None):
        return Pose(position=(cx + params["distance"] * p.radius, cy, cz), target=(cx, cy, cz), lens_mm=35.0)

    far = replace(p, boundsMin=[p.boundsMin[0], p.boundsMin[1] + 50 * p.radius, p.boundsMin[2]],
                  boundsMax=[p.boundsMax[0], p.boundsMax[1] + 50 * p.radius, p.boundsMax[2]])

    def moving(u):
        live = far if any(abs(u - v) < 1e-9 for v in us_out) else p
        return p, None, live, None
    return sample, moving


def test_an_excursion_between_the_coarse_samples_is_caught_on_rendered_frames():
    """#1: judge a moving subject at every rendered frame, not only at the 12 coarse samples: a subject that
    leaves the frame between two samples (u = 5.5/11) and comes back is an exit."""
    from engine.checker import SAMPLES_PER_SHOT, _shot_verdict, frame_us
    p = _p("sports_car")
    shot = {"startS": 0.0, "endS": 3.0}
    us = frame_us(shot, 30)
    assert len(us) >= 90 and us[0] == 0.0 and us[-1] == 1.0
    coarse = [k / (SAMPLES_PER_SHOT - 1) for k in range(SAMPLES_PER_SHOT)]
    between = min((u for u in us if all(abs(u - c) > 1e-6 for c in coarse)), key=lambda u: abs(u - 5.5 / 11))
    sample, moving = _excursion(p, [between])
    prm = {"distance": 4.0}
    assert _shot_verdict(sample, prm, p, "full", "16:9", None, moving) == "ok"            # the coarse grid misses it
    assert _shot_verdict(sample, prm, p, "full", "16:9", None, moving, us=us) == "exit"
    # the hook's entrance: in, out between samples, back in: still an exit on the rendered frames
    assert _shot_verdict(sample, prm, p, "full", "16:9", None, moving, entrance=True, us=us) == "exit"
