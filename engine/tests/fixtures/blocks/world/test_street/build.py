"""TEST ONLY: one ground plane tagged valora_ground, 40 subject lengths plus the drive lane on a side."""


def build(ctx):
    import bpy
    from engine.blender.realism_rig import GROUND_TAG
    size = 40.0 * ctx.profile.longest + 30.0
    me = bpy.data.meshes.new("test_street_ground")
    me.from_pydata([(-size, -size, 0), (size, -size, 0), (size, size, 0), (-size, size, 0)], [], [(0, 1, 2, 3)])
    ground = bpy.data.objects.new("test_street_ground", me)
    ctx.scene.collection.objects.link(ground)
    ground[GROUND_TAG] = True
    ground["valora_block"] = "world/test_street"
