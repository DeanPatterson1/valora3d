"""smoke_plume (phase 6 Task 112, GS-01 ambient): plumes from our own Mantaflow VDB library
(tools/bake_vdb_library.py; plume_soft 2 m, chimney_thin 0.6 m) placed behind / around / beside the subject as the
first camera sees it, on the ground and clear of the bounds x 1.1 (engine/physics/plume.anchors), at their
physical size x scale (the x3 guard), rotated and started per seed inside the sequence's developed part so the
plume is already rising at frame 1, retimed to the clip's fps x timeScale, and drifting downwind
(windCalibration). The library missing -> the procedural M-VOL plume of the same size (engine/blender/vdb.
procedural_volume). Stateless: nothing is baked by the clip. The upload is never touched."""


def build(ctx):
    from engine.blender import vdb as VB
    from engine.physics import gas as G
    from engine.physics import plume as PL
    from engine.physics.wind_calibration import perms
    p, prof, rng = ctx.params, ctx.profile, ctx.rng
    fmt = ctx.script["format"]
    fps, frames = fmt["fps"], int(round(fmt["durationS"] * fmt["fps"]))
    preset = p["preset"]
    seq = VB.library(preset)
    native = (seq or {}).get("native") or {"widthM": G.PRESETS[preset]["size"][0],
                                            "sizeM": list(G.PRESETS[preset]["size"])}
    width = float(native["widthM"]) * float(p["scale"])
    height = float(native.get("sizeM", G.PRESETS[preset]["size"])[2]) * float(p["scale"])
    cam = ctx.camera_positions[0] if ctx.camera_positions else (prof.center[0], prof.center[1] - 4 * prof.longest, 0)
    wind = ctx.scene.get("valora_wind")
    drift = PL.wind_drift(dict(wind) if wind else None, perms(ctx.catalog, "effect", "smoke_plume"), frames / fps)
    colour = G.PRESETS[preset]["colour"]
    obs = []
    for i, a in enumerate(PL.anchors(prof, cam, width, p["placement"], int(p["count"]), rng)):
        name = f"valora_fx_smoke_plume_{i}"
        if seq is not None:
            first, rt = PL.fit_play(len(seq["files"]), frames, G.retime(native.get("fps", G.LIBRARY_FPS), fps,
                                                                          p["timeScale"]), rng)
            mat = VB.volume_material(f"{name}_mat", color=colour, density=_density(p["density"], width))
            ob = VB.place_vdb(seq, anchor=a, scale_m=width, start_frame=1, retime=rt, first_file=first,
                              rotate_deg=rng.uniform(0, 360), name=name, block="effect/smoke_plume", material=mat)
        else:
            ob = VB.procedural_volume(name, anchor=a, width_m=width, height_m=height, frames=(1, frames), fps=fps,
                                      rise_ms=0.5 * p["timeScale"], density=_density(p["density"], width) * 0.6,
                                      color=colour, seed=int(ctx.seed) + i, block="effect/smoke_plume")
        if drift != (0.0, 0.0):
            VB.key_drift(ob, (1, frames), drift)
        obs.append(ob)
    ctx.scene["valora_fx_smoke_plume"] = {"preset": preset, "library": seq is not None, "widthM": width,
                                          "count": len(obs), "driftM": list(drift)}
    return obs


DENSITY_PER_M = 3.0     # (eng, G9): Principled Volume density x the grid, per metre of plume width, at density 1


def _density(d, width):
    """Optical depth stays the same whatever the plume's size: density scales with 1 / width."""
    return d * DENSITY_PER_M * 2.0 / max(width, 0.1)
