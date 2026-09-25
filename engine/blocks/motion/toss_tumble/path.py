"""toss_tumble (METHODS RB-04): the subject is tossed in across the frame on a ballistic arc (apex
arcHeightFrac x height), slowed by timeScale (R4), spinning a whole number of turns (spins) about a STABLE
principal axis, and lands in its rest pose. The axis is the principal axis of max or min inertia (the last or
first principal_axes vector), never the intermediate one (Dzhanibekov tumble; flat thin objects deferred):
of the two, the one closest to horizontal and across the travel, so the flip reads. The body turns about its
centroid (the pose pivot) and is lifted just enough that no surface sample goes below the ground (it takes
off and lands on its own footprint). Air time T = 2 sqrt(2 H / g) / timeScale; the horizontal travel of
distanceFrac x longest runs from `direction` (right: from -x toward +x) into the rest position.
The perceived spin rate is capped at 360 deg/s by the checker (spin_rate_cap walks spins, then timeScale)."""
import math

from engine.motion_path import SubjectPose, rotation_matrix
from engine.physics import shape

G = 9.81
_PLAN = {}


def air_s(params, profile):
    H = params["arcHeightFrac"] * profile.sizeM[2]
    return 2.0 * math.sqrt(2.0 * H / G) / params["timeScale"]


def _plan(params, profile):
    dx = 1.0 if params.get("direction", "right") == "right" else -1.0
    key = (shape._content_key(profile.surfaceSamples or []), dx)
    hit = _PLAN.get(key)
    if hit is None:
        ss = shape.samples(profile)
        pts = [s["p"] for s in ss] or [list(profile.boundsMin), list(profile.boundsMax)]
        c = tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))
        axes = shape.principal_axes(ss)
        across = (0.0, 1.0, 0.0)                              # travel is along x: flip about the across axis
        stable = [axes[0], axes[2]]                           # min / max inertia (never the intermediate)
        ax = max(stable, key=lambda a: abs(sum(a[i] * across[i] for i in range(3))))
        n = math.sqrt(sum(x * x for x in ax)) or 1.0
        ax = tuple(x / n for x in ax)
        step = max(1, len(pts) // 400)                        # the lift reads a thinned surface
        rel = [tuple(p[i] - c[i] for i in range(3)) for p in pts[::step]]
        hit = _PLAN[key] = {"c": c, "axis": ax, "rel": rel, "dx": dx}
        if len(_PLAN) > 32:
            _PLAN.clear()
    return hit


def stable_axis(params, profile):
    return _plan(params, profile)["axis"]


def window(params, profile, duration):
    """When the subject is in the air (the spin happens here)."""
    return params["startS"], params["startS"] + air_s(params, profile)


def rest_s(params, profile, duration):
    return params["startS"] + air_s(params, profile)


def breaks(params, profile, duration):
    """Release and landing: the compiler keys both exactly (review chunk5 #3)."""
    return list(window(params, profile, duration))


def turn_angle(params, profile, t, duration):
    """The unwrapped spin about the stable axis (radians; review chunk5 #4)."""
    T = air_s(params, profile)
    u = min(max(t - params["startS"], 0.0), T)
    return 2.0 * math.pi * round(params["spins"]) * (u / T)


def sample(params, profile, t, duration):
    p = _plan(params, profile)
    T, ts = air_s(params, profile), params["timeScale"]
    H = params["arcHeightFrac"] * profile.sizeM[2]
    u = min(max(t - params["startS"], 0.0), T)
    s = u * ts                                                 # physical time since release
    z = math.sqrt(2.0 * G * H) * s - 0.5 * G * s * s
    th = 2.0 * math.pi * round(params["spins"]) * (u / T)
    q = (math.cos(th / 2), *(math.sin(th / 2) * x for x in p["axis"]))
    R = rotation_matrix(SubjectPose(quat=q))
    low = min(sum(R[2][j] * r[j] for j in range(3)) for r in p["rel"])
    rest_low = min(r[2] for r in p["rel"])
    lift = max(0.0, rest_low - low)                            # keep the turned body above its own footprint
    D = params["distanceFrac"] * profile.longest
    x = p["dx"] * D * (u / T - 1.0)
    return SubjectPose(offset=(x, 0.0, max(0.0, z) + lift), pivot=p["c"], quat=q)


def still(params):
    return False


def flags(params):
    return {"translates": True, "lands": True, "stops": True}
