"""ground_fog: a low scattering layer (port of render-studio rain_look.distance_fog, generalised; the maths
and its (eng) numbers live in engine/physics/fog.py).

One box volume, sized from the subject and the cameras. The density is built in the shader, so there is no
mesh Boolean and nothing to bake (METHODS R1): ground sigma x exp(-z/h), times a clear pocket around the
subject (0 inside POCKET x r) that rides the subject's shared pose (review chunk 2 #6: the pocket anchor is
parented to the engine's motion rig, so a slide or drive carries its clear air along while height, the
boundary fades and the wind coordinates stay fixed in world space), times fades to zero at the box's top and side faces (the box edge never
shows), times drifting wisps advected by the one wind field (valora_wind, perMs from the manifest)."""
import math

TINTS = {"neutral": (0.80, 0.85, 0.90, 1.0),          # render-studio's fog colour
         "warm": (0.92, 0.86, 0.78, 1.0), "cool": (0.74, 0.83, 0.95, 1.0)}
DRIFT_DEPTH = 0.45    # density varies +/-45 % in drifting wisps when there is wind (eng)
WISP_K = 4.0          # wisp size = max(1.5 r, WISP_K x heightM) (eng)


def _math(nt, op, a, b=None, name=None):
    m = nt.nodes.new("ShaderNodeMath")
    m.operation = op
    if name:
        m.name = name
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            m.inputs[i].default_value = float(v)
        else:
            nt.links.new(v, m.inputs[i])
    return m.outputs[0]


def _smooth(nt, value, a, b, lo, hi, name=None):
    m = nt.nodes.new("ShaderNodeMapRange")
    m.interpolation_type = "SMOOTHSTEP"
    m.clamp = True
    if name:
        m.name = name
    m.inputs["From Min"].default_value, m.inputs["From Max"].default_value = a, b
    m.inputs["To Min"].default_value, m.inputs["To Max"].default_value = lo, hi
    nt.links.new(value, m.inputs["Value"])
    return m.outputs["Result"]


def _drift(ctx, nt, density, coords, height_m):
    """Multiply density by noise advected downwind; the mapping's Location is keyed linearly over the clip
    (a shader has no clock), so frame N depends on time alone."""
    from engine.physics import wind as W
    from engine.physics.wind_calibration import perms
    w = ctx.scene.get("valora_wind")
    if w is None or W.is_calm(w["speedMs"]):
        return density
    fps, n = ctx.script["format"]["fps"], ctx.scene.frame_end
    dx, dy, _ = W.vector(w["directionDeg"], w["speedMs"] * perms(ctx.catalog, "effect", "ground_fog"))
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.name = "valora_fog_drift"
    nt.links.new(coords, mp.inputs["Vector"])
    for f, k in ((1, 0.0), (n, (n - 1) / fps)):
        mp.inputs["Location"].default_value = (-dx * k, -dy * k, 0.0)
        mp.inputs["Location"].keyframe_insert("default_value", frame=f)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.0 / max(1.5 * ctx.profile.radius, WISP_K * height_m)
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    wisps = _smooth(nt, noise.outputs["Factor"], 0.0, 1.0, 1.0 - DRIFT_DEPTH, 1.0 + DRIFT_DEPTH)
    from engine.blender.realism_rig import fcurves
    for c in fcurves(nt.animation_data.action):
        for kp in c.keyframe_points:
            kp.interpolation = "LINEAR"
    ctx.scene["valora_fog_drift"] = True
    return _math(nt, "MULTIPLY", density, wisps)


def build(ctx):
    import bpy
    from engine.physics import fog as F
    p, prof = ctx.params, ctx.profile
    h, dens = F.mode_params(p["mode"], p["heightM"], p["density"])
    cx, cy, cz = prof.center
    far = max((math.dist(q, prof.center) for q in ctx.camera_positions), default=4.0 * prof.radius)
    half = 0.5 * F.domain_width(prof.longest, far)
    top = F.domain_height(h)
    pocket = F.pocket_radius(prof.radius)

    lo, hi = (cx - half, cy - half, 0.0), (cx + half, cy + half, top)
    me = bpy.data.meshes.new("valora_fog")
    v = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    ob = bpy.data.objects.new("valora_fog", me)
    ob["valora_block"] = "effect/ground_fog"
    ctx.scene.collection.objects.link(ob)
    ob.visible_shadow = False

    anchor = bpy.data.objects.new("valora_fog_centre", None)   # at the subject centre: coords are metres from it
    anchor["valora_block"] = "effect/ground_fog"
    ctx.scene.collection.objects.link(anchor)
    anchor.location = (cx, cy, cz)

    from engine.blender.realism_rig import rig
    # The pocket follows the subject: an empty under the rig's offset empty (motion -> offset -> subject root),
    # at the subject centre in rig space. Object coords of it are metres from the moving centre; rotation does
    # not matter, the pocket is a length. The rig is found by the engine's own object, never by a name an
    # upload could claim (build_rig refuses a taken name).
    follow = rig()[1]
    pocket_anchor = bpy.data.objects.new("valora_fog_pocket", None)
    pocket_anchor["valora_block"] = "effect/ground_fog"
    ctx.scene.collection.objects.link(pocket_anchor)
    pocket_anchor.parent = follow
    # identity parent inverse, exactly like the subject root under the same empty: rig space = rest world space
    pocket_anchor.location = (cx, cy, cz)

    mat = bpy.data.materials.new("valora_fog")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = TINTS[p["tint"]]
    vol.inputs["Anisotropy"].default_value = F.ANISOTROPY
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.object = anchor
    coords = tc.outputs["Object"]
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coords, sep.inputs[0])
    z = _math(nt, "ADD", sep.outputs["Z"], cz)                   # height above the ground (z = 0)
    ptc = nt.nodes.new("ShaderNodeTexCoord")
    ptc.name = "valora_fog_pocket_coords"
    ptc.object = pocket_anchor
    radial = nt.nodes.new("ShaderNodeVectorMath")
    radial.operation = "LENGTH"
    nt.links.new(ptc.outputs["Object"], radial.inputs[0])

    base = _math(nt, "EXPONENT", _math(nt, "MULTIPLY", z, -1.0 / h))          # exp(-z/h)
    density = _math(nt, "MULTIPLY", base, dens * F.FOG_SIGMA, name="valora_fog_sigma")
    density = _math(nt, "MULTIPLY", density, _smooth(nt, z, 0.6 * top, top, 1.0, 0.0))        # top fade
    xy = nt.nodes.new("ShaderNodeVectorMath")
    xy.operation = "MULTIPLY"
    xy.inputs[1].default_value = (1.0, 1.0, 0.0)
    nt.links.new(coords, xy.inputs[0])
    xy_len = nt.nodes.new("ShaderNodeVectorMath")
    xy_len.operation = "LENGTH"
    nt.links.new(xy.outputs["Vector"], xy_len.inputs[0])
    density = _math(nt, "MULTIPLY", density,
                    _smooth(nt, xy_len.outputs["Value"], F.EDGE_FADE * half, half, 1.0, 0.0))  # side fade
    density = _math(nt, "MULTIPLY", density,
                    _smooth(nt, radial.outputs["Value"], pocket, 2.0 * pocket, 0.0, 1.0, name="valora_fog_pocket"))
    density = _drift(ctx, nt, density, coords, h)
    nt.links.new(density, vol.inputs["Density"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    me.materials.append(mat)
    ctx.scene["valora_fog"] = {"mode": p["mode"], "heightM": h, "density": dens, "sigma0": dens * F.FOG_SIGMA,
                               "pocketRadiusM": pocket, "domainMin": list(lo), "domainMax": list(hi),
                               "centre": [cx, cy, cz], "pocketAnchor": pocket_anchor.name,
                               "pocketParent": follow.name}
    return ob
