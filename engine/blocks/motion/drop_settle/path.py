"""drop_settle (spec drop_in; METHODS RB-01): the subject drops in from above and settles with analytic
bounces. Heights h * e^(2n) (restitution e), air time from real gravity slowed by timeScale (R4: the one
place a clock is slowed, never for weather), a small tilt that is gone by the last contact. Ends in the
ingest rest pose (placed z = 0). Before startS it hangs at the drop height (off-frame above a framed shot).

The tilt never pushes a corner through the floor: it is limited to asin(z / half diagonal) at height z, so
the tilted footprint is always above the ground (z >= 0 at every sample, tested)."""
import math

from engine.motion_path import SubjectPose

G = 9.81


def _plan(params, profile):
    h0 = params["heightFrac"] * profile.sizeM[2]
    e, ts = params["restitution"], params["timeScale"]
    hs = [h0] + [h0 * e ** (2 * k) for k in range(1, int(round(params["bounces"])) + 1)]
    fall = math.sqrt(2 * h0 / G) / ts
    arcs = [2 * math.sqrt(2 * h / G) / ts for h in hs[1:]]
    return hs, fall, arcs


def total_s(params, profile):
    _, fall, arcs = _plan(params, profile)
    return fall + sum(arcs)


def contacts(params, profile):
    """Script times of every ground contact (first landing, then each bounce's end)."""
    _, fall, arcs = _plan(params, profile)
    out, t = [], params["startS"] + fall
    out.append(t)
    for a in arcs:
        t += a
        out.append(t)
    return out


def height(params, profile, t):
    hs, fall, arcs = _plan(params, profile)
    ts = params["timeScale"]
    u = t - params["startS"]
    if u <= 0:
        return hs[0]
    if u < fall:
        s = u * ts
        return max(0.0, hs[0] - 0.5 * G * s * s)
    u -= fall
    for h, a in zip(hs[1:], arcs):
        if u < a:
            s = (u - a / 2) * ts
            return max(0.0, h - 0.5 * G * s * s)
        u -= a
    return 0.0


def rest_s(params, profile, duration):
    return params["startS"] + total_s(params, profile)


def sample(params, profile, t, duration):
    z = height(params, profile, t)
    start, end = params["startS"], rest_s(params, profile, duration)
    k = 1.0 if t <= start else max(0.0, 1.0 - (t - start) / max(1e-6, end - start))
    half = 0.5 * math.hypot(profile.sizeM[0], profile.sizeM[1]) or 1.0
    tilt = min(math.radians(params.get("tiltDeg", 0.0)) * k, math.asin(min(1.0, z / half)))
    return SubjectPose(offset=(0.0, 0.0, z), pitch=tilt)


def still(params):
    return False


def flags(params):
    return {"lands": True, "stops": True}
