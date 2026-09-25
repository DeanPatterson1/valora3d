"""TEST ONLY: constant-speed glide of `metres` along +X over the clip, turning linearly to `yawDeg`."""
import math

from engine.motion_path import SubjectPose


def sample(params, profile, t, duration):
    u = min(max(t / duration, 0.0), 1.0) if duration > 0 else 0.0
    return SubjectPose(offset=(params.get("metres", 3.0) * u, 0.0, 0.0),
                       yaw=math.radians(params.get("yawDeg", 0.0)) * u)


def flags(params):
    return {"translates": params.get("metres", 3.0) > 0}
