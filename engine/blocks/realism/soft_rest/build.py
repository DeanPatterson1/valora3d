"""Soft rest dip (TAXONOMY CD-03 static; METHODS §2.1 M-GND): the subject drops by dip = sinkFrac x height
(realism offset); every vertex below the floor is clamped onto it (flat footprint) and the low surface
bulges out from the footprint centre (engine/physics/contact.soft_deform, in nodes).
The dip is contact.soft_dip_m (review fix 6): nothing unless the vertices touching the ground are mostly
on soft-cued materials (ingest's soft_cue: sheen, subsurface > 0.2 or a normal map), and at most
contact.HARD_DIP_MAX_M on a hard floor, where only the subject gives."""
from engine.physics import contact as C

CONTACT_BAND_FRAC = 0.02   # contact vertices: within 2% of the height of the lowest point (= ingest touchesGround)


def _soft_material(mat):
    if mat is None or not mat.use_nodes:
        return False
    n = next((x for x in mat.node_tree.nodes if x.type == "BSDF_PRINCIPLED"), None)
    if n is None:
        return False
    sock = lambda name: n.inputs.get(name)
    sheen, sss, nrm = sock("Sheen Weight"), sock("Subsurface Weight"), sock("Normal")
    return bool((sheen is not None and (sheen.is_linked or sheen.default_value > 0.0))
                or (sss is not None and (sss.is_linked or sss.default_value > 0.2))
                or (nrm is not None and nrm.is_linked))


def contact_soft_share(meshes, H):
    """Share of the subject's ground-contact vertices whose faces carry a soft-cued material."""
    import numpy as np
    from engine.blender.realism_rig import placed_points
    pts = [(o, placed_points(o)) for o in meshes if len(o.data.vertices)]
    if not pts:
        return 0.0
    zmin = min(float(P[:, 2].min()) for _, P in pts)
    soft = total = 0
    for o, P in pts:
        near = P[:, 2] <= zmin + CONTACT_BAND_FRAC * H
        if not near.any():
            continue
        me = o.data
        slots = np.array([_soft_material(s.material) for s in o.material_slots] or [False])
        mi = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get("material_index", mi)
        lt = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get("loop_total", lt)
        lv = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get("vertex_index", lv)
        flag = np.zeros(len(P), bool)
        np.logical_or.at(flag, lv, slots[np.clip(np.repeat(mi, lt), 0, len(slots) - 1)])
        soft += int((flag & near).sum())
        total += int(near.sum())
    return soft / total if total else 0.0


def build(ctx):
    from engine.blender import gn
    from engine.blender.realism_rig import record, rig
    p, prof = ctx.params, ctx.profile
    _, offset = rig()
    H = prof.sizeM[2]
    share = contact_soft_share(ctx.meshes, H)
    world = (ctx.catalog.get("world", ctx.script["world"]["id"]) if ctx.catalog else None) or {}
    dip = C.soft_dip_m(p["sinkFrac"], H, world.get("groundType", "studio"), share)
    record("soft_contact_share", share)
    if dip <= 0.0:
        record("soft_dip_m", 0.0)
        return
    offset.location.z -= dip
    gc = prof.groundContacts or [{"center": [0.0, 0.0, 0.0], "share": 1.0}]
    cx = sum(g["center"][0] * g["share"] for g in gc) / sum(g["share"] for g in gc)
    cy = sum(g["center"][1] * g["share"] for g in gc) / sum(g["share"] for g in gc)
    sink = float(ctx.scene.get("valora_rz_sink_m", 0.0))
    t = gn.Tree("valora_rz_soft_rest")
    P, back = gn.placed(t, offset)
    ground = gn.ground_in_placed(t, offset, -sink)
    px, py, pz = t.xyz(P)
    z2 = t.math("MAXIMUM", pz, ground)
    k = t.math("MULTIPLY", p["bulgeFrac"] * dip,
               t.math("SUBTRACT", 1.0, t.smoothstep(0.0, C.SOFT_FALLOFF * H, t.math("SUBTRACT", z2, ground))))
    radial = t.vmath("NORMALIZE", t.vec(t.math("SUBTRACT", px, cx), t.math("SUBTRACT", py, cy), 0.0))
    t.set_position(back(t.vmath("ADD", t.vec(px, py, z2), t.vmath("SCALE", radial, scale=k))))
    ng = t.finish()
    for o in ctx.meshes:
        gn.add_modifier(o, ng, "valora_rz_soft_rest")
    record("soft_dip_m", dip)
