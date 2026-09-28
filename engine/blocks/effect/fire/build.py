"""fire (phase 6 Task 112, GS-06): the campfire from our own Mantaflow library (flame + smoke, 1.2 m native,
x scale within the x3 guard) plus a FLICKER LIGHT (LM-08: "fire without light change" is the failure mode).

Place: a marked fire / flame source (sim_facts.emitters, a marker only), else beside or behind the subject as the
first camera sees it, on the ground and clear of the bounds x 1.1 (engine/physics/plume.anchors). Time: started
inside the developed part of the sequence so it is burning at frame 1. The light: a warm point light (FLAME_RGB,
about 1800 K) at 0.25 x the flame height, its energy keyed per frame by engine/physics/plume.flicker (5-12 Hz
seeded sines plus noise, mean LIGHT_W x scale^2 x lightStrength). The library missing -> a procedural flame
volume of the same size. Stateless; the upload is never touched."""

LIGHT_W = 350.0                  # (eng, G9) mean point-light power for the 1.2 m campfire at scale 1
FLAME_RGB = (1.0, 0.5, 0.17)     # ~1800 K
DENSITY = 4.0                    # (eng, G9) smoke density x the grid (the campfire preset's smoke is thin)
FLAME_GAIN = 40.0                # (eng, G9) emission at flame 1 (25 read as dim sticks, 2026-09-28)


def place(ctx, width):
    from engine.physics import plume as PL
    from engine.physics.sim_facts import emitters
    import re
    fire_marks = [e for e in emitters(ctx.profile, ctx.script.get("markers") or [])
                  if e["source"].startswith("marker:")]
    marks = [m for m in (ctx.script.get("markers") or []) if re.search(r"\b(fire|flame|campfire|burn\w*)\b",
                                                                       str(m.get("text", "")), re.I)]
    if fire_marks and marks:
        return tuple(fire_marks[0]["point"]), "marker"
    prof = ctx.profile
    cam = ctx.camera_positions[0] if ctx.camera_positions else (prof.center[0], prof.center[1] - 4 * prof.longest, 0)
    placement = "side" if ctx.params["placement"] == "beside" else "behind"
    return PL.anchors(prof, cam, width, placement, 1, ctx.rng)[0], placement


def build(ctx):
    import bpy
    from engine.blender import vdb as VB
    from engine.physics import gas as G
    from engine.physics import plume as PL
    p, rng = ctx.params, ctx.rng
    fmt = ctx.script["format"]
    fps, frames = fmt["fps"], int(round(fmt["durationS"] * fmt["fps"]))
    seq = VB.library("campfire")
    size = G.PRESETS["campfire"]["size"]
    native = (seq or {}).get("native") or {"widthM": size[0], "sizeM": list(size)}
    k = float(p["scale"])
    width, height = float(native["widthM"]) * k, float(native.get("sizeM", size)[2]) * k
    anchor, how = place(ctx, width)
    mat = VB.volume_material("valora_fx_fire_mat", color=G.PRESETS["campfire"]["colour"],
                             density=float(p["smoke"]) * DENSITY / k, flame=True, flame_gain=FLAME_GAIN / k)
    if seq is not None:
        first, rt = PL.fit_play(len(seq["files"]), frames, G.retime(native.get("fps", G.LIBRARY_FPS), fps,
                                                                      p["timeScale"]), rng)
        ob = VB.place_vdb(seq, anchor=anchor, scale_m=width, start_frame=1, retime=rt, first_file=first,
                          rotate_deg=rng.uniform(0, 360), name="valora_fx_fire", block="effect/fire", material=mat)
    else:
        ob = VB.procedural_volume("valora_fx_fire", anchor=anchor, width_m=0.6 * width, height_m=height,
                                  frames=(1, frames), fps=fps, rise_ms=1.2, density=float(p["smoke"]) * 6.0 / k,
                                  color=(0.3, 0.3, 0.3), flame=True, seed=int(ctx.seed), block="effect/fire")
    light = None
    if p["lightStrength"] > 0:
        ld = bpy.data.lights.new("valora_fx_fire_light", "POINT")
        ld.color = FLAME_RGB
        ld.shadow_soft_size = 0.15 * width
        light = bpy.data.objects.new("valora_fx_fire_light", ld)
        ctx.scene.collection.objects.link(light)
        light.location = (anchor[0], anchor[1], anchor[2] + 0.25 * height)
        light["valora_block"] = "effect/fire:light"
        mean = LIGHT_W * k * k * float(p["lightStrength"])
        for f, m in enumerate(PL.flicker(frames + 1, fps, rng), start=1):
            ld.energy = mean * m
            ld.keyframe_insert("energy", frame=f)
    ctx.scene["valora_fx_fire"] = {"library": seq is not None, "anchor": list(anchor), "from": how,
                                   "widthM": width, "light": light is not None}
    return [o for o in (ob, light) if o is not None]
