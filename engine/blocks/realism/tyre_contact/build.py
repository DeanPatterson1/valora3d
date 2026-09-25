"""Loaded tyres (TAXONOMY CD-02; METHODS §2.1 M-GND). The whole vehicle drops by the tyre deflection d
(realism offset); every tyre-band vertex below the ground is clamped onto it (the flat patch) and the low
sidewall bulges along the axle: engine/physics/tyre.deform, written in nodes. The modifier is stacked after
wheel_roll's, so a rolling wheel keeps its patch at the bottom (METHODS CD-02). A model whose tyres are
already flat at the bottom (tyre.preflattened, per wheel) keeps its own patch: a second one would double
the load. Wheels the source model left a few mm off the ground come down first (tyre.axle_plan): a whole
floating axle turns the car about the grounded axle's contact line; a lone wheel drops with its rim,
capped at min(20 mm, 0.05 r)."""
from engine.physics import tyre as T
from engine.physics.wheel_mask import half_width


def _axis(w):
    ai = max(range(3), key=lambda k: abs(w["axis"][k]))
    return ai, tuple(1.0 if k == ai else 0.0 for k in range(3))


def _modelled(meshes, n_wheels, fwd):
    """Per wheel: (flat length the model's own tyre already has at its bottom, its lowest z), placed space."""
    import numpy as np
    from engine.blender.realism_rig import TYRE, placed_points
    pts = {i: [] for i in range(n_wheels)}
    for o in meshes:
        a = o.data.attributes.get(TYRE)
        if a is None:
            continue
        tag = np.empty(len(o.data.vertices), np.int32)
        a.data.foreach_get("value", tag)
        P = placed_points(o)
        for i in range(n_wheels):
            if (tag == i + 1).any():
                pts[i].append(P[tag == i + 1])
    flats, bottoms = [], []
    for i in range(n_wheels):
        if not pts[i]:
            flats.append(0.0)
            bottoms.append(0.0)
            continue
        p = np.vstack(pts[i])
        flat = p[p[:, 2] <= p[:, 2].min() + T.PREFLAT_TOL_M] @ np.asarray(fwd, dtype=float)
        flats.append(float(flat.max() - flat.min()))
        bottoms.append(float(p[:, 2].min()))
    return flats, bottoms


def build(ctx):
    from engine.blender import gn
    from engine.blender.realism_rig import TYRE, UNSPRUNG, record, rig, tag_wheels
    p, prof = ctx.params, ctx.profile
    _, offset = rig()
    counts = tag_wheels(ctx.meshes, prof.wheels)
    fwd = (prof.vehicle or {}).get("forwardAxis", [0.0, 1.0, 0.0])
    modelled, bottoms = _modelled(ctx.meshes, len(prof.wheels), fwd)
    plan = T.axle_plan(prof.wheels, bottoms, fwd)       # a floating axle tilts the car (review fix 4)
    drops, tilt = plan["drops"], plan["tilt"]
    pre = [T.preflattened(f, w["radius"], p["patchLenFrac"]) for f, w in zip(modelled, prof.wheels)]
    record("tyre_modelled_flat_m", modelled)
    record("tyre_wheel_drop_m", drops)
    record("tyre_tilt_rad", tilt["angle"] if tilt else 0.0)
    record("tyre_preflattened", pre)
    flatten = not all(pre)            # per wheel: an already loaded tyre keeps its own patch
    if not flatten and tilt is None and not any(drops):
        record("tyre_d_m", 0.0)
        record("tyre_objects", 0)
        return
    r_med = sorted(w["radius"] for w in prof.wheels)[len(prof.wheels) // 2]
    d = T.deflection(r_med, p["patchLenFrac"]) if flatten else 0.0   # one drop for the car (per-axle: later)
    offset.location.z -= d
    sink = float(ctx.scene.get("valora_rz_sink_m", 0.0))
    t = gn.Tree("valora_rz_tyre_contact")
    P, back = gn.placed(t, offset)
    ground = gn.ground_in_placed(t, offset, -sink)   # tyres flatten on the hard layer under soft cover
    tag, uns = t.attr(TYRE), t.attr(UNSPRUNG)
    new = P
    if tilt is not None:              # the whole vehicle turns about the grounded axle's contact line
        piv = t.vec(*tilt["pivot"])
        new = t.vmath("ADD", t.rotate(t.vmath("SUBTRACT", new, piv), t.vec(*tilt["axis"]), tilt["angle"]), piv)
    for i, drop in enumerate(drops):  # a lone wheel modelled a little off the ground comes down onto it first
        if drop > 0.0:
            new = t.switch_vec(t.equals(uns, i + 1), new, t.vmath("SUBTRACT", new, t.vec(0.0, 0.0, drop)))
    for i, w in enumerate(prof.wheels):
        if pre[i] and flatten:        # mixed set: a loaded tyre is only kept out of the ground
            comps = t.xyz(new)
            new = t.switch_vec(t.equals(tag, i + 1), new, t.vec(comps[0], comps[1], t.math("MAXIMUM", comps[2], ground)))
            continue
        if pre[i]:
            continue
        ai, axis = _axis(w)
        comps = t.xyz(new)
        z2 = t.math("MAXIMUM", comps[2], ground)
        h = t.math("SUBTRACT", z2, ground)
        k = t.math("MULTIPLY", p["bulgeFrac"] * T.deflection(w["radius"], p["patchLenFrac"]),
                   t.math("SUBTRACT", 1.0, t.smoothstep(0.0, T.BULGE_FALLOFF * w["radius"], h)))
        axial = t.math("SUBTRACT", comps[ai], w["center"][ai])
        side = t.math("MINIMUM", 1.0, t.math("DIVIDE", t.math("ABSOLUTE", axial), half_width(w)))
        push = t.math("MULTIPLY", t.math("MULTIPLY", k, side), t.math("SIGN", axial))
        moved = t.vmath("ADD", t.vec(comps[0], comps[1], z2), t.vmath("SCALE", t.vec(*axis), scale=push))
        new = t.switch_vec(t.equals(tag, i + 1), new, moved)
    t.set_position(back(new))
    ng = t.finish()
    n = 0
    for o in ctx.meshes:
        if o.data.attributes.get(TYRE) is not None:
            n += 1
        if tilt is not None or o.data.attributes.get(TYRE) is not None:   # a tilt moves the body too
            gn.add_modifier(o, ng, "valora_rz_tyre_contact")
    record("tyre_d_m", d)
    record("tyre_objects", n)
    record("tyre_tagged_verts", counts["tyre"])
