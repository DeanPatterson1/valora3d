"""TEST ONLY: ground plane + 400 real-size grass blades in a ring around the subject (never inside its
bounds + 20%), plus 20 rooted inside its footprint (ground_conform presses them flat). Blades are separate triangles (islands) carrying the foliage contract attributes."""
import math

BLADE_H, BLADE_W = 0.12, 0.012   # real grass: 12 cm tall, 1.2 cm wide at the root (scale cue, never scaled)


def build(ctx):
    import bpy
    import numpy as np
    from engine.blender.realism_rig import FOLIAGE_TAG, GROUND_TAG, SWAY, SWAY_LEN, write_attr
    prof, rng = ctx.profile, ctx.rng
    size = 40.0 * prof.longest
    me = bpy.data.meshes.new("test_lawn_ground")
    me.from_pydata([(-size, -size, 0), (size, -size, 0), (size, size, 0), (-size, size, 0)], [], [(0, 1, 2, 3)])
    ground = bpy.data.objects.new("test_lawn_ground", me)
    ctx.scene.collection.objects.link(ground)
    ground[GROUND_TAG] = True
    gm = bpy.data.materials.new("test_lawn_soil")
    gm.use_nodes = True
    ground.data.materials.append(gm)
    r_in = 1.2 * max(prof.half[0], prof.half[1])
    verts, faces, sway, length = [], [], [], []
    for i in range(400):
        a, rr = rng.uniform(0, 2 * math.pi), rng.uniform(r_in, r_in + 2.0 * prof.longest + 0.5)
        x, y = rr * math.cos(a), rr * math.sin(a)
        k = len(verts)
        verts += [(x - BLADE_W / 2, y, 0.0), (x + BLADE_W / 2, y, 0.0), (x, y, BLADE_H)]
        faces.append((k, k + 1, k + 2))
        sway += [0.0, 0.0, 1.0]
        length += [BLADE_H] * 3
    for i in range(20):   # 20 blades rooted inside the footprint: they pierce the subject until ground_conform
        x = rng.uniform(prof.boundsMin[0] * 0.8, prof.boundsMax[0] * 0.8)
        y = rng.uniform(prof.boundsMin[1] * 0.8, prof.boundsMax[1] * 0.8)
        k = len(verts)
        verts += [(x - BLADE_W / 2, y, 0.0), (x + BLADE_W / 2, y, 0.0), (x, y, BLADE_H)]
        faces.append((k, k + 1, k + 2))
        sway += [0.0, 0.0, 1.0]
        length += [BLADE_H] * 3
    bm =bpy.data.meshes.new("test_lawn_grass")
    bm.from_pydata(verts, [], faces)
    grass = bpy.data.objects.new("test_lawn_grass", bm)
    ctx.scene.collection.objects.link(grass)
    grass[FOLIAGE_TAG] = True
    write_attr(grass, SWAY, np.array(sway), "FLOAT")
    write_attr(grass, SWAY_LEN, np.array(length), "FLOAT")
    world = bpy.data.worlds.new("test_lawn_sky")
    world.use_nodes = True
    ctx.scene.world = world
