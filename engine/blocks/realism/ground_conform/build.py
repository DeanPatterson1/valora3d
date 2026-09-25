"""Ground-cover conformity (TAXONOMY CD-07, HF-06 static; METHODS §2.1 CD-07). Foliage vertices inside the
subject's footprint (its placed bounds in x/y, through the rig at frame 1) are pressed to 2 mm; those within
a ring of MARGIN_FRAC x longest lean away from the footprint, strongest at its edge. Stacked after
foliage_sway (resolver ORDER), so pressed blades stay pressed in any wind. The subject's sink into the
cover is contact_ground's sinkMm. Parting grass behind a moving subject (HF-06 dynamic) waits for phase-5
drive."""
MARGIN_FRAC = 0.15    # lean-away ring width, x the subject's longest side (eng)
PRESSED_Z = 0.002     # a pressed blade lies 2 mm high (eng)


def build(ctx):
    import numpy as np
    from engine.blender import gn
    from engine.blender.realism_rig import FOLIAGE_TAG, SWAY, SWAY_LEN, record, rig
    prof, scene = ctx.profile, ctx.scene
    objs = [o for o in scene.objects if o.get(FOLIAGE_TAG) and o.type == "MESH"]
    _, offset = rig()
    scene.frame_set(1)
    m = np.array(offset.matrix_world)
    corners = np.array([[x, y, 0.0, 1.0] for x in (prof.boundsMin[0], prof.boundsMax[0])
                        for y in (prof.boundsMin[1], prof.boundsMax[1])]) @ m.T
    lo, hi = corners[:, :2].min(axis=0), corners[:, :2].max(axis=0)
    margin = MARGIN_FRAC * prof.longest
    t = gn.Tree("valora_rz_ground_conform")
    mw = t.object_transform(t.self_object())
    wp = t.point(t.position(), mw)
    x, y, z = t.xyz(wp)
    dx = t.math("MAXIMUM", t.math("MAXIMUM", t.math("SUBTRACT", float(lo[0]), x), t.math("SUBTRACT", x, float(hi[0]))), 0.0)
    dy = t.math("MAXIMUM", t.math("MAXIMUM", t.math("SUBTRACT", float(lo[1]), y), t.math("SUBTRACT", y, float(hi[1]))), 0.0)
    dist = t.math("SQRT", t.math("ADD", t.math("MULTIPLY", dx, dx), t.math("MULTIPLY", dy, dy)))
    inside = t.math("LESS_THAN", dist, 1e-6)
    cx, cy = float(0.5 * (lo[0] + hi[0])), float(0.5 * (lo[1] + hi[1]))
    out = t.vmath("NORMALIZE", t.vec(t.math("SUBTRACT", x, cx), t.math("SUBTRACT", y, cy), 0.0))
    near = t.math("SUBTRACT", 1.0, t.smoothstep(0.0, margin, dist))
    u = t.attr(SWAY)
    lean = t.math("MULTIPLY", t.math("MULTIPLY", near, ctx.params["leanFrac"]),
                  t.math("MULTIPLY", t.attr(SWAY_LEN), t.math("MULTIPLY", u, u)))
    leaned = t.vmath("ADD", wp, t.vmath("SCALE", out, scale=lean))
    pressed = t.vec(x, y, t.math("MINIMUM", z, PRESSED_Z))
    t.set_position(t.point(t.switch_vec(inside, leaned, pressed), t.invert(mw)))
    ng = t.finish()
    n_in = n_ring = 0
    for o in objs:
        gn.add_modifier(o, ng, "valora_rz_ground_conform")
        co = np.empty(len(o.data.vertices) * 3)
        o.data.vertices.foreach_get("co", co)
        mo = np.array(o.matrix_world)
        roots = (co.reshape(-1, 3) @ mo[:3, :3].T + mo[:3, 3])[::3]   # lawn contract: root vertex first
        d = np.hypot(np.maximum(np.maximum(lo[0] - roots[:, 0], roots[:, 0] - hi[0]), 0),
                     np.maximum(np.maximum(lo[1] - roots[:, 1], roots[:, 1] - hi[1]), 0))
        n_in += int((d == 0).sum())
        n_ring += int(((d > 0) & (d < margin)).sum())
    record("conform_pressed_blades", n_in)
    record("conform_leaning_blades", n_ring)
