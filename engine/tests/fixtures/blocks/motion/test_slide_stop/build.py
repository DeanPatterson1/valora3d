"""TEST ONLY: slide along the long axis (quadratic ease-out, so speed falls linearly to 0) and stop.
coast: slide at constant speed over the whole clip instead, extrapolated past both ends.
yawDeg: a constant yaw on valora_motion (the world slide direction stays the same)."""
import math


def build(ctx):
    import bpy
    from engine.blender.realism_rig import MOTION, key_series
    prof, n = ctx.profile, ctx.scene.frame_end
    stop = max(3, round(0.6 * n))
    ax = 0 if prof.sizeM[0] >= prof.sizeM[1] else 1
    dist = ctx.params["distanceFrac"] * prof.longest
    frames = list(range(1, stop + 1))
    vals = [-dist / 2 + dist * (1 - (1 - (f - 1) / (stop - 1)) ** 2) for f in frames]
    motion = bpy.data.objects[MOTION]
    if ctx.params.get("coast"):   # constant speed, running on past both ends (never stops)
        frames = list(range(1, n + 1))
        key_series(motion, "location", ax, frames, [-dist / 2 + dist * (f - 1) / (n - 1) for f in frames],
                   extrapolate=True)
    else:
        key_series(motion, "location", ax, frames, vals)
    motion.rotation_euler[2] = math.radians(ctx.params.get("yawDeg", 0.0))
