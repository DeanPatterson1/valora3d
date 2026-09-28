"""tyre_smoke build (phase 6 Task 113, VD-10): the library's tyre_smoke_burst (tools/bake_vdb_library.py: a 6 x 4
x 2.5 m domain, two rear-tyre flows at library x = -0.8, y = +-0.8 blowing toward -x) played from the sim's start.

Fit (engine/physics/tyre_smoke.fit): the library's +x is turned onto the car's forward direction at startS (the
drive's own pose; nose sign from sim_facts), scaled so its tyre spacing matches the car's rear track (within the
x3 guard), and anchored so the library's axle midpoint lands on the car's rear-axle contact midpoint. The smoke
stays where the burnout began (it is air, not part of the car). The library missing -> a procedural low billow.
The stateless sim kind (bake.method none): ctx.bake is None."""


def build(ctx):
    from engine.blender import vdb as VB
    from engine.physics import gas as G
    from engine.physics import tyre_smoke as T
    p, s = ctx.params, ctx.script
    fps = s["format"]["fps"]
    frames = int(round(s["format"]["durationS"] * fps))
    ref = next(r for r in s.get("sims", []) if r["id"] == "tyre_smoke")
    start = int(round(ref["startS"] * fps)) + 1
    fit = T.fit(ctx.profile, s, ctx.catalog, ref["startS"])
    seq = VB.library("tyre_smoke_burst")
    mat = VB.volume_material("valora_sim_tyre_smoke_mat", color=G.PRESETS["tyre_smoke_burst"]["colour"],
                             density=float(p["density"]) * T.DENSITY / fit["scale"])
    if seq is not None:
        rt = G.retime(seq["native"].get("fps", G.LIBRARY_FPS), fps, p["timeScale"])
        ob = VB.place_vdb(seq, anchor=fit["anchor"], scale_m=fit["scale"] * seq["native"]["widthM"],
                          start_frame=start, retime=rt, rotate_deg=fit["yawDeg"], name="valora_sim_tyre_smoke",
                          block="sim/tyre_smoke", material=mat)
    else:
        a = fit["anchor"]
        ob = VB.procedural_volume("valora_sim_tyre_smoke", anchor=(a[0], a[1], 0.0), width_m=2.5 * fit["scale"],
                                  height_m=1.2 * fit["scale"], frames=(1, frames), fps=fps, rise_ms=0.2,
                                  density=float(p["density"]) * 2.0, color=(0.8, 0.8, 0.8), seed=int(ctx.seed),
                                  block="sim/tyre_smoke")
    ctx.scene["valora_sim_tyre_smoke"] = {"library": seq is not None, **{k: fit[k] for k in ("anchor", "yawDeg",
                                                                                              "scale")}}
    return ob
