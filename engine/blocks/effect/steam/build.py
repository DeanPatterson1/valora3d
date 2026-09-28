"""steam (phase 6 Task 112, GS-02, stateless M-VOL): a thin wisp above a source, rising at riseMs and fading
within heightM (10-20 cm), real size (widthM 2-8 cm; METHODS R4/R5: steam is a scale cue, never scaled with the
subject). Source: the first emitter (engine/physics/sim_facts.emitters: a steam / vent / spout marker, or an
emissive / exhaust detail), else a marked opening (sim_facts.container), else the top centre of the subject.
The wisp is engine/blender/vdb.procedural_volume (seeded noise advected upward by a keyed mapping), leaning
downwind by windCalibration. Nothing is baked; the upload is never touched."""

DENSITY_PER_M = 60.0    # (eng, G9): at density 1 a 4 cm wisp is about 1.2 optical depths through its core


def source(ctx):
    """(point, how): where the steam rises from."""
    from engine.physics.sim_facts import container, emitters
    markers = ctx.script.get("markers") or []
    em = emitters(ctx.profile, markers)
    if em:
        return tuple(em[0]["point"]), em[0]["source"]
    c = container(ctx.profile, markers)
    if c is not None:
        return tuple(c["opening"]), "container"
    p = ctx.profile
    return (p.center[0], p.center[1], p.boundsMax[2]), "top"


def build(ctx):
    from engine.blender import vdb as VB
    from engine.physics import plume as PL
    from engine.physics.wind_calibration import perms
    p = ctx.params
    fmt = ctx.script["format"]
    fps, frames = fmt["fps"], int(round(fmt["durationS"] * fmt["fps"]))
    pt, how = source(ctx)
    w, h = float(p["widthM"]), float(p["heightM"])
    ob = VB.procedural_volume("valora_fx_steam", anchor=(pt[0], pt[1], pt[2] + 0.002), width_m=w, height_m=h,
                              frames=(1, frames), fps=fps, rise_ms=float(p["riseMs"]),
                              density=float(p["density"]) * DENSITY_PER_M * 0.04 / w, color=(0.95, 0.95, 0.95),
                              seed=int(ctx.seed), block="effect/steam", fade_frac=0.7)
    ob.visible_shadow = False
    wind = ctx.scene.get("valora_wind")
    lean = PL.wind_drift(dict(wind) if wind else None, perms(ctx.catalog, "effect", "steam"), 1.0)
    if lean != (0.0, 0.0):          # a steady lean, not a drift: steam is re-made at the source every instant
        ob.rotation_euler = (lean[1] * -0.4 / max(p["riseMs"], 0.1), lean[0] * 0.4 / max(p["riseMs"], 0.1), 0.0)
    ctx.scene["valora_fx_steam"] = {"source": list(pt), "from": how, "widthM": w, "heightM": h}
    return ob
