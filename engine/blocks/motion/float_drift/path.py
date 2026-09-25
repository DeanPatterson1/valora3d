"""float_drift (spec hover_bob, generalised; METHODS RB-08): the subject floats, bobbing slowly and turning a
few degrees per second, with a tiny pitch/roll sway. z = liftFrac h + bobFrac h sin(2 pi f t); yaw =
yawDegS t (|yawDegS| <= 20 by the manifest, far under the 45 deg/s P-C11 cap); pitch and roll <= SWAY_DEG.
Placement is float (the checker repairs ground -> float: placement_for_motion), so contact and ground
realism are off, as they already are for any floating subject. It never translates, stops or lands."""
import math

from engine.motion_path import SubjectPose

SWAY_DEG = 1.5                   # (eng) pitch/roll sway amplitude, <= 2 deg
SWAY_HZ = (0.13, 0.17)           # (eng) two slow incommensurate sway rates


def sample(params, profile, t, duration):
    h = profile.sizeM[2]
    z = params["liftFrac"] * h + params["bobFrac"] * h * math.sin(2 * math.pi * params["bobHz"] * t)
    a = math.radians(SWAY_DEG)
    return SubjectPose(offset=(0.0, 0.0, z), yaw=math.radians(params["yawDegS"]) * t,
                       pitch=a * math.sin(2 * math.pi * SWAY_HZ[0] * t),
                       roll=a * math.sin(2 * math.pi * SWAY_HZ[1] * t + 1.0))


def still(params):
    return False


def flags(params):
    return {}
