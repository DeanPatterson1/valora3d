"""float_drift (spec hover_bob, generalised; METHODS RB-08): the subject floats, bobbing slowly and turning a
few degrees per second, with a tiny pitch/roll sway. z = liftFrac h + bobFrac h sin(2 pi f t); yaw =
yawDegS t (|yawDegS| <= 20 by the manifest, far under the 45 deg/s P-C11 cap); pitch and roll <= SWAY_DEG.
Placement is float (the checker repairs ground -> float: placement_for_motion), so contact and ground
realism are off, as they already are for any floating subject. It never translates, stops or lands.
The sway tips a corner down by up to sin(SWAY_DEG) x the half footprint, so the lift is raised by that bound
(sway_drop, constant over the clip so the bob stays a pure sine): the lowest point of the tilted bounds keeps
the (liftFrac - bobFrac) h clearance (review chunk5 #5; a tall subject rises by a millimetre or two)."""
import math

from engine.motion_path import SubjectPose

SWAY_DEG = 1.5                   # (eng) pitch/roll sway amplitude, <= 2 deg
SWAY_HZ = (0.13, 0.17)           # (eng) two slow incommensurate sway rates


def sway_drop(profile):
    """Bound (m) on how far the sway lowers the bounds' lowest corner below the untilted base: |pitch|,
    |roll| <= SWAY_DEG about the ground-centre pivot drop x/y corners by sin a x half extents, and a base
    above the pivot by (1 - cos^2 a) x its height (yaw never changes z)."""
    lo, hi = profile.boundsMin, profile.boundsMax
    a = math.radians(SWAY_DEG)
    return (math.sin(a) * ((hi[0] - lo[0]) + (hi[1] - lo[1])) / 2.0
            + (1.0 - math.cos(a) ** 2) * max(0.0, lo[2]))


def sample(params, profile, t, duration):
    h = profile.sizeM[2]
    z = sway_drop(profile) + params["liftFrac"] * h + params["bobFrac"] * h * math.sin(2 * math.pi * params["bobHz"] * t)
    a = math.radians(SWAY_DEG)
    return SubjectPose(offset=(0.0, 0.0, z), yaw=math.radians(params["yawDegS"]) * t,
                       pitch=a * math.sin(2 * math.pi * SWAY_HZ[0] * t),
                       roll=a * math.sin(2 * math.pi * SWAY_HZ[1] * t + 1.0))


def still(params):
    return False


def flags(params):
    return {}
