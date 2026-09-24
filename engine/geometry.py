"""Camera maths shared by the checker (phase 1) and the compiler (phase 2). Stdlib only."""
import math
from dataclasses import dataclass

SENSOR_MM = 36.0
IN_FRAME_TOLERANCE = 1.02  # ndc beyond ±1.02 counts as out of frame


@dataclass(frozen=True)
class Pose:
    position: tuple
    target: tuple
    lens_mm: float


def aspect_wh(aspect):
    w, h = aspect.split(":")
    return int(w), int(h)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    n = math.sqrt(_dot(a, a))
    if n == 0:
        raise ValueError("camera position equals target")
    return (a[0] / n, a[1] / n, a[2] / n)


def _basis(pose):
    """Return (forward, right, up) for a look-at camera, in world space.

    The basis is built with world Z-up: "up" is (0, 0, 1) unless the forward
    vector is nearly vertical (|fwd.z| >= 0.999), in which case it switches to
    world Y-up (0, 1, 0) to avoid a degenerate cross product looking straight
    up or down.

    This is the ONE place camera orientation is derived. The phase-2 Blender
    compiler MUST build its camera rotation from this same function rather
    than from a TRACK_TO constraint, or the checker's framing math and the
    actual render will disagree.
    """
    fwd = _norm(_sub(pose.target, pose.position))
    up_world = (0.0, 0.0, 1.0) if abs(fwd[2]) < 0.999 else (0.0, 1.0, 0.0)
    right = _norm(_cross(fwd, up_world))
    up = _cross(right, fwd)
    return fwd, right, up


def _half_tans(pose, aspect):
    w, h = aspect_wh(aspect)
    half_big = (SENSOR_MM / 2) / pose.lens_mm
    if w >= h:
        return half_big, half_big * h / w
    return half_big * w / h, half_big


def project(pose, point, aspect):
    """Return (ndc_x, ndc_y, depth). ndc in [-1, 1] is inside the frame; depth <= 0 is behind."""
    fwd, right, up = _basis(pose)
    v = _sub(point, pose.position)
    depth = _dot(v, fwd)
    if depth <= 1e-9:
        return math.nan, math.nan, depth
    hx, hy = _half_tans(pose, aspect)
    return _dot(v, right) / depth / hx, _dot(v, up) / depth / hy, depth


def box_corners(lo, hi):
    return [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def point_in_box(p, lo, hi, margin=0.0):
    """margin is a fraction of each axis' size added on every side."""
    for i in range(3):
        pad = (hi[i] - lo[i]) * margin
        if not lo[i] - pad <= p[i] <= hi[i] + pad:
            return False
    return True


def frame_stats(pose, corners, aspect):
    pts = [project(pose, c, aspect) for c in corners]
    in_front = all(d > 0 for _, _, d in pts)
    if not in_front:
        return {"allInFront": False, "inFrame": False, "coverage": math.inf}
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    in_frame = max(map(abs, xs + ys)) <= IN_FRAME_TOLERANCE
    coverage = max((max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2)
    return {"allInFront": True, "inFrame": in_frame, "coverage": coverage}


def camera_matrix(pose):
    """3x3 world rotation (rows) for a Blender camera, which looks down its local -Z with +Y up.
    Columns are (right, up, -forward) from _basis. The compiler MUST build camera rotation from
    this, never from a TRACK_TO constraint (see _basis)."""
    fwd, right, up = _basis(pose)
    return tuple((right[i], up[i], -fwd[i]) for i in range(3))


def focus_depth(pose, point):
    """Distance from the camera to `point` along the view axis (what Blender's DOF uses)."""
    fwd, _, _ = _basis(pose)
    return _dot(_sub(point, pose.position), fwd)
