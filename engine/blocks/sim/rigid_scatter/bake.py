"""rigid_scatter bake (phase 6 Task 100, stage 4b only): real-size procedural pieces (engine/blender/pieces.py)
dropped from engine/physics/scatter.spawn onto the subject's closed shell (passive MESH) and a ground slab
(passive BOX, top at z = 0). Pieces are ACTIVE convex hulls with use_margin and margin 0, 60 substeps and 20
solver iterations (formats.FORMATS['rigid_keys']); the world's time_scale is the block's timeScale. Bullet is
stepped with frame_set and every piece's loc + quat per frame goes to keys.json (rows rounded to 1e-5); the
per-piece size jitter and mesh variant go to keys.json's "info", so build() instances the very meshes that were
simulated."""
import json
from pathlib import Path

# The bake key hashes this file and build.py only (engine/bake/run.block_sha), not engine/blender/pieces.py:
# bump MESH_REV whenever a piece mesh or the Bullet helpers there change, or a stale cache is reused.
MESH_REV = 4


def bake(ctx):
    import bpy
    from engine.blender import pieces as P
    from engine.physics import scatter as S
    p, prof, b = ctx.params, ctx.profile, ctx.bake
    fr = b["frames"]
    sc = ctx.scene
    P.rigid_world(sc, fr, p["timeScale"])
    P.ground_slab(prof)
    P.passive(b["proxy"]["shell"], "MESH", friction=0.6, restitution=0.2)
    cam = ctx.hero_pose.position if ctx.hero_pose is not None else (prof.center[0], prof.center[1] - 1.0, 0.0)
    behind = (prof.center[0] - cam[0], prof.center[1] - cam[1])
    nf = fr["bake_last"] - fr["bake_first"] + 1
    pts = S.spawn(p, prof, ctx.seed, behind=behind, frames=nf)
    jit = S.size_jitter(ctx.seed, len(pts))
    kind, size = p["pieces"], S.piece_size_m(p["pieces"])
    obs, scale, variant = [], {}, {}
    for i, (pt, j) in enumerate(zip(pts, jit)):
        v = ctx.rng.randrange(P.VARIANTS[kind])
        ob = P.piece_object(sc, kind, size, v, f"valora_scatter_{i:03d}", "sim/rigid_scatter", lod="collide")
        ob.scale = (j, j, j)
        ob.location = pt
        ob.rotation_quaternion = S.random_quat(ctx.rng)
        scale[ob.name], variant[ob.name] = j, v
        obs.append(ob)
    bpy.context.view_layer.update()
    P.active(obs, kind, [size * j for j in jit])
    rows = P.record(sc, obs, fr)
    Path(b["dir"], "keys.json").write_text(json.dumps(
        {"frames": [fr["bake_first"], fr["bake_last"]], "pieces": rows,
         "info": {"kind": kind, "size": size, "scale": scale, "variant": variant}},
        separators=(",", ":")), encoding="utf-8")
    zs = [r[-1][2] for r in rows.values()]
    return {"pieces": len(obs), "countAsked": int(p["count"]), "estimateS": round(S.estimate_s(len(obs), nf), 1),
            "frames": fr["bake_last"] - fr["bake_first"] + 1, "kind": kind,
            "minRestZ": min(zs), "maxRestZ": max(zs)}
