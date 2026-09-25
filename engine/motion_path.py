"""The ONE place a script's subject motion becomes subject poses (phase 5 Task 56). The checker frames the
moving subject with it and the compiler keyframes valora_motion from it, so they can never disagree.

A pose is an offset (placed metres) + yaw/pitch/roll (radians) applied about the subject's ground-centre
pivot (profile.center[0], profile.center[1], 0): p' = Rz(yaw) Ry(pitch) Rx(roll) (p - pivot) + pivot + offset
(Blender Euler 'XYZ' order). static/play_clip (and any motion without a path.py) = IDENTITY. A path.py
that can be the identity says so with still(params) (static's always is); without it the motion counts as
moving.

Shot time: with fps, u in [0, 1] maps to t = startS + u * (endS - startS - 1/fps), exactly the timeline's
frame-aligned span (compiler/timeline.shot_u), so checker samples and compiler frames see the same pose."""
import math
from dataclasses import dataclass, replace

SWEEP_SAMPLES = 24  # (eng) poses sampled per clip to build swept bounds / measure travel


@dataclass(frozen=True)
class SubjectPose:
    offset: tuple = (0.0, 0.0, 0.0)
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0


IDENTITY = SubjectPose()


def _motion(script):
    return (script.get("subject") or {}).get("motion") or {}


def subject_pose(script, profile, catalog, t):
    motion = _motion(script)
    bid = motion.get("id", "static")
    if not catalog.has_motion_path(bid):          # play_clip and fixture motions have no path.py
        return IDENTITY
    sample = catalog.load_motion_path(bid)
    return sample(motion.get("params") or {}, profile, float(t), _duration(script))


def _duration(script):
    return float((script.get("format") or {}).get("durationS", 0.0))


def pose_fn(script, profile, catalog):
    return lambda t: subject_pose(script, profile, catalog, t)


def _times(t0, t1, n=SWEEP_SAMPLES):
    return [t0 + (t1 - t0) * k / (n - 1) for k in range(n)]


def is_moving(script, profile, catalog):
    """False only for a motion without a path.py, or whose path.py declares still(params) True (the
    explicit identity contract, catalog.motion_still): such a script checks and compiles exactly as before.
    Sampling never decides it (review chunk1 #2: a brief excursion between samples would switch off both
    the motion check and every compiler key)."""
    motion = _motion(script)
    return not catalog.motion_still(motion.get("id", "static"), motion.get("params") or {})


def pivot(profile):
    return (profile.center[0], profile.center[1], 0.0)


def rotate(v, pose):
    """The pose's rotation applied to a direction (no pivot, no offset)."""
    x, y, z = v
    cr, sr = math.cos(pose.roll), math.sin(pose.roll)          # about the subject's local X
    y, z = cr * y - sr * z, sr * y + cr * z
    cp, sp = math.cos(pose.pitch), math.sin(pose.pitch)        # about local Y
    x, z = cp * x + sp * z, -sp * x + cp * z
    cy, sy = math.cos(pose.yaw), math.sin(pose.yaw)            # about world Z
    x, y = cy * x - sy * y, sy * x + cy * y
    return (x, y, z)


def _rot(p, pose, pv):
    x, y, z = rotate((p[0] - pv[0], p[1] - pv[1], p[2] - pv[2]), pose)
    return (x + pv[0] + pose.offset[0], y + pv[1] + pose.offset[1], z + pv[2] + pose.offset[2])


def apply(p, pose, profile):
    """A placed point moved by the pose (world coordinates)."""
    return _rot(p, pose, pivot(profile))


def unapply(p, pose, profile):
    """Inverse of apply: a world point back into placed (rest) coordinates."""
    pv = pivot(profile)
    x, y, z = (p[i] - pv[i] - pose.offset[i] for i in range(3))
    cy, sy = math.cos(-pose.yaw), math.sin(-pose.yaw)
    x, y = cy * x - sy * y, sy * x + cy * y
    cp, sp = math.cos(-pose.pitch), math.sin(-pose.pitch)
    x, z = cp * x + sp * z, -sp * x + cp * z
    cr, sr = math.cos(-pose.roll), math.sin(-pose.roll)
    y, z = cr * y - sr * z, sr * y + cr * z
    return (x + pv[0], y + pv[1], z + pv[2])


def _corners(lo, hi):
    return [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def posed_bounds(profile, pose):
    if pose == IDENTITY:
        return list(profile.boundsMin), list(profile.boundsMax)
    pv = pivot(profile)
    pts = [_rot(c, pose, pv) for c in _corners(profile.boundsMin, profile.boundsMax)]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def posed_profile(profile, pose):
    """A shallow copy whose bounds (and so its centre, a property) are the posed AABB. Sizes stay the
    measured ones (the subject's own size never changes; only where it is). Detail points move with it."""
    if pose == IDENTITY:
        return profile
    lo, hi = posed_bounds(profile, pose)
    pv = pivot(profile)
    details = []
    for d in profile.detailPoints or []:
        e = dict(d)
        if "point" in d:
            e["point"] = list(_rot(d["point"], pose, pv))
        if d.get("normal"):
            e["normal"] = list(rotate(d["normal"], pose))
        details.append(e)
    return replace(profile, boundsMin=lo, boundsMax=hi, detailPoints=details)


def posed_markers(markers, profile, pose):
    """Markers whose placed anchors (point, normal) move with the subject."""
    if pose == IDENTITY or not markers:
        return markers
    pv, out = pivot(profile), []
    for m in markers:
        a = dict(m.get("anchor") or {})
        if "point" in a:
            a["point"] = list(_rot(a["point"], pose, pv))
        if a.get("normal"):
            a["normal"] = list(rotate(a["normal"], pose))
        out.append({**m, "anchor": a})
    return out


def posed_target(target, profile, pose):
    """A resolved rest-pose Target (engine.targets) moved with the subject: point moved, normal turned.
    Resolving on the rest profile first keeps the surface fallback on the measured samples."""
    if target is None or pose == IDENTITY:
        return target
    return replace(target, point=tuple(_rot(target.point, pose, pivot(profile))),
                   normal=tuple(rotate(target.normal, pose)))


def shot_t(shot, u, fps=None):
    a, b = shot["startS"], shot["endS"]
    span = (b - a) - (1.0 / fps if fps else 0.0)
    return a + u * max(span, 0.0)


def camera_t(shot, follows="anchor", u=0.5, fps=None):
    """anchor: the shot's midpoint (a pass-by stays centred); subject: the live time at u."""
    return (shot["startS"] + shot["endS"]) / 2 if follows == "anchor" else shot_t(shot, u, fps)


def camera_profile(shot, profile, pose_at, follows="anchor", u=0.5, fps=None):
    """The profile a camera programme is solved against: the mid-shot pose (anchor) or the live pose."""
    return posed_profile(profile, pose_at(camera_t(shot, follows, u, fps)))


def swept_bounds(profile, pose_at, t0, t1, n=SWEEP_SAMPLES):
    los, his = zip(*(posed_bounds(profile, pose_at(t)) for t in _times(t0, t1, n)))
    return [min(v[i] for v in los) for i in range(3)], [max(v[i] for v in his) for i in range(3)]


def horizontal_travel(pose_at, t0, t1, n=SWEEP_SAMPLES):
    """Max horizontal pivot travel over the clip, hypot(offset.x, offset.y): turning in place is not travel."""
    return max(math.hypot(p.offset[0], p.offset[1]) for p in (pose_at(t) for t in _times(t0, t1, n)))
