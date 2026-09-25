"""slide_in: the subject glides in along the ground and stops with friction (constant deceleration), then holds
in its rest pose. Travel s(tau) = d (1 - (1 - tau)^2) for tau = (t - startS) / durationS on [0, 1], so its
speed falls linearly to exactly 0 at the stop. It enters along directionDeg (world azimuth it travels
TOWARD, 0 = +x) from d = distanceFrac x longest back along that line and ends where the subject stands, so
the hero frame is the rest pose. The subject does not turn. In the studio (driveLaneM 0) the checker caps
the travel at 0.2 x longest (distanceParam, motion_travel_capped); outdoors it may use the drive lane."""
import math

from engine.motion_path import SubjectPose


def travel(params, t):
    """Metres travelled so far as a share of the distance: 0 before, 1 after, constant deceleration between."""
    tau = min(max((t - params["startS"]) / max(1e-6, params["durationS"]), 0.0), 1.0)
    return 1.0 - (1.0 - tau) ** 2


def rest_s(params, profile, duration):
    return params["startS"] + params["durationS"]


def sample(params, profile, t, duration):
    d = params["distanceFrac"] * profile.longest
    a = math.radians(params["directionDeg"])
    back = d * (1.0 - travel(params, t))           # still to go
    return SubjectPose(offset=(-back * math.cos(a), -back * math.sin(a), 0.0))


def still(params):
    return params["distanceFrac"] <= 0.0


def flags(params):
    return {"translates": True, "stops": True}
