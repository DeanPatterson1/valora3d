"""The ONE place a script's subject motion becomes subject poses (phase 5 Task 56). The checker frames the
moving subject with it and the compiler keyframes valora_motion from it, so they can never disagree.

A pose is an offset (placed metres) + yaw/pitch/roll (radians) applied about the subject's ground-centre
pivot (profile.center[0], profile.center[1], 0): p' = Rz(yaw) Ry(pitch) Rx(roll) (p - pivot) + pivot + offset
(Blender Euler 'XYZ' order). A motion that turns about another point sets `pivot` (placed space: a roll's
axis line at height r, a topple's support edge; review amendment 77), and one that turns about an arbitrary
axis sets `quat` (w, x, y, z), which replaces yaw/pitch/roll (a PCA roll axis is never a local Euler axis). static/play_clip (and any motion without a path.py) = IDENTITY. A path.py
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
    pivot: tuple = None     # placed-space point the rotation turns about; None = (cx, cy, 0)
    quat: tuple = None      # (w, x, y, z) rotation; replaces yaw/pitch/roll when set


IDENTITY = SubjectPose()


def _motion(script):
    return (script.get("subject") or {}).get("motion") or {}


def subject_pose(script, profile, catalog, t, shot=None):
    """The pose at script time t. A motion whose params set perShot (drive, review amendment 79) restarts at
    every shot: its path runs on shot-relative time t - shot.startS (and the shot's length as its duration).
    shot = the shot (index or shot dict) to take that time from (the compiler's cut keys: the subframe before a
    cut belongs to the outgoing shot, the one after to the incoming shot; a tracking camera's Track pins its own
    shot); None = the shot playing at t. Without perShot the shot is ignored and the path runs on clip time."""
    motion = _motion(script)
    bid = motion.get("id", "static")
    if not catalog.has_motion_path(bid):          # play_clip and fixture motions have no path.py
        return IDENTITY
    sample = catalog.load_motion_path(bid)
    params = motion.get("params") or {}
    sh = _per_shot(script, t, shot)
    if sh is not None:
        return sample(params, profile, float(t) - float(sh["startS"]), float(sh["endS"]) - float(sh["startS"]))
    return sample(params, profile, float(t), _duration(script))


def per_shot(script):
    """True when the motion restarts at every shot (perShot, review amendment 79) and there are shots."""
    return bool((_motion(script).get("params") or {}).get("perShot")) and bool(script.get("shots"))


def frame_shots(script, frames):
    """Per compiler frame f (showing script time (f - 1) / fps), the shot whose take it shows when the motion
    restarts per shot (perShot); None otherwise (the clip is one take). Realism reading the subject track
    never differentiates across a change of shot: the track jumps there (a replay), the subject does not."""
    if not per_shot(script):
        return None
    fps = float(script["format"]["fps"])
    return [shot_at(script["shots"], (f - 1) / fps) for f in frames]


def shot_at(shots, t):
    """Index of the shot playing at script time t (the last one started by t; the first before any)."""
    i = 0
    for k, sh in enumerate(shots):
        if sh["startS"] <= t + 1e-9:
            i = k
    return i


def _per_shot(script, t, shot):
    if not per_shot(script):
        return None
    shots = script["shots"]
    if isinstance(shot, dict):
        return shot
    return shots[shot_at(shots, float(t)) if shot is None else shot]


def _duration(script):
    return float((script.get("format") or {}).get("durationS", 0.0))


def pose_fn(script, profile, catalog):
    """pose_at(t, shot=None); pose_at.per_shot says whether the shot matters (perShot)."""
    fn = lambda t, shot=None: subject_pose(script, profile, catalog, t, shot)  # noqa: E731
    fn.per_shot = per_shot(script)
    return fn


def pose_breaks(script, profile, catalog):
    """Script times where the path's velocity jumps (a bounce contact, a landing, a release), from path.py's
    optional breaks(params, profile, duration). The compiler keys them exactly (review chunk5 #3): a key a
    fraction of a frame off a contact interpolates a bounce that turns back above the ground."""
    motion = _motion(script)
    bid = motion.get("id", "static")
    if not catalog.has_motion_path(bid):
        return []
    fn = getattr(catalog.motion_module(bid), "breaks", None)
    if fn is None:
        return []
    params = motion.get("params") or {}
    if per_shot(script):
        out = []
        for sh in script["shots"]:
            a, b = float(sh["startS"]), float(sh["endS"])
            out += [a + x for x in fn(params, profile, b - a) if 0.0 <= x < b - a]
        return sorted(out)
    return sorted(float(x) for x in fn(params, profile, _duration(script)))


def turn_fn(script, profile, catalog):
    """The path's unwrapped rotation angle (radians about its own axis) as a function of (t, shot), from
    path.py's optional turn_angle(params, profile, t, duration); None when it has none. Two quaternion keys
    cannot tell a 30 degree turn from a 390 degree one; this can (review chunk5 #4)."""
    motion = _motion(script)
    bid = motion.get("id", "static")
    if not catalog.has_motion_path(bid):
        return None
    fn = getattr(catalog.motion_module(bid), "turn_angle", None)
    if fn is None:
        return None
    params = motion.get("params") or {}

    def at(t, shot=None):
        sh = _per_shot(script, t, shot)
        if sh is not None:
            return fn(params, profile, float(t) - float(sh["startS"]), float(sh["endS"]) - float(sh["startS"]))
        return fn(params, profile, float(t), _duration(script))
    return at


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


def pose_pivot(pose, profile):
    """The point this pose turns about: its own pivot, else the ground-centre pivot."""
    return tuple(pose.pivot) if pose.pivot is not None else pivot(profile)


def quat_matrix(q):
    """3x3 rotation matrix of a quaternion (w, x, y, z); normalised first."""
    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z) or 1.0
    w, x, y, z = w / n, x / n, y / n, z / n
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]]


def euler_matrix(yaw, pitch, roll):
    """Rz(yaw) Ry(pitch) Rx(roll): Blender Euler 'XYZ' = (roll, pitch, yaw)."""
    cr, sr, cp, sp, cy, sy = (math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch),
                              math.cos(yaw), math.sin(yaw))
    return [[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr]]


def rotation_matrix(pose):
    return quat_matrix(pose.quat) if pose.quat is not None else euler_matrix(pose.yaw, pose.pitch, pose.roll)


def pose_quat(pose):
    """The pose's rotation as a unit quaternion (w, x, y, z)."""
    if pose.quat is not None:
        w, x, y, z = pose.quat
        n = math.sqrt(w * w + x * x + y * y + z * z) or 1.0
        return (w / n, x / n, y / n, z / n)
    cr, sr = math.cos(pose.roll / 2), math.sin(pose.roll / 2)
    cp, sp = math.cos(pose.pitch / 2), math.sin(pose.pitch / 2)
    cy, sy = math.cos(pose.yaw / 2), math.sin(pose.yaw / 2)
    return (cy * cp * cr + sy * sp * sr, cy * cp * sr - sy * sp * cr,
            cy * sp * cr + sy * cp * sr, sy * cp * cr - cy * sp * sr)


def rotate(v, pose):
    """The pose's rotation applied to a direction (no pivot, no offset)."""
    if pose.quat is not None:
        m = quat_matrix(pose.quat)
        return tuple(sum(m[i][j] * v[j] for j in range(3)) for i in range(3))
    x, y, z = v
    cr, sr = math.cos(pose.roll), math.sin(pose.roll)          # about the subject's local X
    y, z = cr * y - sr * z, sr * y + cr * z
    cp, sp = math.cos(pose.pitch), math.sin(pose.pitch)        # about local Y
    x, z = cp * x + sp * z, -sp * x + cp * z
    cy, sy = math.cos(pose.yaw), math.sin(pose.yaw)            # about world Z
    x, y = cy * x - sy * y, sy * x + cy * y
    return (x, y, z)


def _rot(p, pose, pv):
    if pose.pivot is not None:
        pv = tuple(pose.pivot)
    x, y, z = rotate((p[0] - pv[0], p[1] - pv[1], p[2] - pv[2]), pose)
    return (x + pv[0] + pose.offset[0], y + pv[1] + pose.offset[1], z + pv[2] + pose.offset[2])


def apply(p, pose, profile):
    """A placed point moved by the pose (world coordinates)."""
    return _rot(p, pose, pivot(profile))


def unapply(p, pose, profile):
    """Inverse of apply: a world point back into placed (rest) coordinates."""
    pv = pose_pivot(pose, profile)
    d = [p[i] - pv[i] - pose.offset[i] for i in range(3)]
    if pose.quat is not None:
        m = quat_matrix(pose.quat)                           # the transpose undoes a rotation
        x, y, z = (sum(m[j][i] * d[j] for j in range(3)) for i in range(3))
        return (x + pv[0], y + pv[1], z + pv[2])
    x, y, z = d
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
