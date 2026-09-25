"""topple (METHODS RB-03): a tall subject tips over its support edge and lands on its side. It needs a support
polygon (>= 3 points on the ground) and aspect height / narrowest footprint >= MIN_ASPECT; a squatter shape
would only rock, so supports() says it is too squat to tip over.

It pivots about the support-polygon edge whose outward normal points most along `direction` (right = +x,
left = -x, placed frame). The angle follows the inverted pendulum released just past balance, analytic:
theta(u) = theta_land (cosh(u / tau) - 1) / (cosh(FALL_K) - 1), tau = sqrt(rho / g) (rho: edge to centroid),
so it starts slowly and hits the ground fastest. theta_land is where the rotated surface first touches the
ground again (numeric, from the surface samples): the subject lies on its side. rock adds a small decaying
rock back up off that side (never through the ground). The pose rotates about the edge's axis vector
through the edge midpoint (the pose pivot), so the pivot edge stays at z = 0 at every sample."""
import math

from engine.motion_path import SubjectPose, rotation_matrix
from engine.physics import shape

G = 9.81
MIN_ASPECT = 1.3       # (eng) height / narrowest footprint below this does not topple convincingly
FALL_K = 3.0           # (eng) the fall lasts FALL_K pendulum times
ROCK_DEG, ROCK_S, ROCK_N = 4.0, 0.35, 2   # (eng) the rock: amplitude, period, count (1-2 rocks)
LAND_STEP = math.radians(0.5)


def aspect(profile):
    return profile.sizeM[2] / max(1e-9, min(profile.sizeM[0], profile.sizeM[1]))


def supports(params, profile):
    if aspect(profile) < MIN_ASPECT:
        return False, "this shape is too squat to tip over"
    return True, ""


def _edge(params, profile):
    """(a, b, axis unit, outward normal) of the support edge facing the direction."""
    poly = shape.support_polygon(shape.samples(profile))
    want = (1.0, 0.0) if params.get("direction", "right") == "right" else (-1.0, 0.0)
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    best = None
    for a, b in zip(poly, poly[1:] + poly[:1]):
        ex, ey = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(ex, ey)
        if ln < 1e-9:
            continue
        nx, ny = ey / ln, -ex / ln
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        if nx * (mx - cx) + ny * (my - cy) < 0:
            nx, ny = -nx, -ny                                   # outward
        score = nx * want[0] + ny * want[1]
        if best is None or score > best[0]:
            best = (score, a, b, (nx, ny))
    _, a, b, n = best
    ln = math.hypot(b[0] - a[0], b[1] - a[1])
    return (a[0], a[1], 0.0), (b[0], b[1], 0.0), ((b[0] - a[0]) / ln, (b[1] - a[1]) / ln, 0.0), n


def _axis_quat(axis, th):
    return (math.cos(th / 2), *(math.sin(th / 2) * x for x in axis))


_PLAN = {}


def _plan(params, profile):
    key = (shape._content_key(profile.surfaceSamples or []), params.get("direction", "right"))
    hit = _PLAN.get(key)
    if hit is not None:
        return hit
    a, b, e, n = _edge(params, profile)
    w = (-n[1], n[0], 0.0)                      # up x n: the top turns outward, along n
    pv = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0.0)
    pts = [s["p"] for s in shape.samples(profile)]
    c = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
    rho = math.dist(c, pv)
    far = [p for p in pts if (p[0] - pv[0]) * n[0] + (p[1] - pv[1]) * n[1] < -1e-3 * profile.longest or p[2] > 1e-3 * profile.longest]

    def lowest(th):
        R = rotation_matrix(SubjectPose(quat=_axis_quat(w, th)))
        return min(sum(R[2][j] * (p[j] - pv[j]) for j in range(3)) for p in far) if far else 0.0

    th = LAND_STEP
    while th < math.pi and lowest(th) > 0.0:
        th += LAND_STEP
    lo, hi = th - LAND_STEP, th
    for _ in range(30):
        mid = (lo + hi) / 2
        if lowest(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    hit = _PLAN[key] = {"axis": w, "pivot": pv, "land": lo, "tau": math.sqrt(max(rho, 1e-6) / G), "edge": (a, b)}
    if len(_PLAN) > 32:
        _PLAN.clear()
    return hit


def fall_s(params, profile):
    return FALL_K * _plan(params, profile)["tau"]


def rest_s(params, profile, duration):
    return params["startS"] + fall_s(params, profile) + (ROCK_N * ROCK_S if params.get("rock") else 0.0)


def angle(params, profile, t):
    p = _plan(params, profile)
    u = t - params["startS"]
    T = fall_s(params, profile)
    if u <= 0:
        return 0.0
    if u < T:
        return p["land"] * (math.cosh(u / p["tau"]) - 1.0) / (math.cosh(FALL_K) - 1.0)
    th = p["land"]
    if params.get("rock"):
        v = u - T
        if v < ROCK_N * ROCK_S:
            k = math.exp(-2.0 * v / (ROCK_N * ROCK_S))
            th -= math.radians(ROCK_DEG) * k * abs(math.sin(math.pi * v / ROCK_S))   # rocks up off its side
    return th


def sample(params, profile, t, duration):
    p = _plan(params, profile)
    return SubjectPose(pivot=p["pivot"], quat=_axis_quat(p["axis"], angle(params, profile, t)))


def still(params):
    return False


def flags(params):
    return {"stops": True, "lands": True}
