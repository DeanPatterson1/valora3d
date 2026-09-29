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
Hero pass (2026-09-28): alongFrac slides the camera car along the heading (x half the subject's length: -1 puts
it level with the tail, so side + alongFrac < 0 is a rear three-quarter chase or a camera beside the rear wheel);
aimAlongFrac slides the aim point the same way (0.5 aims between the centre and the nose end) and aimDropFrac lowers
it by that share of the height (a low camera aimed at a wheel, not at the roof line). All three default to 0: the
original programme unchanged.
Recorded, not built: shutter 0.5-0.75 for vehicles (the compiler's shutter is set by the tier) and camera
shake coupling (VD-06, phase 7)."""
import math

from engine.camera_context import rest_forward
from engine.geometry import Pose

MIN_HEIGHT_M = 0.03


def _normal(h, side):
    return (h[1], -h[0]) if side == "right" else (-h[1], h[0])


def _half_len(profile):
    return 0.5 * max(profile.sizeM[0], profile.sizeM[1])


def _place(params, anchor, heading, radius, h_size, mode, half_len=0.0):
    d = params["distance"] * radius
    cx, cy, _ = anchor.center
    a = params.get("alongFrac", 0.0) * half_len
    cx, cy = cx + heading[0] * a, cy + heading[1] * a
    if mode == "lead":
        ox, oy = heading[0] * d, heading[1] * d
    elif mode == "tail":
        ox, oy = -heading[0] * d, -heading[1] * d
    else:                                            # side, and the flyby's roadside spot
        n = _normal(heading, params["side"])
        ox, oy = n[0] * d, n[1] * d
    z = anchor.boundsMin[2] + max(MIN_HEIGHT_M, params["heightFrac"] * h_size)
    return (cx + ox, cy + oy, z)


def _aim(params, anchor, heading, h_size, half_len):
    cx, cy, cz = anchor.center
    a = params.get("aimAlongFrac", 0.0) * half_len
    return (cx + heading[0] * a, cy + heading[1] * a, cz - params.get("aimDropFrac", 0.0) * h_size)


def sample(params, profile, u, target=None, ctx=None):
    track = ctx.track if ctx is not None else None
    mode = params["mode"]
    if track is None:                                # a still subject: frame the rest pose
        fwd, hl = rest_forward(profile), _half_len(profile)
        pos = _place(params, profile, fwd, profile.radius, profile.sizeM[2], mode, hl)
        return Pose(position=pos, target=_aim(params, profile, fwd, profile.sizeM[2], hl), lens_mm=params["lensMm"])
    radius, h_size, hl = track.profile.radius, track.profile.sizeM[2], _half_len(track.profile)
    t = track.t(u)
    if mode == "flyby":
        tp = track.t(params["passU"])
        pos = _place(params, track.at(tp), track.heading(tp), radius, h_size, mode, hl)
        return Pose(position=pos, target=_aim(params, track.at(t), track.heading(t), h_size, hl),
                    lens_mm=params["lensMm"])
    tl = t - params["lagS"]
    anchor, hd = track.at(tl), track.heading(tl)
    pos = _place(params, anchor, hd, radius, h_size, mode, hl)
    return Pose(position=pos, target=_aim(params, anchor, hd, h_size, hl), lens_mm=params["lensMm"])
