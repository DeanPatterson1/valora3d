"""smoke_sim bake (phase 6 Task 113, GS-01 interactive / GS-09): a Mantaflow GAS domain around the subject
(engine/physics/gas.smoke_domain: <= 3 x longest, widened along a moving subject's path), the subject's closed
shell (ctx.bake["proxy"]["shell"], T97) as a COLLISION obstacle (moving: blender_bake parents it to the rig, so
Mantaflow reads its animation), and low, slightly warm sources so the smoke rolls along the ground and around the
subject:
- ground: SOURCES_GROUND discs on a ring just outside the footprint (bounds x 1.1), puffing upward;
- marker: one disc at the first emitter (a marker or an emissive / exhaust detail), else ground;
- tyres: one disc per rear tyre contact (engine/physics/tyre_smoke.rear_contacts), blowing backward.
Baked (shift mode: bake frame 1 = the first pre-roll frame) into ctx.bake["dir"] as OpenVDB, then only
data/*.vdb is kept. The report carries the domain (lo, hi, cells) and engine/blender/gas.density_stats over the
bake: density sums, NaN, and smoke voxels inside the shell AT EACH FRAME'S POSE (the moving-shell probe)."""
import math

SOURCES_GROUND = 6           # (eng, G10) discs on the ring
SOURCE_R_FRAC = 0.09         # (eng) disc radius x longest
COLOURS = {"white": (0.9, 0.9, 0.9), "grey": (0.55, 0.55, 0.56), "charcoal": (0.2, 0.2, 0.21),
           "red": (0.75, 0.18, 0.15), "blue": (0.2, 0.35, 0.8), "amber": (0.85, 0.55, 0.2)}


def sources(ctx):
    """[(centre, radius, velocity)] in placed metres at the bake's first frame."""
    from engine.physics.sim_facts import emitters
    prof, p = ctx.profile, ctx.params
    L = prof.longest
    r = max(0.03, SOURCE_R_FRAC * L)
    if p["source"] == "marker":
        em = emitters(prof, ctx.script.get("markers") or [])
        if em:
            pt, n = em[0]["point"], em[0]["normal"]
            nn = math.sqrt(sum(c * c for c in n)) or 1.0
            return [(tuple(pt), 0.5 * r, tuple(0.6 * c / nn for c in n))]
    if p["source"] == "tyres" and prof.wheels:
        from engine.physics.tyre_smoke import _forward, rear_contacts
        mk = ctx.script.get("markers") or []
        f = _forward(prof, mk)
        return [((c[0], c[1], max(c[2], 0.0) + 0.6 * r), r, (-1.5 * f[0], -1.5 * f[1], 0.3))
                for c in rear_contacts(prof, mk)]
    ring = math.hypot(prof.half[0], prof.half[1]) * 1.1 + r
    c = prof.center
    out = []
    for i in range(SOURCES_GROUND):
        a = 2 * math.pi * (i + ctx.rng.random() * 0.5) / SOURCES_GROUND
        out.append(((c[0] + ring * math.cos(a), c[1] + ring * math.sin(a), 0.6 * r), r, (0.0, 0.0, 0.15 * L)))
    return out


def _path(ctx):
    """Placed positions of the subject centre over the bake (a moving subject), from the keyed rig."""
    from engine.blender.realism_rig import motion_transforms
    fr = ctx.bake["frames"]
    try:
        tr = motion_transforms(ctx.scene, list(range(fr["bake_first"], fr["bake_last"] + 1, 4)))
    except Exception:
        return None
    c = ctx.profile.center
    pts = []
    for loc, rows in tr:
        pts.append(tuple(loc[i] + sum(rows[i][j] * c[j] for j in range(3)) for i in range(3)))
    return pts if max(math.dist(pts[0], q) for q in pts) > 0.05 * ctx.profile.longest else None


def bake(ctx):
    from engine.blender import gas as GB
    from engine.physics import gas as G
    p, fr = ctx.params, ctx.bake["frames"]
    path = _path(ctx)
    lo, hi = G.smoke_domain(ctx.profile, p["source"], path=path)
    res = int(min(G.RES_CAP, p["res"]))
    dom = GB.domain("valora_sim_smoke_domain", lo, hi, res=res, frame_start=fr["bake_first"],
                    frame_end=fr["bake_last"], cache_dir=ctx.bake["dir"], vorticity=0.2, dissolve=None,
                    time_scale=float(p["timeScale"]))
    colour = COLOURS[p["colour"]]
    srcs = sources(ctx)
    for i, (c, r, v) in enumerate(srcs):
        GB.source(f"valora_sim_smoke_src{i}", c, r, kind="SMOKE", temperature=0.35, density=float(p["density"]),
                  velocity=v, colour=colour)
    shells = [o for o in (ctx.bake["proxy"].get("shell"),) if o is not None]
    for o in shells:
        GB.obstacle(o)
    secs, files = GB.bake(dom, ctx.scene)
    n = fr["bake_last"] - fr["bake_first"] + 1
    step = max(1, n // 12)
    stats = GB.density_stats(dom, list(range(fr["bake_first"], fr["bake_last"] + 1, step)), obstacles=shells,
                             stride=max(1, res // 64))
    GB.keep_vdb_only(ctx.bake["dir"])
    return {"domain": {"lo": list(lo), "hi": list(hi), "cells": stats[-1]["res"] if stats else None, "res": res},
            "sources": len(srcs), "moving": path is not None, "vdbFiles": len(files), "simSeconds": round(secs, 2),
            "gas": stats}
