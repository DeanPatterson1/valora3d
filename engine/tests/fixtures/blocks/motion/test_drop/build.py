"""TEST ONLY: free fall at g = 9.81 m/s^2 from heightFrac x the subject's height, then rest on z = 0."""


def build(ctx):
    import bpy
    from engine.blender.realism_rig import MOTION, key_series
    fps, n = ctx.script["format"]["fps"], ctx.scene.frame_end
    h = ctx.params["heightFrac"] * ctx.profile.sizeM[2]
    frames = list(range(1, n + 1))
    key_series(bpy.data.objects[MOTION], "location", 2, frames,
               [max(0.0, h - 0.5 * 9.81 * ((f - 1) / fps) ** 2) for f in frames])
