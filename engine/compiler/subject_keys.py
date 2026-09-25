"""Pure: WHEN valora_motion is keyed and with WHAT channel values (the compiler's key_subject_motion keys
exactly this list; engine/motion_path is the pose, this is its sampling).

Blender interpolates the keys linearly (location, Euler, and the quaternion's components, normalised when
the matrix is built). One key per frame is not enough for three kinds of path:
- a velocity jump between frames (a bounce contact, a landing, a release; review chunk5 #3): the path's
  breaks() times are keyed exactly, so the rendered bounce reaches the ground at each contact instead of
  turning back above it;
- a curved stretch (a ballistic arc, a rolling pivot): a key interval is halved while the interpolated
  transform of four probe points strays more than KEY_TOL x longest from the path at its middle;
- a fast turn (roll on a slender cylinder; review chunk5 #4): quaternion keys are kept within KEY_MAX_TURN of
  their neighbour, measured on the path's unwrapped turn_angle() when it has one (two quaternions cannot tell
  a 30 degree turn from a 390 degree one), so the hemisphere correction always picks the path's way round.
A motion that restarts per shot (perShot, review amendment 79) gets the camera's cut keys: the outgoing pose
at f - 1 + SHUTTER / 2 held (CONSTANT) until the incoming pose at f - SHUTTER / 2, so no exposure sees the
jump and motion blur never smears across the cut."""
import math
from dataclasses import dataclass

from engine.compiler.tiers import SHUTTER
from engine.motion_path import (euler_matrix, per_shot, pose_breaks, pose_pivot, pose_quat, quat_matrix, rotate,
                                shot_at, subject_pose, turn_fn)

KEY_TOL = 1e-3                    # (eng) max stray of the keyed transform between keys, share of the longest side
KEY_MAX_TURN = math.radians(90)   # (eng) max rotation between neighbouring quaternion keys
KEY_MIN_STEP = 1.0 / 16.0         # (eng) frames: a key interval is never halved below this
SNAP = 1e-6                       # frames: a break this close to a key is that key


@dataclass(frozen=True)
class SubjectKey:
    frame: float
    shot: int
    pose: object
    hold: bool = False      # CONSTANT from this key to the next (the outgoing side of a perShot cut)


def channels(pose, profile, quat):
    """(location, rotation) valora_motion takes for a pose: the empty sits at the origin, so the pose's pivot
    goes into its location (loc = pivot + offset - R pivot); rotation = (w, x, y, z) or Euler (roll, pitch, yaw)."""
    pv = pose_pivot(pose, profile)
    r = rotate(pv, pose)
    loc = tuple(pv[i] + pose.offset[i] - r[i] for i in range(3))
    return loc, (pose_quat(pose) if quat else (pose.roll, pose.pitch, pose.yaw))


def matrix(loc, rot, quat):
    """3x4 [R | loc] of keyed channel values (a quaternion is normalised, as Blender does)."""
    R = quat_matrix(rot) if quat else euler_matrix(rot[2], rot[1], rot[0])
    return [R[i] + [loc[i]] for i in range(3)]


def probe_points(profile):
    """Four affinely independent points on the subject: its centre and one half-size step along each axis."""
    c, h = list(profile.center), 0.5 * profile.longest
    return [tuple(c)] + [tuple(c[j] + (h if j == i else 0.0) for j in range(3)) for i in range(3)]


def transform(m, p):
    return tuple(sum(m[i][j] * p[j] for j in range(3)) + m[i][3] for i in range(3))


def pose_mismatch(m, pose, profile):
    """Max distance (m) between where a keyed/evaluated transform m (3x4 or 4x4 rows) and the pose put the four
    probe points: the whole transform, not just where it takes the origin (review chunk5 #13: a turn about a
    pivot at the origin moves no origin)."""
    from engine.motion_path import apply
    return max(math.dist(transform(m, q), apply(q, pose, profile)) for q in probe_points(profile))


def _lerp(a, b, s):
    return tuple(x + (y - x) * s for x, y in zip(a, b))


def _flip(q, ref):
    return tuple(-c for c in q) if sum(a * b for a, b in zip(q, ref)) < 0 else q


def _turn(qa, qb):
    d = min(1.0, abs(sum(a * b for a, b in zip(qa, qb))))
    return 2.0 * math.acos(d)


def subject_keys(script, profile, catalog):
    """[SubjectKey] sorted by frame, and whether the rotation is keyed as a quaternion."""
    fps, n = script["format"]["fps"], int(round(script["format"]["durationS"] * script["format"]["fps"]))
    shots, cut = script.get("shots") or [], per_shot(script)
    pose = lambda f, i: subject_pose(script, profile, catalog, (f - 1) / fps, i)  # noqa: E731
    base, gaps, prev = [], [], None
    for f in range(0, n + 2):
        i = shot_at(shots, (f - 1) / fps) if shots else 0
        if cut and prev is not None and i != prev:          # the camera's cut subframes (compiler/timeline)
            a, b = f - 1 + SHUTTER / 2, f - SHUTTER / 2
            base += [(a, prev, True), (b, i, False)]
            gaps.append((a, b))
        base.append((float(f), i, False))
        prev = i
    for t in pose_breaks(script, profile, catalog):
        f = 1.0 + t * fps
        if not 0.0 < f < n + 1 or any(a - SNAP < f < b + SNAP for a, b in gaps):
            continue
        if all(abs(f - k[0]) > SNAP for k in base):
            base.append((f, shot_at(shots, t) if shots else 0, False))
    base.sort(key=lambda k: k[0])
    keys = [SubjectKey(f, i, pose(f, i), h) for f, i, h in base]
    quat = any(k.pose.quat is not None for k in keys)
    turn = turn_fn(script, profile, catalog) if quat else None
    pts, tol = probe_points(profile), KEY_TOL * profile.longest
    out = [keys[0]]
    for k in keys[1:]:
        a = out[-1]
        if not a.hold:
            out += _refine(a, k, pose, turn, fps, profile, quat, pts, tol)
        out.append(k)
    return out, quat


def _refine(a, b, pose, turn, fps, profile, quat, pts, tol):
    """Keys strictly between a and b (same shot as a) until every interval is straight and turns little."""
    if b.frame - a.frame <= KEY_MIN_STEP + 1e-12:
        return []
    fm = 0.5 * (a.frame + b.frame)
    split = False
    if quat:
        qa, qb = pose_quat(a.pose), pose_quat(b.pose)
        if turn is not None:
            ta, tb = turn((a.frame - 1) / fps, a.shot), turn((b.frame - 1) / fps, a.shot)
            split = abs(tb - ta) > KEY_MAX_TURN
        split = split or _turn(qa, qb) > KEY_MAX_TURN
    m = SubjectKey(fm, a.shot, pose(fm, a.shot))
    if not split:
        la, ra = channels(a.pose, profile, quat)
        lb, rb = channels(b.pose, profile, quat)
        if quat:
            rb = _flip(rb, ra)
        got = matrix(_lerp(la, lb, 0.5), _lerp(ra, rb, 0.5), quat)
        lm, rm = channels(m.pose, profile, quat)
        want = matrix(lm, rm, quat)
        split = max(math.dist(transform(got, p), transform(want, p)) for p in pts) > tol
    if not split:
        return []
    return _refine(a, m, pose, turn, fps, profile, quat, pts, tol) + [m] + _refine(m, b, pose, turn, fps, profile, quat, pts, tol)


def key_values(keys, profile, quat):
    """(frames, locations, rotations, holds) to key: quaternions kept in one hemisphere with their neighbour,
    which is the path's way round because neighbours turn <= KEY_MAX_TURN."""
    frames, locs, rots, holds = [], [], [], []
    for k in keys:
        loc, rot = channels(k.pose, profile, quat)
        if quat and rots:
            rot = _flip(rot, rots[-1])
        frames.append(k.frame)
        locs.append(loc)
        rots.append(rot)
        holds.append(k.hold)
    return frames, locs, rots, holds


def evaluate(values, frame, quat):
    """The keyed transform at a (fractional) frame, as Blender's F-curves give it: linear between keys (CONSTANT
    after a hold key), constant past both ends. A 3x4 matrix."""
    frames, locs, rots, holds = values
    if frame <= frames[0]:
        return matrix(locs[0], rots[0], quat)
    if frame >= frames[-1]:
        return matrix(locs[-1], rots[-1], quat)
    j = max(k for k in range(len(frames)) if frames[k] <= frame)
    if holds[j] or frames[j] == frame:
        return matrix(locs[j], rots[j], quat)
    s = (frame - frames[j]) / (frames[j + 1] - frames[j])
    return matrix(_lerp(locs[j], locs[j + 1], s), _lerp(rots[j], rots[j + 1], s), quat)
