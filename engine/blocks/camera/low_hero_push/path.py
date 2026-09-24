import math
from engine.easing import ease, settle
from engine.geometry import Pose

# Floor clearance so a "ground" camera never sits inside the floor plane.
MIN_HEIGHT_M = 0.03


def sample(params, profile, u, target=None):
    cx, cy, cz = profile.center
    k = ease(params["easing"], settle(u, params["settleFrac"]))
    d = profile.radius * params["distance"] * (1.0 - params["pushFrac"] * k)
    az = math.radians(params["azimuthDeg"])
    z = max(MIN_HEIGHT_M, params["heightFrac"] * profile.sizeM[2])
    pos = (cx + d * math.cos(az), cy + d * math.sin(az), z)
    return Pose(position=pos, target=(cx, cy, cz), lens_mm=params["lensMm"])
