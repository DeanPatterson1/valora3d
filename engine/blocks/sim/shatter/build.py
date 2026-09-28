"""shatter build (phase 6 Task 102): rebuilds every shard from keys.json "info" (its pane-local vertices around
its centroid, and faces) and keys it from the baked rows (pieces.key_pieces: LINEAR keys, render frame = bake frame
+ offset). Before the impact the shards rest in place, so the prop reads whole. Never a rigid world here
(SimInCompile). Materials: clear glass (IOR 1.52, a faint green edge tint), ice (IOR 1.31, frosted), or a matte
plaster wall; glass and ice keep sharp faces (flat shading) so the fracture edges catch light."""
import json
from pathlib import Path

from engine.bake.run import BakeMissing

LOOKS = {   # (base colour, roughness, transmission, IOR)  (eng; G3 owner grade)
    "prop_glass": ((0.97, 1.0, 0.98), 0.0, 1.0, 1.52),
    "prop_ice": ((0.9, 0.95, 1.0), 0.12, 1.0, 1.31),
    "prop_wall": ((0.82, 0.8, 0.76), 0.9, 0.0, 1.5),
}


def _material(target):
    import bpy
    name = f"valora_shatter_{target}"
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        sh = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        col, rough, trans, ior = LOOKS[target]
        sh.inputs["Base Color"].default_value = (*col, 1.0)
        sh.inputs["Roughness"].default_value = rough
        sh.inputs["Transmission Weight"].default_value = trans
        sh.inputs["IOR"].default_value = ior
    return m


def build(ctx):
    import bmesh
    import bpy
    from engine.blender import pieces as P
    b = ctx.bake
    f = Path(b["dir"]) / "keys.json" if b else None
    if f is None or not f.is_file():
        raise BakeMissing(f"shatter: no keys.json in {b and b['dir']}")
    keys = json.loads(f.read_text(encoding="utf-8"))
    info = keys["info"]
    mat = _material(info["target"])

    def one(name):
        sh = info["shards"][name]
        bm = bmesh.new()
        vs = [bm.verts.new(v) for v in sh["verts"]]
        for face in sh["faces"]:
            try:
                bm.faces.new([vs[j] for j in face])
            except ValueError:
                pass
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        ctx.scene.collection.objects.link(ob)
        return ob
    shards = P.key_pieces(ctx, keys, "sim/shatter", one)
    _intact(ctx, info, shards, keys, mat)


def _intact(ctx, info, shards, keys, mat):
    """Until the release frame the prop renders as ONE whole box (no pre-cut cracks on screen); from then on the
    shards take over. Visibility is keyed CONSTANT (hide_render / hide_viewport)."""
    import bmesh
    import bpy
    from mathutils import Matrix
    pane = info.get("pane")
    if not pane:
        return
    rel = info["release"] + ctx.bake["frames"]["offset"]
    w, t, h = pane["dims"]
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = (v.co.x * w, v.co.y * t, v.co.z * h)
    me = bpy.data.meshes.new("valora_shatter_intact")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new("valora_shatter_intact", me)
    ctx.scene.collection.objects.link(ob)
    ob["valora_block"] = "sim/shatter"
    ob.matrix_world = Matrix(pane["matrix"])
    for o, before in [(ob, False)] + [(s, True) for s in shards]:
        for frame, hidden in ((rel - 1, before), (rel, not before)):
            o.hide_render = o.hide_viewport = hidden
            o.keyframe_insert("hide_render", frame=frame)
            o.keyframe_insert("hide_viewport", frame=frame)
