"""plinth_spin (the owner's spin-on-plinth seed): the subject stands on a visible plinth (build.py) and turns
ONCE, a bounded eased turn of turnDeg inside [startS, startS + turnS], then holds. Never a continuous loop:
the turn is in_out_cubic (peak rate 3 x the mean turnDeg / turnS, capped at 45 deg/s by the checker's
spin_rate_cap) and the camera must move during it (spin_needs_camera_move), so no
params can reproduce the harness's constant-rate 360 turntable. The plinth raises the subject by its height
(PLINTH_H x longest): contact realism sits it on the plinth top."""
import math

from engine.easing import ease
from engine.motion_path import SubjectPose

PLINTH_H = 0.04        # (eng) plinth height, share of the subject's longest side
PLINTH_R = 0.6         # (eng) plinth radius, share of the footprint diagonal


def plinth_height(profile):
    return PLINTH_H * profile.longest


def plinth_radius(profile):
    return PLINTH_R * math.hypot(profile.sizeM[0], profile.sizeM[1])


def window(params, profile, duration):
    return params["startS"], params["startS"] + params["turnS"]


def turn(params, t):
    """The turn so far (radians), eased over the window, held after it."""
    u = (t - params["startS"]) / max(1e-6, params["turnS"])
    return math.radians(params["turnDeg"]) * ease("in_out_cubic", u)


def rest_s(params, profile, duration):
    return params["startS"] + params["turnS"]


def sample(params, profile, t, duration):
    return SubjectPose(offset=(0.0, 0.0, plinth_height(profile)), yaw=turn(params, t))


def still(params):
    return False


def flags(params):
    return {"stops": True}
