"""embers (phase 6 Task 105, PT-09): glowing embers rising from a source and flickering. Stateless: every ember's
position is a function of Scene Time alone (engine/physics/particle_pack.ember_state, evaluated here as nodes with
seeded Random Value draws in place of the pure module's hash), so any frame renders anywhere and nothing is
baked. Each ember respawns every life seconds (2-5 s) at a seeded point of the source disc, rises at riseMs with a
sideways sway, flickers at 5-12 Hz and fades in and out over its life; it carries the analytic `velocity` (R7).
Source: the first emitter (a marker, or an emissive / exhaust detail point; engine/physics/sim_facts.emitters),
else a ground disc of spread x the subject's longest side around it. The upload is never touched."""
import math

EMBER_GAIN = 60.0     # (eng, G5) emission at full glow; the glow is Blackbody(EMBER_K) x flicker x fade
EMBER_K = (1050.0, 1450.0)
SWAY_FRAC = 0.15      # = engine/physics/particle_pack.ember_state sway / spread


def _material(bpy):
    m = bpy.data.materials.get("valora_ember") or bpy.data.materials.new("valora_ember")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    bb = nt.nodes.new("ShaderNodeBlackbody")
    k = nt.nodes.new("ShaderNodeAttribute")
    k.attribute_type, k.attribute_name = "GEOMETRY", "kelvin"
    g = nt.nodes.new("ShaderNodeAttribute")
    g.attribute_type, g.attribute_name = "GEOMETRY", "glow"
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = EMBER_GAIN
    nt.links.new(k.outputs["Fac"], bb.inputs["Temperature"])
    nt.links.new(bb.outputs[0], em.inputs["Color"])
    nt.links.new(g.outputs["Fac"], mul.inputs[0])
    nt.links.new(mul.outputs[0], em.inputs["Strength"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def _source(ctx):
    from engine.physics.sim_facts import emitters
    em = emitters(ctx.profile, ctx.script.get("markers") or [])
    spread = ctx.params["spread"] * ctx.profile.longest
    if em:
        return tuple(em[0]["point"]), 0.25 * spread
    return (ctx.profile.center[0], ctx.profile.center[1], 0.0), spread


def build(ctx):
    import bpy
    from engine.blender import weather_nodes as wn
    from engine.blender.gn import Tree, add_modifier
    from engine.physics import particle_pack as P
    p, seed = ctx.params, int(ctx.seed)
    base, spread = _source(ctx)
    n, rise = int(p["count"]), float(p["riseMs"])
    t = Tree("valora_fx_embers")
    pts = t.node("GeometryNodePoints")
    pts.inputs["Count"].default_value = n
    t.geometry = pts.outputs["Points"]
    idx = wn.index(t)
    rnd = lambda lo, hi, s, ident=None: wn.random(t, "FLOAT", lo, hi, seed + s, ident)  # noqa: E731
    sec = t.time()
    life = rnd(P.EMBER_LIFE_S[0], P.EMBER_LIFE_S[1], 1)
    tt = t.math("ADD", sec, t.math("MULTIPLY", life, rnd(0.0, 1.0, 2)))
    cyc = t.math("FLOOR", t.math("DIVIDE", tt, life))
    age = t.math("SUBTRACT", tt, t.math("MULTIPLY", cyc, life))
    frac = t.math("DIVIDE", age, life)
    id2 = t.math("ADD", t.math("MULTIPLY", idx, 7919.0), cyc)
    a = t.math("MULTIPLY", rnd(0.0, 1.0, 3, id2), 2 * math.pi)
    r = t.math("MULTIPLY", t.math("SQRT", rnd(0.0, 1.0, 4, id2)), spread)
    w = rnd(1.3, 2.3, 5)
    sway = SWAY_FRAC * spread
    wa = t.math("ADD", t.math("MULTIPLY", w, age), a)
    wb = t.math("ADD", t.math("MULTIPLY", t.math("MULTIPLY", w, 0.7), age), a)
    x = t.math("ADD", t.math("ADD", base[0], t.math("MULTIPLY", r, t.math("COSINE", a))), t.math("MULTIPLY", t.math("SINE", wa), sway))
    y = t.math("ADD", t.math("ADD", base[1], t.math("MULTIPLY", r, t.math("SINE", a))), t.math("MULTIPLY", t.math("COSINE", wb), sway))
    z = t.math("ADD", base[2], t.math("MULTIPLY", age, rise))
    t.set_position(t.vec(x, y, z))
    vx = t.math("MULTIPLY", t.math("COSINE", wa), sway * 1.0)
    vel = t.vec(t.math("MULTIPLY", vx, w), t.math("MULTIPLY", t.math("MULTIPLY", t.math("SINE", wb), -0.7 * sway), w), rise)
    t.store("velocity", vel, "FLOAT_VECTOR")
    hz = rnd(P.EMBER_FLICKER_HZ[0], P.EMBER_FLICKER_HZ[1], 6)
    flick = t.math("ADD", 0.6, t.math("MULTIPLY", 0.4, t.math("SINE", t.math("ADD", t.math("MULTIPLY", sec, t.math("MULTIPLY", hz, 2 * math.pi)), a))))
    fade = t.math("MULTIPLY", t.smoothstep(0.0, 0.1, frac), t.math("SUBTRACT", 1.0, t.smoothstep(0.6, 1.0, frac)))
    t.store("glow", t.math("MULTIPLY", flick, fade))
    t.store("kelvin", t.math("SUBTRACT", rnd(EMBER_K[0], EMBER_K[1], 7), t.math("MULTIPLY", frac, 250.0)))
    rad = t.node("GeometryNodeSetPointRadius")
    t.feed(rad.inputs["Points"], t.geometry)
    t.feed(rad.inputs["Radius"], t.math("MULTIPLY", rnd(P.EMBER_SIZE_M[0], P.EMBER_SIZE_M[1], 8), 0.5))
    t.geometry = rad.outputs["Points"]
    sm = t.node("GeometryNodeSetMaterial")
    t.feed(sm.inputs["Geometry"], t.geometry)
    sm.inputs["Material"].default_value = _material(bpy)
    t.geometry = sm.outputs["Geometry"]
    ng = t.finish()
    ob = bpy.data.objects.new("valora_fx_embers", bpy.data.pointclouds.new("valora_fx_embers"))
    ctx.scene.collection.objects.link(ob)
    ob["valora_block"] = "effect/embers"
    add_modifier(ob, ng, "valora_embers")
    ctx.scene["valora_fx_embers"] = {"count": n, "base": list(base), "spreadM": spread, "riseMs": rise}
    return ob
