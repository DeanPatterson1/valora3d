"""Overshoot-and-settle after a stop, squash-and-recover after a landing (TAXONOMY SF-05, RB-01, CD-04;
products.md P-M01). Keyed on the realism offset, so it adds to whatever the motion block does. The
subject is centred on the offset's origin in x/y and stands on z = 0, so scaling the offset squashes
it about its own footprint. Events come from motion_track (the subject's centre under the full transform), and a
world direction goes into the offset's frame through the motion's full rotation at that frame, not the yaw
alone (review chunk5 #2: a toppled subject rests turned about a horizontal axis). A landing squash scales
the offset's own z, so it is skipped (settle_squash_skipped) when that z is tilted off the world's up."""
import math

from engine.physics import events, settle

UPRIGHT_COS = math.cos(math.radians(5.0))   # (eng) a squash needs the offset's z within 5 deg of world up


def build(ctx):
    from engine.blender.realism_rig import key_series, motion_track, motion_transforms, record, rig
    p, prof, scene = ctx.params, ctx.profile, ctx.scene
    fps, n = ctx.script["format"]["fps"], scene.frame_end
    _, offset = rig()
    pos, _yaw = motion_track(scene)
    rot = [R for _, R in motion_transforms(scene)]
    x0, y0 = offset.location.x, offset.location.y
    ox, oy, sz = [x0] * n, [y0] * n, [1.0] * n
    window = int(1.5 * p["settleS"] * fps) + 1
    v = events.speeds(pos, fps)
    thr = events.MOVE_FRAC * prof.longest
    stops = events.stops(pos, fps, prof.longest)
    for e in stops:
        i = e["frame"] - 1          # index of the first resting position
        j = i - 1
        while j > 0 and v[j] > thr:
            j -= 1
        amp = p["overshootFrac"] * math.dist(pos[j], pos[i])
        # e["dir"] is a world direction; the offset lives under the turned motion empty (review fix 2):
        # local = R^T dir with the full rotation (chunk5 #2); the along-local-z part is not keyed here
        R = rot[e["frame"] - 1]
        lx = R[0][0] * e["dir"][0] + R[1][0] * e["dir"][1]
        ly = R[0][1] * e["dir"][0] + R[1][1] * e["dir"][1]
        for f in range(e["frame"], min(n, e["frame"] + window) + 1):
            d = settle.overshoot((f - e["frame"]) / fps, amp, p["settleS"])
            ox[f - 1] += lx * d
            oy[f - 1] += ly * d
    lands = events.landings(pos, fps, prof.longest)
    upright = [e for e in lands if rot[e["frame"] - 1][2][2] >= UPRIGHT_COS]   # local z still (nearly) world up
    for e in upright:
        for f in range(e["frame"], min(n, e["frame"] + window) + 1):
            sz[f - 1] = settle.squash_z((f - e["frame"]) / fps, p["squash"], p["settleS"])
    frames = list(range(1, n + 1))
    if stops:
        key_series(offset, "location", 0, frames, ox)
        key_series(offset, "location", 1, frames, oy)
    if upright and p["squash"] < 1.0:
        sxy = [settle.squash_xy(z) for z in sz]
        key_series(offset, "scale", 0, frames, sxy)
        key_series(offset, "scale", 1, frames, sxy)
        key_series(offset, "scale", 2, frames, sz)
    record("settle_stops", len(stops))
    record("settle_landings", len(lands))
    record("settle_landing_frames", [e["frame"] for e in lands])
    record("settle_squash_skipped", len(lands) - len(upright))
