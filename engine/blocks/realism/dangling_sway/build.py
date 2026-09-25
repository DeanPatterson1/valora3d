"""Dangling sway (TAXONOMY SC-08, SF-02, SF-03; METHODS §2.11 M-KIN): the hanging part turns rigidly about
its pivot with the shared wind (engine/blender/sway_nodes.pivot_tree, the mirror of
engine/physics/sway.swing_point), so it never stretches. Swing from the subject's own acceleration (a strap
swinging after a stop) needs moving subjects and lands with phase 5 (Deferred). The wind is world-fixed:
the subject's own motion does not change the swing direction, which is what real straps do."""


def build(ctx):
    import bpy
    from engine.blender import gn
    from engine.blender.realism_rig import SWAY_PIVOT, record, tag_dangling
    from engine.blender.sway_nodes import pivot_tree
    tagged, total = tag_dangling(ctx.meshes, ctx.profile.danglingParts or [])
    record("dangling_verts", tagged)
    record("dangling_total_verts", total)
    if not tagged or bpy.data.node_groups.get("valora_wind") is None:
        return
    ng = pivot_tree("valora_rz_dangling_sway", ctx.params["stiffness"], ctx.params["flutter"])
    for o in ctx.meshes:
        if o.data.attributes.get(SWAY_PIVOT) is not None:
            gn.add_modifier(o, ng, "valora_rz_dangling_sway")
