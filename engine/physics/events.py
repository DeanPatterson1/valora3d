"""Stops and landings read from the subject's motion track (one position per frame, frame 1 first: the
subject's reference point, its placed bounding-box centre, moved by valora_motion's FULL transform;
reference_track). The empty's bare location is not a track: a roll, topple or toss turns about its own pivot,
so the location carries pivot - R pivot and would read a rolling can as stopping and landing (review
chunk5 #2). Realism blocks attach settles to these events; the motion block never has to
announce them (phase-5 drive/drop/roll plug in unchanged)."""
import math

MOVE_FRAC = 0.02        # moving = faster than 2% of the subject's length per second (eng)
MIN_MOVE_S = 0.2        # a stop needs at least 0.2 s of movement before it (eng)
DECEL_WINDOW_S = 0.25   # deceleration measured over the last 0.25 s before the stop (eng)
REST_Z_FRAC = 0.01      # "on the ground" = within 1% of the longest side of z = 0


def reference_track(transforms, ref):
    """Per frame, where the reference point `ref` (placed space) has moved: loc + R ref - ref.
    transforms: (loc, R) per frame, R a 3x3 rotation (rows). A yaw about a vertical line through ref gives
    the bare offset, so a plain slide, drive or drop reads exactly as its path's offset."""
    return [tuple(loc[i] + sum(R[i][j] * ref[j] for j in range(3)) - ref[i] for i in range(3))
            for loc, R in transforms]


def takes(shots, n):
    """[(i0, i1)] index ranges of one continuous take each: runs of equal shots[i] (motion_path.frame_shots;
    a perShot drive replays at every cut). shots None = one take [(0, n)]."""
    if shots is None:
        return [(0, n)]
    out, i0 = [], 0
    for i in range(1, n + 1):
        if i == n or shots[i] != shots[i - 1]:
            out.append((i0, i))
            i0 = i
    return out


def take_of(shots, n, frame):
    """(first, last) 1-based frames of the take that holds 1-based `frame`."""
    for i0, i1 in takes(shots, n):
        if i0 < frame <= i1:
            return i0 + 1, i1
    return 1, n


def _per_take(fn, pos, shots, *args):
    out = []
    for i0, i1 in takes(shots, len(pos)):
        out += [{**e, "frame": e["frame"] + i0} for e in fn(pos[i0:i1], *args)]
    return out


def speeds(pos, fps):
    """Ground-plane speed per frame (m/s). Vertical motion is a fall or a lift, never a stop."""
    return [0.0] + [math.dist(pos[i][:2], pos[i - 1][:2]) * fps for i in range(1, len(pos))]


def stops(pos, fps, longest, shots=None):
    """Stops (frame = the first 1-based frame at rest), within each take (shots: frame_shots; a cut's
    jump is never a stop)."""
    if shots is not None:
        return _per_take(stops, pos, shots, fps, longest)
    thr, v, out, run = MOVE_FRAC * longest, speeds(pos, fps), [], 0
    k = max(1, round(DECEL_WINDOW_S * fps))
    for i in range(1, len(v)):
        if v[i] > thr:
            run += 1
            continue
        if run >= MIN_MOVE_S * fps:
            j = max(0, i - k)
            decel = (max(v[j:i]) - v[i]) / ((i - j) / fps)
            dx, dy = pos[i - 1][0] - pos[i - 2][0], pos[i - 1][1] - pos[i - 2][1]
            n = math.hypot(dx, dy) or 1.0
            # frame (1-based) i = index i - 1: the first frame at the resting position
            out.append({"frame": i, "decelMs2": round(decel, 4), "dir": [round(dx / n, 6), round(dy / n, 6)]})
        run = 0
    return out


def landings(pos, fps, longest, shots=None):
    """The first frame at rest after falling. The impact speed is the fastest descent over the 3 frames
    before it (the last step before rest is clamped at the ground and reads slow). Within each take."""
    if shots is not None:
        return _per_take(landings, pos, shots, fps, longest)
    thr, out = MOVE_FRAC * longest, []
    vz = [0.0] + [(pos[i][2] - pos[i - 1][2]) * fps for i in range(1, len(pos))]
    for i in range(2, len(pos)):
        if vz[i - 1] < -thr and abs(vz[i]) <= thr and pos[i][2] <= REST_Z_FRAC * longest:
            out.append({"frame": i, "impactMs": round(-min(vz[max(1, i - 3):i]), 4)})
    return out
