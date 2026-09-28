"""debris_float build (phase 6 Task 101): the stateless sim kind (bake.method "none", ctx.bake is None). Every
piece's analytic path (engine/physics/debris.py) is keyed per frame over the whole clip, LINEAR (object motion
blur); outside the sim window the pieces are hidden (hide_render / hide_viewport keyed CONSTANT). Real meshes come
from engine/blender/pieces.py (CC0 by construction)."""


def build(ctx):
    from engine.blender import pieces as P
    from engine.physics import debris as D
    from engine.physics.scatter import continuous_quats, row
    s, p = ctx.script, ctx.params
    fps, dur = s["format"]["fps"], s["format"]["durationS"]
    n = int(round(dur * fps))
    lay = D.layout(p, ctx.profile, ctx.seed, dur)
    ref = next(r for r in s.get("sims", []) if r["id"] == "debris_float")
    a, b = int(round(ref["startS"] * fps)) + 1, int(round(ref["endS"] * fps)) + 1
    for i, x in enumerate(lay):
        v = ctx.rng.randrange(P.VARIANTS[p["pieces"]])
        ob = P.piece_object(ctx.scene, p["pieces"], x["size"], v, f"valora_debris_{i:02d}", "sim/debris_float")
        rows = continuous_quats([row(D.position(x, (f - 1) / fps), D.rotation(x, (f - 1) / fps))
                                 for f in range(0, n + 2)])
        P.key_rows(ob, 0, rows)
        if a > 1 or b < n:
            for flag, fr in ((a > 1, a - 1), (False, a), (True, b + 1)):
                ob.hide_render = ob.hide_viewport = flag
                ob.keyframe_insert("hide_render", frame=fr)
                ob.keyframe_insert("hide_viewport", frame=fr)
