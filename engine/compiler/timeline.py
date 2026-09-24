"""Pure frame timeline: which shot and camera pose every Blender frame gets, and the cut keys.

Blender frame f (1-based) shows time t = (f - 1) / fps. With a centred shutter of SHUTTER frames,
frame f-1 exposes until f-1+SHUTTER/2 and frame f from f-SHUTTER/2. At a cut the camera jumps
between keys at those two subframes, so no exposure ever sees the jump. This ports render-studio
film_camera.animate (ModVision tools/render-studio/film_camera.py:367).

Keys outside a shot's own frames (frame 0, frame n+1 and the cut subframes) are not clamped to the
shot's end pose: that would freeze the camera for half of the first and last exposures and halve
their motion blur whenever a path still moves at u = 0 or 1 (in_quad does). Instead the pose is
extrapolated linearly from the shot's two outermost frames, i.e. the path keeps its end velocity."""
from dataclasses import dataclass

from engine.compiler.tiers import SHUTTER
from engine.geometry import Pose, focus_depth, set_fstop
from engine.targets import resolve_target


@dataclass(frozen=True)
class CamKey:
    frame: float
    shot: int
    pose: Pose
    fstop: float
    focusM: float
    target: tuple = None  # a detail shot's target point (the compiler checks it is in view)


def frame_count(fmt):
    return int(round(fmt["durationS"] * fmt["fps"]))


def shot_index(shots, t):
    i = 0
    for k, sh in enumerate(shots):
        if sh["startS"] <= t + 1e-9:
            i = k
    return i


def shot_u(shot, t, fps):
    """Progress through a shot; the shot's last frame reaches exactly u = 1 (what the checker sampled)."""
    span = shot["endS"] - shot["startS"] - 1.0 / fps
    if span <= 0:
        return 0.0
    return min(max((t - shot["startS"]) / span, 0.0), 1.0)


def _pose_at(frame, i, s, profile, catalog, tgt):
    fps, sh = s["format"]["fps"], s["shots"][i]
    ref = sh["camera"]
    return catalog.load_camera_path(ref["id"])(ref["params"], profile, shot_u(sh, (frame - 1) / fps, fps), tgt)


def _extrapolate(a, b, t):
    """Pose a + (b - a) * t, component-wise (t > 1 continues past b)."""
    lerp = lambda x, y: tuple(p + (q - p) * t for p, q in zip(x, y))  # noqa: E731
    return Pose(position=lerp(a.position, b.position), target=lerp(a.target, b.target),
                lens_mm=a.lens_mm + (b.lens_mm - a.lens_mm) * t)


def _key(frame, i, s, profile, catalog):
    fps, sh = s["format"]["fps"], s["shots"][i]
    ref = sh["camera"]
    detail = catalog.get("camera", ref["id"])["framing"] == "detail"
    tgt = resolve_target(sh, profile, s.get("markers", [])) if detail else None
    first = int(round(sh["startS"] * fps)) + 1  # the shot's own frames (the checker frame-aligns shots)
    last = int(round(sh["endS"] * fps))
    if frame < first and last > first:
        a, b = (_pose_at(f, i, s, profile, catalog, tgt) for f in (first + 1, first))
        pose = _extrapolate(a, b, 1.0 + (first - frame))
    elif frame > last and last > first:
        a, b = (_pose_at(f, i, s, profile, catalog, tgt) for f in (last - 1, last))
        pose = _extrapolate(a, b, 1.0 + (frame - last))
    else:
        pose = _pose_at(frame, i, s, profile, catalog, tgt)
    focus = tgt.point if tgt else profile.center  # spec §4.6: focus is by construction
    return CamKey(frame, i, pose, set_fstop(ref["params"]["fstop"], profile.radius),
                  max(focus_depth(pose, focus), 1e-3), tuple(tgt.point) if tgt else None)


def camera_keys(s, profile, catalog):
    fps, n, shots = s["format"]["fps"], frame_count(s["format"]), s["shots"]
    keys, prev = [], None
    for f in range(0, n + 2):  # frames 0 and n+1 carry the end velocity into frames 1 and n's blur
        i = shot_index(shots, (f - 1) / fps)
        if prev is not None and i != prev:
            keys.append(_key(f - 1 + SHUTTER / 2, prev, s, profile, catalog))
            keys.append(_key(f - SHUTTER / 2, i, s, profile, catalog))
        keys.append(_key(f, i, s, profile, catalog))
        prev = i
    return keys


def key_frames(s, limit=None):
    """A few frames that stand for the clip: the hook frame (t = 0.5 s, TIERS T3-15), each shot's
    middle, and the last frame. Tests pass limit=3. Never render a full sequence in a test."""
    fps, n = s["format"]["fps"], frame_count(s["format"])
    frames = [int(round(0.5 * fps)) + 1, n]
    frames += [int(round((sh["startS"] + sh["endS"]) / 2 * fps)) + 1 for sh in s["shots"]]
    out = sorted({max(1, min(n, f)) for f in frames})
    if limit and len(out) > limit:
        idx = sorted({round(k * (len(out) - 1) / (limit - 1)) for k in range(limit)}) if limit > 1 else [0]
        out = [out[j] for j in idx]
    return out
