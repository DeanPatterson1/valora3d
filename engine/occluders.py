"""Declared world occluders and the lower-frame sight-line guard (TG-47 follow-up, 2026-09-25).

A low hero camera (TG-47: 0.3-0.7 m) that stands on the far side of a kerb, pavement or curb sees that raised
slab fill the bottom of the frame (night_street look 4ced996a: a 15 cm pavement slab over ~40% of a 9:16
frame). Each outdoor world declares its raised, always-built geometry in block.json as `occluders`: boxes in the
subject frame (u across, v along the subject's longer horizontal axis, metres from the subject's centre; the
frame street_layout and courtyard_layout use), so the checker and the director can test a camera without
building the set:

    {"id": "kerb_pavement", "u": [lo, hi], "v": [lo, hi] | null, "z": [z0, z1], "mirror": true}

A u/v bound is a number or {"m": m, "k": k, "plus": p} = max(m, k x longest) + p (the layouts' own sizing
rule); v null runs the whole world; mirror adds the box reflected across the along axis (both sides).

The guard casts a grid of rays through the lower part of the frame (from the bottom edge up to the subject's
centre) and counts the rays that meet an occluder nearer than the subject before the ground or the subject.
More than LOS_TOL of them = the camera is on the wrong side of the world's raised geometry."""
import math

from engine.geometry import _basis, _half_tans, project

LOS_TOL = 0.02          # (eng) share of lower-frame rays allowed to meet raised world geometry first
GRID_X, GRID_Y = 16, 8  # (eng) rays across x down the lower frame (128: two hits stay under LOS_TOL)
RAISE_TOL_M = 0.02      # (eng) an occluder no taller than this is flush with the ground (never counted)
FAR_M = 1e3             # a v: null box runs this far each way
STAND_CLEAR_M = 0.3     # (eng) a camera over an occluder's footprint + this stands on the slab, not at ground
                        # level on the subject's side (street_layout.SLAB_CLEAR_M)


def _frame(profile):
    """((cx, cy), across-axis index): along follows the longer horizontal half (the layouts' _frame)."""
    cx, cy = profile.center[0], profile.center[1]
    return (cx, cy), (0 if profile.half[1] >= profile.half[0] else 1)


def _val(spec, longest):
    if isinstance(spec, (int, float)):
        return float(spec)
    return max(float(spec.get("m", 0.0)), float(spec.get("k", 0.0)) * longest) + float(spec.get("plus", 0.0))


def valid(items):
    """True when `items` is a well-formed occluders list (the catalog validates block.json with it)."""
    def bound(b):
        return isinstance(b, (int, float)) or (isinstance(b, dict) and set(b) <= {"m", "k", "plus"}
                                                 and all(isinstance(v, (int, float)) for v in b.values()))

    def pair(p, nullable=False):
        return (nullable and p is None) or (isinstance(p, list) and len(p) == 2 and all(bound(b) for b in p))
    return isinstance(items, list) and all(
        isinstance(o, dict) and set(o) <= {"id", "u", "v", "z", "mirror"} and isinstance(o.get("id"), str)
        and pair(o.get("u")) and pair(o.get("v"), True) and isinstance(o.get("z"), list) and len(o["z"]) == 2
        and all(isinstance(z, (int, float)) for z in o["z"]) and isinstance(o.get("mirror", False), bool)
        for o in items)


def declared(world, profile):
    """Placed (lo, hi) boxes of the world manifest's declared occluders for this subject ([] when none)."""
    (cx, cy), ia = _frame(profile)
    L = profile.longest
    out = []
    for o in (world or {}).get("occluders") or []:
        u0, u1 = sorted(_val(b, L) for b in o["u"])
        v0, v1 = (-FAR_M, FAR_M) if o.get("v") is None else sorted(_val(b, L) for b in o["v"])
        z0, z1 = float(o["z"][0]), float(o["z"][1])
        for s in ((1, -1) if o.get("mirror") else (1,)):
            a, b = sorted((s * u0, s * u1))
            lo_uv, hi_uv = (a, v0), (b, v1)
            if ia == 0:
                out.append(((cx + lo_uv[0], cy + lo_uv[1], z0), (cx + hi_uv[0], cy + hi_uv[1], z1)))
            else:
                out.append(((cx + lo_uv[1], cy + lo_uv[0], z0), (cx + hi_uv[1], cy + hi_uv[0], z1)))
    return out


def across(position, subject_lo, subject_hi, boxes):
    """Cheap plan test: True when a camera at `position` stands within STAND_CLEAR_M of an occluder's footprint
    or its plan line to the subject's centre crosses one (it is on the far side). Such a camera is (nearly)
    always blocked, so searches reject it before casting any ray; blocked_share stays the judge."""
    c = ((subject_lo[0] + subject_hi[0]) / 2, (subject_lo[1] + subject_hi[1]) / 2)
    o = position
    for lo, hi in boxes:
        if hi[2] - max(0.0, lo[2]) <= RAISE_TOL_M:
            continue
        if all(lo[i] - STAND_CLEAR_M <= o[i] <= hi[i] + STAND_CLEAR_M for i in range(2)):
            return True
        t0, t1 = 0.0, 1.0
        for i in range(2):
            d = c[i] - o[i]
            if abs(d) < 1e-12:
                if not lo[i] <= o[i] <= hi[i]:
                    break
                continue
            a, b = (lo[i] - o[i]) / d, (hi[i] - o[i]) / d
            t0, t1 = max(t0, min(a, b)), min(t1, max(a, b))
        else:
            if t0 <= t1:
                return True
    return False


def _enter(o, d, lo, hi):
    """Entry distance of the ray o + t d (t >= 0) into the box [lo, hi], or None (0 when o is inside)."""
    t0, t1 = 0.0, math.inf
    for i in range(3):
        if abs(d[i]) < 1e-12:
            if not lo[i] <= o[i] <= hi[i]:
                return None
            continue
        a, b = (lo[i] - o[i]) / d[i], (hi[i] - o[i]) / d[i]
        t0, t1 = max(t0, min(a, b)), min(t1, max(a, b))
        if t0 > t1:
            return None
    return t0


def blocked_share(pose, subject_lo, subject_hi, boxes, aspect, stop=False):
    """Share of the lower-frame rays (bottom edge up to the subject's centre) that meet an occluder before the
    ground (z = 0) or the subject, and nearer than the subject's closest footprint point. A camera standing over
    an occluder's footprint (within STAND_CLEAR_M) is wholly blocked: it is on the slab, not beside the subject.
    stop: return as soon as the share is past LOS_TOL (the value is then only a lower bound)."""
    boxes = [b for b in boxes if b[1][2] - max(0.0, b[0][2]) > RAISE_TOL_M]
    if not boxes:
        return 0.0
    o = pose.position
    if any(all(lo[i] - STAND_CLEAR_M <= o[i] <= hi[i] + STAND_CLEAR_M for i in range(2)) for lo, hi in boxes):
        return 1.0
    fwd, right, up = _basis(pose)
    hx, hy = _half_tans(pose, aspect)
    c = tuple((a + b) / 2 for a, b in zip(subject_lo, subject_hi))
    yc = project(pose, c, aspect)[1]
    top = min(1.0, yc) if yc == yc else 0.0
    if top <= -1.0:
        return 0.0
    nx = min(max(o[0], subject_lo[0]), subject_hi[0]) - o[0]
    ny = min(max(o[1], subject_lo[1]), subject_hi[1]) - o[1]
    near = math.hypot(nx, ny)                                    # horizontal reach to the subject
    hit, n, cap = 0, GRID_X * GRID_Y, int(LOS_TOL * GRID_X * GRID_Y)
    for j in range(GRID_Y):
        y = -1.0 + (top + 1.0) * (j + 0.5) / GRID_Y
        for i in range(GRID_X):
            x = -1.0 + 2.0 * (i + 0.5) / GRID_X
            d = tuple(f + x * hx * r + y * hy * u for f, r, u in zip(fwd, right, up))
            m = math.sqrt(sum(v * v for v in d))
            d = tuple(v / m for v in d)
            end = -o[2] / d[2] if d[2] < -1e-12 else math.inf
            ts = _enter(o, d, subject_lo, subject_hi)
            if ts is not None:
                end = min(end, ts)
            h = math.hypot(d[0], d[1])
            for lo, hi in boxes:
                t = _enter(o, d, lo, hi)
                if t is not None and t < end and t * h < near:
                    hit += 1
                    break
            if stop and hit > cap:                                        # already over LOS_TOL: the answer is "blocked"
                return hit / n
    return hit / n
