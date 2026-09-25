"""golden_field: an open field under a low sun (phase 5 Task 71). Procedural, CC0 by construction.

The layout is pure (engine/worlds/field_layout.py); this file realises it:
- the ground (valora_ground, groundType grass): a field-coloured noise surface with bump, which is the grass
  beyond the real blades; an optional dirt track (also valora_ground);
- the blades, realised as mesh islands in one valora_foliage object (hand-off H6): every blade its own island,
  valora_sway 0 at the root rising to 1 at the tip, valora_sway_len its length, so ground_conform and
  foliage_sway apply automatically; wildflowers carry a flower head on the same island;
- a far treeline/hill silhouette ring at the field's edge (no shadows);
- the sky: a physical sky with its sun where the world's SUN light is; overcast mixes it toward cloud grey;
- ONE `SUN` light (tagged valora_world_sun). Its azimuth is sunAzimuthDeg around the subject, measured from
  the hero camera's view direction (0 = behind the subject: a rim); its elevation, colour and softness come
  from timeOfDay (CATALOG-GAPS rank 7: 2-15 degrees). hard_sun (Task 72) takes this sun over instead of
  adding a second one. The upload's materials are never touched (spec §4.5)."""
import math

BLOCK = "world/golden_field"
# timeOfDay -> sun elevation deg, colour K, strength W/m^2, angular diameter deg, sky strength   (all eng)
SUN = {"dawn": (5.0, 3500.0, 2.5, 1.5, 0.55), "golden": (8.0, 3200.0, 3.5, 1.5, 0.75),
       "dusk": (3.0, 2800.0, 1.6, 1.5, 0.35), "overcast": (35.0, 6000.0, 0.8, 25.0, 1.0)}
BLADE_W = {"grass": 0.012, "wheat": 0.008, "wildflowers": 0.010}    # (eng) blade base width, real size
BLADE_RGB = {"grass": (0.060, 0.115, 0.028), "wheat": (0.46, 0.34, 0.12), "wildflowers": (0.070, 0.120, 0.030)}
GROUND_RGB = {"grass": ((0.035, 0.060, 0.016), (0.10, 0.12, 0.035)), "wheat": ((0.20, 0.14, 0.05), (0.42, 0.31, 0.11)),
              "wildflowers": ((0.035, 0.060, 0.016), (0.10, 0.12, 0.035))}      # (eng) ground noise ramp
FLOWER_RGB = ((0.60, 0.08, 0.10), (0.85, 0.70, 0.10), (0.55, 0.45, 0.80))        # (eng) poppy, buttercup, cornflower
FLOWER_M = 0.018            # (eng) flower head size, real
DIRT_RGB = (0.11, 0.075, 0.045)
SILHOUETTE_RGB = (0.018, 0.025, 0.012)


def _sun_vector(ctx, azimuth_deg, elevation_deg):
    """Unit vector from the subject toward the sun."""
    cx, cy, _ = ctx.profile.center
    hero = ctx.hero_pose
    if hero is not None:
        fx, fy = cx - hero.position[0], cy - hero.position[1]
    else:
        fx, fy = 0.0, 1.0
    n = math.hypot(fx, fy) or 1.0
    base = math.atan2(fy / n, fx / n) + math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    return (math.cos(el) * math.cos(base), math.cos(el) * math.sin(base), math.sin(el))


def _sky(bpy, ctx, tod, sun_dir):
    from engine.blender.set_parts import nishita
    el, _, _, _, strength = SUN[tod]
    w = bpy.data.worlds.new("valora_field_sky")
    w.use_nodes = True
    nt = w.node_tree
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    # Blender's sky: sun_rotation is the sun's angle about Z measured from +Y toward -X (counter-clockwise from
    # the Y axis as seen from above); atan2(-x, y) maps our vector onto it.
    rot = math.degrees(math.atan2(-sun_dir[0], sun_dir[1]))
    # below the horizon the sky shows its horizon colour (a physical sky is dark blue down there, which a high
    # orbit sees past the silhouette ring as a band of "sea")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    up = nt.nodes.new("ShaderNodeMath")
    up.operation = "MAXIMUM"
    up.inputs[1].default_value = 0.0
    nt.links.new(sep.outputs["Z"], up.inputs[0])
    vec = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(sep.outputs["X"], vec.inputs["X"])
    nt.links.new(sep.outputs["Y"], vec.inputs["Y"])
    nt.links.new(up.outputs[0], vec.inputs["Z"])
    sky = nishita(nt, vec.outputs["Vector"], el, rot, dust=3.0 if tod != "overcast" else 6.0)
    colour = sky.outputs["Color"]
    if tod == "overcast":
        grey = nt.nodes.new("ShaderNodeMix")
        grey.data_type = "RGBA"
        grey.inputs["Factor"].default_value = 0.6
        nt.links.new(colour, grey.inputs[6])
        grey.inputs[7].default_value = (0.45, 0.47, 0.50, 1.0)
        colour = grey.outputs[2]
    nt.links.new(colour, bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    ctx.scene.world = w
    return rot


def _ground_mat(bpy, name, crop):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    sh = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 10.0
    nt.links.new(geo.outputs["Position"], noise.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    lo, hi = GROUND_RGB[crop]
    ramp.color_ramp.elements[0].color = (*lo, 1.0)
    ramp.color_ramp.elements[1].color = (*hi, 1.0)
    nt.links.new(noise.outputs["Fac"], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], sh.inputs["Base Color"])
    sh.inputs["Roughness"].default_value = 0.85
    bump = nt.nodes.new("ShaderNodeBump")                  # the far grass: a displaced texture, not blades
    bump.inputs["Distance"].default_value = 0.02
    bump.inputs["Strength"].default_value = 0.6
    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 60.0
    nt.links.new(geo.outputs["Position"], fine.inputs["Vector"])
    nt.links.new(fine.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], sh.inputs["Normal"])
    return m


def _blades(bpy, ctx, lay, crop):
    """One joined foliage mesh: a triangle per blade (its own island), a flower triangle sharing the tip."""
    import numpy as np
    from engine.blender import set_parts as P
    from engine.blender.realism_rig import SWAY, SWAY_LEN, write_attr
    bl = lay["blades"]
    if not bl:
        return None, 0
    w = BLADE_W[crop]
    verts, faces, sway, length, mat_idx = [], [], [], [], []
    for x, y, yaw, h, lean, flower, pick in bl:
        a = math.radians(yaw)
        dx, dy = math.cos(a), math.sin(a)
        px, py = -dy * w / 2, dx * w / 2
        k = len(verts)
        tip = (x + lean * h * dx, y + lean * h * dy, h)
        verts += [(x - px, y - py, 0.0), (x + px, y + py, 0.0), tip]
        faces.append((k, k + 1, k + 2))
        sway += [0.0, 0.0, 1.0]
        length += [h, h, h]
        mat_idx.append(0)
        if flower:
            f = FLOWER_M
            verts += [(tip[0] + f * dx - f * dy, tip[1] + f * dy + f * dx, h + 0.3 * f),
                      (tip[0] + f * dx + f * dy, tip[1] + f * dy - f * dx, h + 0.3 * f)]
            faces.append((k + 2, k + 3, k + 4))
            sway += [1.0, 1.0]
            length += [h, h]
            mat_idx.append(1 + int(pick * len(FLOWER_RGB)) % len(FLOWER_RGB))
    mats = [P.mat(f"valora_field_{crop}", BLADE_RGB[crop], 0.55)]
    if crop == "wildflowers":
        mats += [P.mat(f"valora_field_flower_{i}", c, 0.5) for i, c in enumerate(FLOWER_RGB)]
    ob = P.mesh(ctx.scene, "valora_field_blades", BLOCK, verts, faces, mats, mat_idx if len(mats) > 1 else None)
    P.tag(ob, BLOCK, foliage=True)
    write_attr(ob, SWAY, np.asarray(sway), "FLOAT")
    write_attr(ob, SWAY_LEN, np.asarray(length), "FLOAT")
    return ob, max(sway[i] for f in faces for i in f[:2])      # every root (a face's first two corners) is 0


def build(ctx):
    import bpy
    from engine.blender import set_parts as P
    from engine.color import kelvin_to_rgb
    from engine.worlds.field_layout import layout
    p, prof = ctx.params, ctx.profile
    tod, crop = p["timeOfDay"], p["crop"]
    lay = layout(prof, ctx.seed, float(p["grassHeightM"]), crop, bool(p["track"]),
                 cameras=[tuple(c) for c in ctx.camera_positions])
    el, kelvin, strength, angle, _ = SUN[tod]
    sun_dir = _sun_vector(ctx, float(p["sunAzimuthDeg"]), el)
    sky_rot = _sky(bpy, ctx, tod, sun_dir)

    cx, cy = lay["centre"]
    e = lay["extent"] / 2
    ground = P.mesh(ctx.scene, "valora_field_ground", BLOCK,
                    [(cx - e, cy - e, 0.0), (cx + e, cy - e, 0.0), (cx + e, cy + e, 0.0), (cx - e, cy + e, 0.0)],
                    [(0, 1, 2, 3)], [_ground_mat(bpy, "valora_field_ground", crop)])
    P.tag(ground, BLOCK, ground=True)
    track = None
    if lay["track"]:
        x0, y0, x1, y1 = lay["track"]
        track = P.mesh(ctx.scene, "valora_field_track", BLOCK,
                       [(x0, y0, 0.001), (x1, y0, 0.001), (x1, y1, 0.001), (x0, y1, 0.001)], [(0, 1, 2, 3)],
                       [P.mat("valora_field_dirt", DIRT_RGB, 0.9)])
        P.tag(track, BLOCK, ground=True)

    blades, root_sway = _blades(bpy, ctx, lay, crop)

    r = lay["extent"] / 2 * 0.98                                # the silhouette ring at the field's edge
    n = len(lay["horizon"])
    v, f = [], []
    for i, hgt in enumerate(lay["horizon"]):
        a0, a1 = math.tau * i / n, math.tau * (i + 1) / n
        h0, h1 = hgt * r, lay["horizon"][(i + 1) % n] * r
        P.quad(v, f, [(cx + r * math.cos(a0), cy + r * math.sin(a0), -0.5), (cx + r * math.cos(a1), cy + r * math.sin(a1), -0.5),
                      (cx + r * math.cos(a1), cy + r * math.sin(a1), h1), (cx + r * math.cos(a0), cy + r * math.sin(a0), h0)])
    horizon = P.mesh(ctx.scene, "valora_field_horizon", BLOCK, v, f, [P.mat("valora_field_horizon", SILHOUETTE_RGB, 0.95)])
    horizon.visible_shadow = False

    ld = bpy.data.lights.new("valora_field_sun", "SUN")
    ld.energy, ld.color, ld.angle = strength, kelvin_to_rgb(kelvin), math.radians(angle)
    sun = bpy.data.objects.new("valora_field_sun", ld)
    ctx.scene.collection.objects.link(sun)
    from mathutils import Vector
    sun.rotation_euler = Vector([-c for c in sun_dir]).to_track_quat("-Z", "Y").to_euler()   # shines along -Z
    P.tag(sun, BLOCK)
    sun["valora_world_sun"] = True

    ctx.scene["valora_field"] = {
        "timeOfDay": tod, "crop": crop, "extent": lay["extent"], "bladeRadius": lay["bladeRadius"],
        "blades": len(lay["blades"]), "bladeRootSwayMax": float(root_sway), "track": lay["track"] is not None,
        "clearing": dict(lay["clearing"]), "sun": {"elevationDeg": el, "azimuthDeg": float(p["sunAzimuthDeg"]),
                                                   "kelvin": kelvin, "strength": strength, "angleDeg": angle,
                                                   "direction": list(sun_dir), "skyRotationDeg": sky_rot},
        "sunObject": sun.name, "sightCut": lay["sightCut"]}
    return ground
