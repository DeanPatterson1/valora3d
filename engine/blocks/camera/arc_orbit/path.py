import math
from engine.easing import ease, settle
from engine.geometry import Pose


def sample(params, profile, u, target=None):
    cx, cy, cz = profile.center
    d = profile.radius * params["distance"]
    k = ease(params["easing"], settle(u, params["settleFrac"]))
    az = math.radians(params["startAzimuthDeg"] + params["sweepDeg"] * k)
    el = math.radians(params["elevationDeg"])
    horiz = d * math.cos(el)
    pos = (cx + horiz * math.cos(az), cy + horiz * math.sin(az), cz + d * math.sin(el))
    return Pose(position=pos, target=(cx, cy, cz), lens_mm=params["lensMm"])
