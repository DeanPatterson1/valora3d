"""Soft rest dip (TAXONOMY CD-03 static; METHODS §2.1 M-GND): the subject drops by dip = sinkFrac x height
(realism offset); every vertex below the floor is clamped onto it (flat footprint) and the low surface
bulges out from the footprint centre (engine/physics/contact.soft_deform, in nodes)."""
from engine.physics import contact as C


def build(ctx):
    from engine.blender import gn
    from engine.blender.realism_rig import record, rig
    p, prof = ctx.params, ctx.profile
    _, offset = rig()
    H = prof.sizeM[2]
    dip = p["sinkFrac"] * H
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
