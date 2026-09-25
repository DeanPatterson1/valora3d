"""Overshoot-and-settle after a stop, squash-and-recover after a landing (TAXONOMY SF-05, RB-01, CD-04;
products.md P-M01). Keyed on the realism offset, so it adds to whatever the motion block does. The
subject is centred on the offset's origin in x/y and stands on z = 0, so scaling the offset squashes
it about its own footprint."""
import math

from engine.physics import events, settle


def build(ctx):
    from engine.blender.realism_rig import key_series, motion_track, record, rig
    p, prof, scene = ctx.params, ctx.profile, ctx.scene
    fps, n = ctx.script["format"]["fps"], scene.frame_end
    _, offset = rig()
    pos, yaw = motion_track(scene)
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
        # e["dir"] is a world direction; the offset lives under the (yawed) motion empty (review fix 2)
        c, s = math.cos(-yaw[e["frame"] - 1]), math.sin(-yaw[e["frame"] - 1])
        lx, ly = c * e["dir"][0] - s * e["dir"][1], s * e["dir"][0] + c * e["dir"][1]
        for f in range(e["frame"], min(n, e["frame"] + window) + 1):
            d = settle.overshoot((f - e["frame"]) / fps, amp, p["settleS"])
            ox[f - 1] += lx * d
            oy[f - 1] += ly * d
    lands = events.landings(pos, fps, prof.longest)
    for e in lands:
        for f in range(e["frame"], min(n, e["frame"] + window) + 1):
            sz[f - 1] = settle.squash_z((f - e["frame"]) / fps, p["squash"], p["settleS"])
    frames = list(range(1, n + 1))
    if stops:
        key_series(offset, "location", 0, frames, ox)
        key_series(offset, "location", 1, frames, oy)
    if lands and p["squash"] < 1.0:
        sxy = [settle.squash_xy(z) for z in sz]
        key_series(offset, "scale", 0, frames, sxy)
        key_series(offset, "scale", 1, frames, sxy)
        key_series(offset, "scale", 2, frames, sz)
    record("settle_stops", len(stops))
    record("settle_landings", len(lands))
    record("settle_landing_frames", [e["frame"] for e in lands])
