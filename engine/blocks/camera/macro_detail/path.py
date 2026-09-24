import math
from engine.easing import ease, settle
from engine.geometry import Pose
from engine.targets import DEFAULT_NORMAL

MIN_HEIGHT_M = 0.01
LOOK_DRIFT = 0.15  # how much the aim follows a slide; small keeps the target near centre


def sample(params, profile, u, target=None):
    point, normal = (target.point, target.normal) if target else (profile.center, DEFAULT_NORMAL)
    az = math.atan2(normal[1], normal[0]) + math.radians(params["azimuthOffsetDeg"])
    el0 = math.asin(max(-1.0, min(1.0, normal[2])))
    el = max(math.radians(-10.0), min(math.radians(80.0), el0 + math.radians(params["elevationOffsetDeg"])))
    k = ease(params["easing"], settle(u, params["settleFrac"]))
    d0 = profile.radius * params["distance"]
    out = (math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))
    right = (-math.sin(az), math.cos(az), 0.0)
    if params["move"] == "push":
        d, s = d0 * (1.0 - params["pushFrac"] * k), 0.0
    else:
        d, s = d0, (k - 0.5) * params["slideFrac"] * d0
    pos = [point[i] + out[i] * d + right[i] * s for i in range(3)]
    pos[2] = max(pos[2], MIN_HEIGHT_M)
    look = tuple(point[i] + right[i] * s * LOOK_DRIFT for i in range(3))
    return Pose(position=tuple(pos), target=look, lens_mm=params["lensMm"])
