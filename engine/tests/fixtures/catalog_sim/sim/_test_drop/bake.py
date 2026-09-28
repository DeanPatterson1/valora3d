"""TEST ONLY: drop one 5 cm cube from 1.5 x the subject height onto the subject's closed shell (Bullet, stepped
with frame_set), and write its per-frame transform to keys.json (rigid_keys, engine/bake/formats.py)."""
import json
from pathlib import Path

SIZE = 0.05


def bake(ctx):
    import bpy
    sc, b, p = ctx.scene, ctx.bake, ctx.profile
    fr = b["frames"]
    bpy.ops.mesh.primitive_plane_add(size=max(4.0, 4 * p.longest))
    ground = bpy.context.object
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    ground.rigid_body.collision_shape = "BOX"
    shell = b["proxy"]["shell"]
    for o in bpy.context.scene.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = shell
    shell.select_set(True)
    bpy.ops.rigidbody.object_add(type="PASSIVE")
    shell.rigid_body.collision_shape = "MESH"
    bpy.ops.mesh.primitive_cube_add(size=SIZE)
    cube = bpy.context.object
    cube.location = (p.center[0] + ctx.rng.uniform(-0.1, 0.1) * p.half[0], p.center[1], 1.5 * p.boundsMax[2] + SIZE)
    bpy.ops.rigidbody.object_add(type="ACTIVE")
    cube.rigid_body.collision_shape = "CONVEX_HULL"
    for o in (cube, shell, ground):
        o.rigid_body.use_margin, o.rigid_body.collision_margin = True, 0.0
    w = sc.rigidbody_world
    w.substeps_per_frame, w.solver_iterations = 60, 20
    w.time_scale = float(ctx.params["timeScale"])
    w.point_cache.frame_start, w.point_cache.frame_end = fr["bake_first"], fr["bake_last"]
    rows = []
    for f in range(fr["bake_first"], fr["bake_last"] + 1):
        sc.frame_set(f)
        loc, rot = cube.matrix_world.to_translation(), cube.matrix_world.to_quaternion()
        rows.append([round(v, 5) for v in (*loc, *rot)])
    Path(b["dir"], "keys.json").write_text(json.dumps({"frames": [fr["bake_first"], fr["bake_last"]],
                                                       "pieces": {"cube": rows}}), encoding="utf-8")
    return {"pieces": 1, "frames": len(rows), "restZ": rows[-1][2]}
