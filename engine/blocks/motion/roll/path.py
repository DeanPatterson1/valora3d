"""roll (METHODS RB-02): a round subject rolls in on its side and comes to rest in its ingest pose. It needs a
high-confidence roll axis (engine/physics/shape.roll_axis: a flat principal axis with a round side) and must
already rest on that round side (its axis line at height r), else supports() says it can't roll convincingly.

Travel is perpendicular to the axis and horizontal; the rotation is about the axis VECTOR (the PCA axis is
arbitrary, so never a local Euler axis: the pose carries a quaternion), through the axis line at height r
(the pose pivot), by angle = travel / r: no slip, and the contact line stays at z = 0. The speed decays like
rolling resistance, v ~ exp(-t / tau), blended to exactly 0 at the roll time T so the stop is real:
s(u) = D F(u) / F(T), F(u) = tau (1 - exp(-u / tau)) - u exp(-T / tau), tau = T / 2. T grows with the
distance, T = 2 sqrt(D / A_ROLL) in [ROLL_MIN_S, ROLL_MAX_S]: a 1.2 m roll takes 4 s (tau 2 s, the plan's
number), a can's 18 cm about 1.5 s, so a short roll is over before the clip's first detail shot.
direction right travels along axis x up, left the other way (placed frame)."""
import math

from engine.motion_path import SubjectPose
from engine.physics import shape

A_ROLL = 0.3           # (eng) m/s^2: T = 2 sqrt(D / A_ROLL), so a 1.2 m roll lasts 4 s (tau = T / 2 = 2 s)
ROLL_MIN_S, ROLL_MAX_S = 1.0, 4.0   # (eng) the roll time's bounds
AXIS_FLAT = 0.1        # (eng) |axis.z| above this rolls in a wobble: not supported
ON_SIDE = 0.15         # (eng) the axis line must sit at r +- 15% (the subject rests on its round side)


_AXIS = {}


def _axis(profile):
    """(roll axis, sample centroid), cached per sample content: every pose sample needs it, and the compiler
    samples a fast roll many times a frame (review chunk5 #4)."""
    key = shape._content_key(profile.surfaceSamples or [])
    hit = _AXIS.get(key)
    if hit is None:
        ss = shape.samples(profile)
        ra = shape.roll_axis(ss)
        pts = [s["p"] for s in ss]
        c = [sum(p[i] for p in pts) / len(pts) for i in range(3)] if pts else list(profile.center)
        if len(_AXIS) > 32:
            _AXIS.clear()
        hit = _AXIS[key] = (ra, c)
    return hit


def supports(params, profile):
    ra, c = _axis(profile)
    if ra["confidence"] != "high" or ra["radius"] <= 0:
        return False, "this shape can't roll convincingly (no round side)"
    if abs(ra["axis"][2]) > AXIS_FLAT:
        return False, "this shape can't roll convincingly (its round side is not lying flat)"
    if abs(c[2] - ra["radius"]) > ON_SIDE * ra["radius"]:
        return False, "this shape can't roll convincingly (it is not resting on its round side)"
    return True, ""


def _geometry(params, profile):
    ra, c = _axis(profile)
    ax, ay = ra["axis"][0], ra["axis"][1]
    n = math.hypot(ax, ay) or 1.0
    ax, ay = ax / n, ay / n
    sign = 1.0 if params.get("direction", "right") == "right" else -1.0
    d = (sign * ay, -sign * ax, 0.0)               # travel: axis x up (right) or the reverse (left)
    w = (-d[1], d[0], 0.0)                         # up x d: rolling toward d turns about +w
    return d, w, max(ra["radius"], 1e-6), (c[0], c[1], ra["radius"])


def distance(params, profile):
    return params["distanceFrac"] * profile.longest


def roll_s(params, profile):
    return min(ROLL_MAX_S, max(ROLL_MIN_S, 2.0 * math.sqrt(distance(params, profile) / A_ROLL)))


def _share(u, T):
    tau = T / 2.0
    F = lambda x: tau * (1.0 - math.exp(-x / tau)) - x * math.exp(-T / tau)   # noqa: E731
    u = min(max(u, 0.0), T)
    return F(u) / F(T)


def rest_s(params, profile, duration):
    return params["startS"] + roll_s(params, profile)


def breaks(params, profile, duration):
    """It starts rolling and stops: the compiler keys both exactly (review chunk5 #3)."""
    return [params["startS"], rest_s(params, profile, duration)]


def turn_angle(params, profile, t, duration):
    """The unwrapped turn about the roll axis (radians): travel / r, no slip (review chunk5 #4)."""
    _d, _w, r, _pv = _geometry(params, profile)
    D = distance(params, profile)
    return (D * _share(t - params["startS"], roll_s(params, profile)) - D) / r


def sample(params, profile, t, duration):
    d, w, r, pv = _geometry(params, profile)
    D = distance(params, profile)
    s = D * _share(t - params["startS"], roll_s(params, profile)) - D   # <= 0: still to go, 0 at rest
    th = s / r
    q = (math.cos(th / 2), *(math.sin(th / 2) * x for x in w))
    return SubjectPose(offset=(d[0] * s, d[1] * s, 0.0), pivot=pv, quat=q)


def still(params):
    return False


def flags(params):
    return {"translates": True, "stops": True}
