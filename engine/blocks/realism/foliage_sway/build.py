"""Foliage sway (TAXONOMY HF-01..03; METHODS §2.5 M-GNT): the world's foliage (valora_foliage objects with
valora_sway / valora_sway_len) bends with the shared wind, each point keeping its distance from the blade's
root (review item 4). No wind field, still air or a breeze whose gust peak bends less than
engine/physics/sway.VISIBLE_DEG -> no deformer at all (review item 1: a Scene-Time tree re-evaluates the
whole foliage mesh every frame)."""


def build(ctx):
    import bpy
    from engine.blender import gn
    from engine.blender.realism_rig import FOLIAGE_TAG, record
    from engine.blender.sway_nodes import sway_tree, wind_moves
    objs = [o for o in ctx.scene.objects if o.get(FOLIAGE_TAG) and o.type == "MESH"]
    if bpy.data.node_groups.get("valora_wind") is None or not objs or not wind_moves(ctx, ctx.params["stiffness"]):
        record("foliage_objects", 0)
        return
    ng = sway_tree("valora_rz_foliage_sway", ctx.params["stiffness"], ctx.params["flutter"])
    for o in objs:
        gn.add_modifier(o, ng, "valora_rz_foliage_sway")
    record("foliage_objects", len(objs))
