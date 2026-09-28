"""TEST ONLY: key the cube from the bake's keys.json (LINEAR keys, so object motion blur works). Reads the
cache only; it never simulates (SimInCompile)."""
import json
from pathlib import Path

from engine.bake.run import BakeMissing

SIZE = 0.05


def build(ctx):
    import bpy
    b = ctx.bake
    f = Path(b["dir"]) / "keys.json" if b else None
    if f is None or not f.is_file():
        raise BakeMissing(f"_test_drop: no keys.json in {b and b['dir']}")
    keys = json.loads(f.read_text(encoding="utf-8"))
    me = bpy.data.meshes.new("valora_sim_test_drop")
    bm_verts = [(x * SIZE / 2, y * SIZE / 2, z * SIZE / 2) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(bm_verts, [], faces)
    ob = bpy.data.objects.new("valora_sim_test_drop", me)
    ctx.scene.collection.objects.link(ob)
    ob["valora_block"] = "sim/_test_drop"
    ob.rotation_mode = "QUATERNION"
    first, off = keys["frames"][0], b["frames"]["offset"]
    for i, row in enumerate(keys["pieces"]["cube"]):
        frame = first + i + off
        ob.location, ob.rotation_quaternion = row[:3], row[3:]
        ob.keyframe_insert("location", frame=frame)
        ob.keyframe_insert("rotation_quaternion", frame=frame)
    from engine.blender.realism_rig import fcurves
    for c in fcurves(ob.animation_data.action):
        for kp in c.keyframe_points:
            kp.interpolation = "LINEAR"
