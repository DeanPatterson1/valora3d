"""Haze: a scattering volume whose density is expressed per metre, normalised to the set's scale.

Units. extinction sigma [1/m] = density * HAZE_K / r, with r the subject's bounding radius. So
HAZE_K is the optical depth per subject radius at density 1, and a miniature set gets the same
look as a full-size one (a 7 cm toy set is hazed like a car studio, not with real 7 cm of air).
For a car (r ~ 2.6 m) density 1 is sigma = HAZE_K / 2.6 per metre; see HAZE_K for the numbers.

Shape. The density is the full value around the camera path, zero inside a clear pocket around
the subject (1-2 r, keeps it crisp) and fades smoothly to zero between FADE_IN and FADE_OUT times
the farthest camera distance. The box that carries the volume encloses the whole fade sphere, so
no ray ever meets a box face where the density is not already zero: the domain has no visible
edge, even where a camera sees past the backdrop into the world (reverse angles on a cyc)."""
import math

# Optical depth per subject radius at density 1 (eng). Calibrated 2026-09-24 on toycar/script_t3,
# hero frame 256, black cyc + reflection_rig + premium_dark, 180x320 preview renders; frame mean
# (8-bit): haze off 85.9 | K 0.003: 89.4 | 0.005: 94.6 (+10%) | 0.008: 101.8 | 0.02: 121.8 |
# 0.4 (the old value): 200.8. Density 0.8 at 0.005 = 121.8 (+42%, heavy but not a fog-out).
# Haze glows in proportion to the key lights, so on a black set it must be optically thin: at car
# scale (r ~ 2.6 m) density 1 is sigma ~0.002 /m. Uncalibrated for white/grey cycs, softbox rigs
# and other grades (test band: engine/tests/test_compile_blender.py test_haze_is_subtle...).
HAZE_K = 0.005
POCKET = (1.0, 2.0)   # clear pocket: zero density inside 1 r, full from 2 r (x subject radius)
FADE_IN = 1.1         # full density out to 1.1 x the farthest camera ...
FADE_OUT = 3.0        # ... fading smoothly to zero at 3 x (the backdrop wall is usually in the fade)
TINTS = {"neutral": (1.0, 1.0, 1.0, 1.0), "warm": (1.0, 0.93, 0.85, 1.0), "cool": (0.86, 0.93, 1.0, 1.0)}


DRIFT_DEPTH = 0.35   # density varies +/-35% in drifting wisps when there is wind (eng)
DRIFT_SCALE = 1.5    # wisp size, x the subject radius (eng)


def _drift(ctx, nt, density, centre_ob):
    """Multiply density by a noise advected downwind. Shaders have no clock, so the noise mapping's
    Location is keyed linearly over the clip (stateless per frame)."""
    from engine.physics import wind as W
    w = ctx.scene.get("valora_wind")
    if w is None or W.is_calm(w["speedMs"]):
        return density
    r = ctx.profile.radius
    fps, n = ctx.script["format"]["fps"], ctx.scene.frame_end
    from engine.physics.wind_calibration import perms
    dx, dy, _ = W.vector(w["directionDeg"], w["speedMs"] * perms(ctx.catalog, "effect", "haze_volume"))
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.object = centre_ob
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.name = "valora_haze_drift"
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    for f, k in ((1, 0.0), (n, (n - 1) / fps)):
        mp.inputs["Location"].default_value = (-dx * k, -dy * k, 0.0)
        mp.inputs["Location"].keyframe_insert("default_value", frame=f)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.0 / (DRIFT_SCALE * r)
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    mod = nt.nodes.new("ShaderNodeMapRange")
    mod.inputs["To Min"].default_value, mod.inputs["To Max"].default_value = 1.0 - DRIFT_DEPTH, 1.0 + DRIFT_DEPTH
    nt.links.new(noise.outputs["Factor"], mod.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nt.links.new(density, mul.inputs[0])
    nt.links.new(mod.outputs["Result"], mul.inputs[1])
    ctx.scene["valora_haze_drift"] = True
    from engine.blender.realism_rig import fcurves
    for c in fcurves(nt.animation_data.action):     # constant drift speed: linear keys
        for kp in c.keyframe_points:
            kp.interpolation = "LINEAR"
    return mul.outputs[0]


def sigma_per_m(density, radius):
    return density * HAZE_K / radius


def _fade(ctx):
    """(centre, full-density radius, zero-density radius) of the haze sphere, placed coordinates."""
    c = ctx.profile.center
    far = max((math.dist(q, c) for q in ctx.camera_positions), default=4.0 * ctx.profile.radius)
    return tuple(c), FADE_IN * far, FADE_OUT * far


def _box(centre, r_zero):
    """Cube just outside the fade sphere: every face sits where the density is already zero."""
    half = 1.02 * r_zero
    return [c - half for c in centre], [c + half for c in centre]


def _map(nt, value, a, b, lo, hi):
    m = nt.nodes.new("ShaderNodeMapRange")
    m.interpolation_type = "SMOOTHSTEP"
    m.clamp = True
    m.inputs["From Min"].default_value, m.inputs["From Max"].default_value = a, b
    m.inputs["To Min"].default_value, m.inputs["To Max"].default_value = lo, hi
    nt.links.new(value, m.inputs["Value"])
    return m.outputs["Result"]


def build(ctx):
    import bpy
    p, prof = ctx.params, ctx.profile
    r = prof.radius
    centre, r_full, r_zero = _fade(ctx)
    lo, hi = _box(centre, r_zero)
    me = bpy.data.meshes.new("valora_haze")
    v = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    ob = bpy.data.objects.new("valora_haze", me)
    ctx.scene.collection.objects.link(ob)
    mat = bpy.data.materials.new("valora_haze")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = TINTS[p["tint"]]
    vol.inputs["Anisotropy"].default_value = p["anisotropy"]
    centre_ob = bpy.data.objects.new("valora_haze_centre", None)
    ctx.scene.collection.objects.link(centre_ob)
    centre_ob.location = centre
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.object = centre_ob
    length = nt.nodes.new("ShaderNodeVectorMath")
    length.operation = "LENGTH"
    nt.links.new(tc.outputs["Object"], length.inputs[0])
    dist = length.outputs["Value"]
    density = _map(nt, dist, r_full, r_zero, sigma_per_m(p["density"], r), 0.0)
    if p["clearPocket"]:
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        nt.links.new(density, mul.inputs[0])
        nt.links.new(_map(nt, dist, POCKET[0] * r, POCKET[1] * r, 0.0, 1.0), mul.inputs[1])
        density = mul.outputs[0]
    density = _drift(ctx, nt, density, centre_ob)
    nt.links.new(density, vol.inputs["Density"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    me.materials.append(mat)
    ob.visible_shadow = False
    ctx.scene["valora_haze_domain"] = [lo, hi]
    ctx.scene["valora_haze_fade"] = [*centre, r_full, r_zero]
