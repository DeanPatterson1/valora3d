"""Constant angular velocity, no easing and no settle: the T1-X1 signature by design."""
import math

from engine.geometry import Pose


def sample(params, profile, u, target=None):
    cx, cy, cz = profile.center
    d = profile.radius * params["distance"]
    az = math.radians(params["startAzimuthDeg"] + params["sweepDeg"] * u)
    el = math.radians(params["elevationDeg"])
    horiz = d * math.cos(el)
    pos = (cx + horiz * math.cos(az), cy + horiz * math.sin(az), cz + d * math.sin(el))
    return Pose(position=pos, target=(cx, cy, cz), lens_mm=params["lensMm"])
