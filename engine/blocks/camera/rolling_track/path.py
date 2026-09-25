"""rolling_track (phase 5 Task 84, CATALOG-GAPS rank 5): the camera car (vehicles.md V-C09, V-C10).

follows "subject": the programme is solved against the subject's live track (engine/camera_context.Track,
passed as ctx.track by every call site), in its HEADING frame (the travel direction, engine/camera_context):
- side / lead / tail: a fixed offset of distance x radius (the rest radius) beside (on `side` of the travel
  direction), ahead of or behind the subject's pose at t - lagS, at heightFrac x height above its ground,
  aimed at that pose's centre. The lag (0.1-0.3 s) is analytic: the camera targets the pose at t - lag, so a
  launch or a brake reads as the camera car reacting late, with no filter state;
- flyby: anchored beside the subject's pose at passU (on `side` of its heading there), panning to follow the
  live subject: the closest approach is at passU.
Without a track (a still subject: the checker reports camera_needs_motion; the motion rules' lock test) it
frames the rest pose the same way. requiresMotion ["translates"]. linearByDesign: a camera car has no ease.
Recorded, not built: shutter 0.5-0.75 for vehicles (the compiler's shutter is set by the tier) and camera
shake coupling (VD-06, phase 7)."""
import math

from engine.camera_context import rest_forward
from engine.geometry import Pose

MIN_HEIGHT_M = 0.03


def _normal(h, side):
    return (h[1], -h[0]) if side == "right" else (-h[1], h[0])


def _place(params, anchor, heading, radius, h_size, mode):
    d = params["distance"] * radius
    cx, cy, _ = anchor.center
    if mode == "lead":
        ox, oy = heading[0] * d, heading[1] * d
    elif mode == "tail":
        ox, oy = -heading[0] * d, -heading[1] * d
    else:                                            # side, and the flyby's roadside spot
        n = _normal(heading, params["side"])
        ox, oy = n[0] * d, n[1] * d
    z = anchor.boundsMin[2] + max(MIN_HEIGHT_M, params["heightFrac"] * h_size)
    return (cx + ox, cy + oy, z)


def sample(params, profile, u, target=None, ctx=None):
    track = ctx.track if ctx is not None else None
    mode = params["mode"]
    if track is None:                                # a still subject: frame the rest pose
        pos = _place(params, profile, rest_forward(profile), profile.radius, profile.sizeM[2], mode)
        return Pose(position=pos, target=tuple(profile.center), lens_mm=params["lensMm"])
    radius, h_size = track.profile.radius, track.profile.sizeM[2]
    t = track.t(u)
    if mode == "flyby":
        tp = track.t(params["passU"])
        pos = _place(params, track.at(tp), track.heading(tp), radius, h_size, mode)
        return Pose(position=pos, target=tuple(track.at(t).center), lens_mm=params["lensMm"])
    tl = t - params["lagS"]
    anchor = track.at(tl)
    pos = _place(params, anchor, track.heading(tl), radius, h_size, mode)
    return Pose(position=pos, target=tuple(anchor.center), lens_mm=params["lensMm"])
