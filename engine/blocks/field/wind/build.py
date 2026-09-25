"""The wind field (TAXONOMY WD-01; METHODS §2.9). Builds the shared node group `valora_wind`
(Position -> Wind, m/s) and records the params on the scene for Python consumers.

wind(p, t) = d * s * (1 + gustiness * g) + turbulence * s * h, where d is the unit direction, s the mean
speed, g in [-1, 1] a noise advected downwind at the mean speed (gust fronts travel with the air), and h a
horizontal turbulence vector in [-0.5, 0.5]^2. Its speed stays inside engine/physics/wind.envelope()
widened by turbulence * s. Time is Scene Time: no frame depends on the one before."""
from engine.physics import wind as W


def build(ctx):
    from engine.blender.gn import Tree
    p = ctx.params
    s, g, tb = p["speedMs"], p["gustiness"], p["turbulence"]
    dx, dy, _ = W.vector(p["directionDeg"], 1.0)
    ctx.scene["valora_wind"] = {"directionDeg": p["directionDeg"], "speedMs": s, "gustiness": g, "turbulence": tb}
    t = Tree("valora_wind", inputs=(("Position", "NodeSocketVector"),), outputs=(("Wind", "NodeSocketVector"),))
    pos, sec = t.input("Position"), t.time()
    d = t.vec(dx, dy, 0.0)
    offs = float(ctx.seed % 997)                                   # per-clip noise offset (METHODS R3)
    drift = t.vmath("SCALE", d, scale=t.math("MULTIPLY", sec, s))  # how far the air moved since t = 0
    q = t.vmath("SCALE", t.vmath("SUBTRACT", pos, drift), scale=1.0 / W.GUST_WAVELENGTH_M)
    fac, _ = t.noise(t.vmath("ADD", q, t.vec(offs, offs, 0.0)))
    gust = t.math("SUBTRACT", t.math("MULTIPLY", fac, 2.0), 1.0)               # [-1, 1]
    mean = t.vmath("SCALE", d, scale=t.math("MULTIPLY", s, t.math("ADD", 1.0, t.math("MULTIPLY", gust, g))))
    tq = t.vmath("SCALE", t.vmath("SUBTRACT", pos, drift), scale=1.0 / W.TURB_SCALE_M)
    _, col = t.noise(t.vmath("ADD", tq, t.vec(-offs, offs, 0.5)))
    hx, hy, _ = t.xyz(t.vmath("SUBTRACT", col, t.vec(0.5, 0.5, 0.5)))
    turb = t.vmath("SCALE", t.vec(hx, hy, 0.0), scale=tb * s)
    t.output("Wind", t.vmath("ADD", mean, turb))
    t.finish()
