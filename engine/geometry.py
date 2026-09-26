"""Camera maths shared by the checker (phase 1) and the compiler (phase 2). Stdlib only."""
import math
from dataclasses import dataclass

SENSOR_MM = 36.0
IN_FRAME_TOLERANCE = 1.02  # ndc beyond ±1.02 counts as out of frame
# Camera f-numbers are authored for a car-sized set (the render-studio car films they come from).
# Framing is in subject radii, so it is scale-free; depth of field is not (DoF / frame ~ N * s / f).
REF_RADIUS_M = 2.5


@dataclass(frozen=True)
class Pose:
    position: tuple
    target: tuple
    lens_mm: float
    roll: float = 0.0   # radians about the view axis; + turns the picture's up toward its left (dutch_hero, Task 81)


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
    if pose.roll:   # a camera roll turns right/up about the view axis: the picture turns by -roll (Task 81)
        c, s = math.cos(pose.roll), math.sin(pose.roll)
        right, up = (tuple(c * r + s * u for r, u in zip(right, up)),
                     tuple(-s * r + c * u for r, u in zip(right, up)))
    return fwd, right, up


def sensor_fit(width_px, height_px):
    """The locked sensor convention (critique mat-v2 #5): SENSOR_MM spans the frame's LONG side, set explicitly
    (Blender 'AUTO' does the same today but is a default, not a decision): HORIZONTAL for landscape and square,
    VERTICAL for portrait."""
    return "HORIZONTAL" if width_px >= height_px else "VERTICAL"


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


SILHOUETTE_DIRS = 256    # (eng) directions whose extreme surface sample is kept as a silhouette point
SAMPLE_CELLS = 40        # ingest's SURFACE_CELLS: one kept surface sample per cube of side longest / 40
_SIL_CACHE = {}          # id(samples) -> (samples, points): the live reference keeps the id from being reused


def silhouette_points(samples, n=SILHOUETTE_DIRS):
    """The surface samples that can bound the subject's projected outline: the extreme sample along each of n
    evenly spread directions (Fibonacci sphere). They are convex-hull vertices of the sampled surface, so their
    projected extent is the mesh's own silhouette extent (to the sampling), never the bounds box's: a car's box
    corners sit off the body (rounded nose and tail, the wing's tips) and overstate the width it fills (round 6
    heroes: the silhouette 0.68-0.75 of the frame width when the box just fit). The samples are one per voxel
    (side longest / SAMPLE_CELLS), so the true surface can lie up to a cell past a kept point: each point is
    pushed outward, along the directions that chose it, by half a cell. [] when there are no samples."""
    if not samples:
        return []
    hit = _SIL_CACHE.get(id(samples))
    if hit is not None and hit[0] is samples:
        return hit[1]
    pts = [tuple(float(c) for c in p) for p in samples]
    golden = math.pi * (3.0 - math.sqrt(5.0))
    pad = 0.5 * max(max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3)) / SAMPLE_CELLS
    keep = {}
    for k in range(n):
        z = 1.0 - 2.0 * (k + 0.5) / n
        r = math.sqrt(max(0.0, 1.0 - z * z))
        d = (r * math.cos(golden * k), r * math.sin(golden * k), z)
        best = max(range(len(pts)), key=lambda i: _dot(pts[i], d))
        acc = keep.setdefault(best, [0.0, 0.0, 0.0])
        for i in range(3):
            acc[i] += d[i]
    out = []
    for i in sorted(keep):
        a = keep[i]
        m = math.sqrt(_dot(a, a)) or 1.0
        out.append(tuple(pts[i][j] + pad * a[j] / m for j in range(3)))
    if len(_SIL_CACHE) >= 64:
        _SIL_CACHE.clear()
    _SIL_CACHE[id(samples)] = (samples, out)
    return out


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


def ray_box_exit(origin, direction, lo, hi):
    """Distance along a unit ray from a point inside the box [lo, hi] to where it leaves it.
    None when the origin is outside the box."""
    if not all(l <= o <= h for o, l, h in zip(origin, lo, hi)):
        return None
    t = math.inf
    for o, d, l, h in zip(origin, direction, lo, hi):
        if d > 0:
            t = min(t, (h - o) / d)
        elif d < 0:
            t = min(t, (l - o) / d)
    return t


def set_fstop(fstop, radius):
    """The f-number Blender renders so a set of this radius keeps the in-focus depth, as a share of
    the frame, the director asked for at car scale. Larger sets keep the f-number as asked."""
    return fstop * max(1.0, REF_RADIUS_M / radius)


def mist_far(camera_positions, corners, margin=1.01):
    """Mist depth that covers the whole set: the farthest set-geometry corner seen from any camera
    key, plus 1%. A mist range sized to the subject clamps most of the background to 1.0, and the
    harness (TIERS T2-07) can then not tell near background from far."""
    return margin * max(math.dist(c, k) for c in camera_positions for k in corners)
