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
  adding a second one. The upload's materials are never touched (spec §4.5).

Art pass (2026-09-25, the rain courtyard's recipe): with the pinned CC0 library the sky is a real golden-hour
HDRI rotated so its sun sits on the SUN light's azimuth; the ground is scanned withered grass with leafy
patches, running on as a far meadow that dissolves into the photo's own horizon (aerial haze sampled from
the HDRI just above the horizon); photoscanned tufts (grass_medium_02 with its dry variant, grass_medium_01)
join a thinned set of blades in the ONE swaying foliage mesh, varied per tuft and glowing when backlit;
static instanced tufts carry a trampled cover under the blades and the field out to the horizon (the
layout's sight cut applies to them too); short treelines of real trees (tree_small_02), the first behind
the subject as the hero sees it, fade into the haze by distance. With an empty library every piece falls
back to the procedural field above."""
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
DIRT_TILE_M = 4.0            # dry_ground_01 is a 4 m scan
SILHOUETTE_RGB = (0.018, 0.025, 0.012)
# art pass (all eng). timeOfDay -> the pinned HDRI, its tint and strength; the photo's sun azimuth (deg, atan2
# of the brightest region's direction, measured 2026-09-25 with a luminance centroid over the 4k files)
HDRI = {"golden": ("magalies_field_sunset_4k", (1.0, 0.94, 0.84), 0.8),
        "dusk": ("plains_sunset_4k", (1.0, 0.86, 0.74), 0.35), "dawn": ("plains_sunset_4k", (0.86, 0.9, 1.0), 0.45),
        "overcast": ("kloppenheim_01_4k", (1.0, 1.0, 1.0), 2.0)}
HDRI_SUN_AZ = {"magalies_field_sunset_4k": 143.77, "plains_sunset_4k": 142.98, "kloppenheim_01_4k": 144.31}
FAR_M = 1200.0               # the far meadow plane: the photo's own ground is never projected (these HDRIs
                             # stand in tall grass: its near-horizon band is stalks, which smear when projected)
GROUND_TILE_M = 2.0          # withered_grass / leafy_grass tile (dry_ground_01 for the track)
GREEN_SHARE = {"golden": 0.22, "dusk": 0.22, "dawn": 0.35, "overcast": 0.6}    # leafy_grass patches
GROUND_TINT = {"grass": (0.42, 0.33, 0.19), "wheat": (0.5, 0.4, 0.22),
               "wildflowers": (0.38, 0.34, 0.18)}                  # dark: the gaps between tufts read as shade
MACRO_M = 9.0                # large-scale brightness patches across the meadow (breaks the tile repeat)
HAZE = {"golden": (0.95, 0.66, 0.40), "dusk": (0.55, 0.36, 0.28), "dawn": (0.62, 0.62, 0.70),
        "overcast": (0.55, 0.58, 0.60)}            # aerial-perspective colour (x HDRI strength)
HAZE_HALF_M = 350.0          # distance at which the meadow / a tree is half haze (toward a low sun the horizon
                             # is many times brighter than the lit ground: a short half-distance fogs it out)
TINY_EVERY = 2               # one trampled / cleared blade in TINY_EVERY roots a tiny tuft (ground cover)
TINY_VERT_CAP = 400_000
TRANSLUCENT = 0.3            # share of translucent (backlit glow) in the grass
BLADE_KEEP = 3               # with the library, one procedural blade in BLADE_KEEP stays (fine fill under tufts)
TUFT_EVERY = 4               # one blade in TUFT_EVERY is a candidate tuft root
TUFT_VERT_CAP = 1_600_000    # the foliage probe walks every edge: keep the joined mesh bounded
TUFT_VERTS = 400             # every tuft is collapsed to about this many vertices
TUFT_CONE_DEG = 38.0         # tufts go first where a camera looks (within this of its line to the subject)
TUFT_MIN_H = 0.05            # blades shorter than this (the clearing, a sight cut) never root a tuft
DRY_SHARE = {"golden": 0.72, "dusk": 0.72, "dawn": 0.55, "overcast": 0.45}   # mean tint toward the dry texture
BLADE_ROOT = {"grass": (0.05, 0.075, 0.02), "wheat": (0.30, 0.22, 0.08), "wildflowers": (0.05, 0.08, 0.02)}
BLADE_TIP = {"grass": (0.52, 0.42, 0.18), "wheat": (0.78, 0.60, 0.28), "wildflowers": (0.30, 0.34, 0.12)}


def _sun_vector(ctx, azimuth_deg, elevation_deg):
    """Unit vector from the subject toward the sun."""
    cx, cy, _ = ctx.profile.center
    hero = ctx.hero_pose
    from engine.lighting.rigs import sun_vector
    if hero is None:
        return sun_vector(ctx.profile, (cx, cy - 1.0, 0.0), azimuth_deg, elevation_deg)
    return sun_vector(ctx.profile, hero.position, azimuth_deg, elevation_deg)   # 0 = behind, +90 = camera right


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


def _photo_ground(bpy, dry, green, crop, tod):
    """withered_grass (matted, sun-dried) broken up by large leafy_grass patches, tinted to the crop."""
    from engine.blender.env_assets import pbr
    m = pbr("valora_field_ground", dry, GROUND_TILE_M, tint=GROUND_TINT[crop], rough_k=1.0, bump_k=1.0,
            rough_min=0.9, specular=0.2)
    nt = m.node_tree
    sh = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    base = next(l for l in nt.links if l.to_socket == sh.inputs["Base Color"]).from_socket
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    macro = nt.nodes.new("ShaderNodeTexNoise")                 # metre-scale light / dark patches
    macro.inputs["Scale"].default_value = 1.0 / MACRO_M
    macro.inputs["Detail"].default_value = 4.0
    nt.links.new(geo.outputs["Position"], macro.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 0.65, 1.3
    nt.links.new(macro.outputs["Fac"], mr.inputs["Value"])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    for ax in ("X", "Y", "Z"):
        nt.links.new(mr.outputs["Result"], comb.inputs[ax])
    mm = nt.nodes.new("ShaderNodeMix")
    mm.data_type, mm.blend_type = "RGBA", "MULTIPLY"
    mm.inputs["Factor"].default_value = 1.0
    nt.links.new(base, mm.inputs[6])
    nt.links.new(comb.outputs[0], mm.inputs[7])
    base = mm.outputs[2]
    nt.links.new(base, sh.inputs["Base Color"])
    if not all(green.values()):
        return m
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    sc.inputs["Scale"].default_value = 1.0 / (GROUND_TILE_M * 1.37)
    nt.links.new(geo.outputs["Position"], sc.inputs[0])
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(str(green["diff"]), check_existing=True)
    nt.links.new(sc.outputs["Vector"], t.inputs["Vector"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.25
    noise.inputs["Detail"].default_value = 5.0
    nt.links.new(geo.outputs["Position"], noise.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeMapRange")
    g = GREEN_SHARE[tod]
    ramp.inputs["From Min"].default_value = 0.62 - 0.25 * g
    ramp.inputs["From Max"].default_value = 0.70 - 0.25 * g
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(ramp.outputs["Result"], mix.inputs["Factor"])
    nt.links.new(base, mix.inputs[6])
    nt.links.new(t.outputs["Color"], mix.inputs[7])
    nt.links.new(mix.outputs[2], sh.inputs["Base Color"])
    return m


def _blade_arrays(lay, crop):
    """The procedural blades as flat arrays: each blade a tapered, bending strip (root pair, mid pair, tip: a
    quad and a triangle, its own island); a flower triangle shares the tip. Material slot 0 is the blade,
    1.. the flowers."""
    import numpy as np
    w = BLADE_W[crop]
    co, lv, ps, u, ln, pm, tint = [], [], [], [], [], [], []
    for x, y, yaw, h, lean, flower, pick in lay["blades"]:
        a = math.radians(yaw)
        dx, dy = math.cos(a), math.sin(a)
        px, py = -dy * w / 2, dx * w / 2
        k = len(co)
        mid = (x + 0.3 * lean * h * dx, y + 0.3 * lean * h * dy, 0.55 * h)      # the bend grows toward the tip
        tip = (x + lean * h * dx, y + lean * h * dy, h)
        co += [(x - px, y - py, 0.0), (x + px, y + py, 0.0),
               (mid[0] + 0.6 * px, mid[1] + 0.6 * py, mid[2]), (mid[0] - 0.6 * px, mid[1] - 0.6 * py, mid[2]), tip]
        ps += [len(lv), len(lv) + 4]
        lv += [k, k + 1, k + 2, k + 3, k + 3, k + 2, k + 4]
        u += [0.0, 0.0, 0.55, 0.55, 1.0]
        ln += [h] * 5
        tint += [pick] * 5
        pm += [0, 0]
        if flower:
            f = FLOWER_M
            co += [(tip[0] + f * dx - f * dy, tip[1] + f * dy + f * dx, h + 0.3 * f),
                   (tip[0] + f * dx + f * dy, tip[1] + f * dy - f * dx, h + 0.3 * f)]
            ps.append(len(lv))
            lv += [k + 4, k + 5, k + 6]
            u += [1.0, 1.0]
            ln += [h, h]
            tint += [pick] * 2
            pm.append(1 + int(pick * len(FLOWER_RGB)) % len(FLOWER_RGB))
    f32, i64 = np.float32, np.int64
    return {"co": np.asarray(co, f32).reshape(-1, 3), "lv": np.asarray(lv, i64), "ps": np.asarray(ps, i64),
            "u": np.asarray(u, f32), "len": np.asarray(ln, f32), "pm": np.asarray(pm, i64),
            "tint": np.asarray(tint, f32), "uv": np.zeros((len(lv), 2), f32)}


def _blade_mats(bpy, crop):
    """Blade colour from the root (dark, green) to the tip (dry, sun-bleached) along valora_sway, jittered per
    blade by valora_tint: the fallback field is no longer one flat green."""
    from engine.blender import set_parts as P
    from engine.blender.env_assets import TINT_ATTR
    m = bpy.data.materials.new(f"valora_field_{crop}")
    m.use_nodes = True
    nt = m.node_tree
    sh = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    sh.inputs["Roughness"].default_value = 0.55
    sw, tn = nt.nodes.new("ShaderNodeAttribute"), nt.nodes.new("ShaderNodeAttribute")
    sw.attribute_name, tn.attribute_name = "valora_sway", TINT_ATTR
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*BLADE_ROOT[crop], 1.0)
    ramp.color_ramp.elements[1].color = (*BLADE_TIP[crop], 1.0)
    nt.links.new(sw.outputs["Fac"], ramp.inputs["Fac"])
    jit = nt.nodes.new("ShaderNodeMapRange")
    jit.inputs["To Min"].default_value, jit.inputs["To Max"].default_value = 0.6, 1.25
    nt.links.new(tn.outputs["Fac"], jit.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type, mul.blend_type = "RGBA", "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(ramp.outputs["Color"], mul.inputs[6])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    for ax in ("X", "Y", "Z"):
        nt.links.new(jit.outputs["Result"], comb.inputs[ax])
    nt.links.new(comb.outputs[0], mul.inputs[7])
    nt.links.new(mul.outputs[2], sh.inputs["Base Color"])
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")   # thin blades glow when backlit
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    nt.links.new(mul.outputs[2], tr.inputs["Color"])
    mx = nt.nodes.new("ShaderNodeMixShader")
    mx.inputs["Fac"].default_value = TRANSLUCENT
    nt.links.new(sh.outputs[0], mx.inputs[1])
    nt.links.new(tr.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    mats = [m]
    if crop == "wildflowers":
        mats += [P.mat(f"valora_field_flower_{i}", c, 0.5) for i, c in enumerate(FLOWER_RGB)]
    return mats


def _tuft_sites(lay, protos, tod, cameras):
    """Photoscanned tufts rooted at candidate blades (every TUFT_EVERY-th), as tall as that blade (so the
    clearing, the edge taper and every sight cut carry over), never reaching into the subject's footprint.
    The vertex budget goes first to roots a camera looks across (within TUFT_CONE_DEG of its line through the
    subject, either side of it), nearest the subject first; the rest of the field keeps the procedural blades."""
    import random
    cx, cy = lay["centre"]
    hx, hy = lay["footprint"]
    rng = random.Random(len(lay["blades"]))
    cams = [(c[0] - cx, c[1] - cy) for c in cameras if math.hypot(c[0] - cx, c[1] - cy) > 1e-6]
    cos_cone = math.cos(math.radians(TUFT_CONE_DEG))
    cands = []
    for i, (x, y, yaw, h, lean, flower, pick) in enumerate(lay["blades"]):
        if i % TUFT_EVERY or h < TUFT_MIN_H:
            continue
        pi = int(pick * 997) % len(protos)
        pr = protos[pi]
        s = h / pr["h"]
        reach = pr["r"] * s + 0.02
        if abs(x - cx) - reach <= hx and abs(y - cy) - reach <= hy:
            continue
        dx, dy = x - cx, y - cy
        seen = not cams
        for ax, ay in cams:
            d = math.hypot(dx, dy) * math.hypot(ax, ay)
            if d > 0 and abs(dx * ax + dy * ay) / d > cos_cone:
                seen = True
                break
        cands.append((0 if seen else 1, rng.random(), x, y, s, pi))
    cands.sort()
    sites, verts, dry = [], 0, DRY_SHARE[tod]
    tiny = [i for i, pr in enumerate(protos) if pr.get("tiny")]
    big = [i for i, pr in enumerate(protos) if not pr.get("tiny")]
    cands = [c for c in cands if c[5] in big]
    for _, _, x, y, s, pi in cands:
        n = len(protos[pi]["co"])
        if verts + n > TUFT_VERT_CAP:
            continue
        verts += n
        t = min(1.0, max(0.0, rng.gauss(dry, 0.22)))
        sites.append((x, y, rng.uniform(0.0, 360.0), s, pi, t))
    if tiny:                                                 # ground cover where the blades are cut or cleared
        tv = 0
        for i, (x, y, yaw, h, lean, flower, pick) in enumerate(lay["blades"]):
            if i % TINY_EVERY or h >= 3 * TUFT_MIN_H:
                continue
            pi = tiny[int(pick * 991) % len(tiny)]
            pr = protos[pi]
            s = min(1.6, max(h, 0.02) / pr["h"])
            reach = pr["r"] * s + 0.01
            if abs(x - cx) - reach <= hx and abs(y - cy) - reach <= hy:
                continue
            if tv + len(pr["co"]) > TINY_VERT_CAP:
                break
            tv += len(pr["co"])
            sites.append((x, y, rng.uniform(0.0, 360.0), s, pi, min(1.0, max(0.0, rng.gauss(dry, 0.25)))))
    return sites


def _foliage(bpy, ctx, lay, crop, tod, lib):
    """ONE joined foliage mesh (the foliage contract): the procedural blades and, with the library, the
    photoscanned tufts. Every island has valora_sway 0 at its lowest point and valora_sway_len its length."""
    import numpy as np
    from engine.blender import env_assets as E
    from engine.blender import set_parts as P
    from engine.blender.realism_rig import SWAY, SWAY_LEN, write_attr
    mats = _blade_mats(bpy, crop)
    n_tufts = 0
    protos = []
    if lib["grass02"] is not None:
        protos += E.load_protos(lib["grass02"], target_verts=TUFT_VERTS)
    if lib["grass01"] is not None:
        protos += E.load_protos(lib["grass01"], keep=("mid", "small", "tall"), target_verts=TUFT_VERTS)
        for pr in E.load_protos(lib["grass01"], keep=("tiny",)):
            pr["tiny"] = True
            protos.append(pr)
    blades = lay["blades"]
    if protos and blades:
        blades = [b for i, b in enumerate(blades) if i % BLADE_KEEP == 0 or b[5]]   # flowers always stay
    parts = [_blade_arrays({"blades": blades}, crop)] if blades else []
    if protos and lay["blades"]:
        tuft_mats = {}
        for pr in protos:
            src = pr["mats"][0] if pr["mats"] else None
            key = src.name if src is not None else "none"
            if key not in tuft_mats:
                dry = lib["grass02_dry"] if "grass_medium_02" in key else None
                tuft_mats[key] = E.tinted_foliage(src, f"valora_field_tuft_{len(tuft_mats)}", dry_path=dry,
                                                  tip_rgb=BLADE_TIP[crop] if tod != "overcast" else None,
                                                  translucency=TRANSLUCENT)
            pr["mats"] = [tuft_mats[key]]
        sites = _tuft_sites(lay, protos, tod, list(ctx.camera_positions))
        arr = E.scatter(protos, sites)
        if arr is not None:
            arr["pm"] = arr["pm"] + len(mats)
            mats += arr.pop("mats")
            parts.append(arr)
            n_tufts = len(sites)
    if not parts:
        return None, 0.0, 0, protos
    cat = {k: np.concatenate([pt[k] for pt in parts]) for k in ("co", "u", "len", "pm", "tint", "uv")}
    lvs, pss, vo, lo = [], [], 0, 0
    for pt in parts:                                          # re-base each part's loops and loop starts
        lvs.append(pt["lv"] + vo)
        pss.append(pt["ps"] + lo)
        vo += len(pt["co"])
        lo += len(pt["lv"])
    ob = E.build_mesh(ctx.scene, "valora_field_blades", cat["co"], np.concatenate(lvs), np.concatenate(pss),
                      cat["uv"], cat["pm"] if len(mats) > 1 else None, mats)
    P.tag(ob, BLOCK, foliage=True)
    write_attr(ob, SWAY, cat["u"], "FLOAT")
    write_attr(ob, SWAY_LEN, cat["len"], "FLOAT")
    write_attr(ob, E.TINT_ATTR, cat["tint"], "FLOAT")
    return ob, _root_sway(ob), n_tufts, protos


def _far_grass(bpy, ctx, lay, protos, crop, tod, lib, cameras):
    """Instanced tufts from the blade disc's edge to the horizon at the layout's far-grass sites (static; the
    near field keeps the swaying foliage mesh). The layout already cut them under every camera's sight line."""
    from engine.blender import env_assets as E
    from engine.blender import set_parts as P
    big = [pr for pr in protos if not pr.get("tiny")]
    if not big:
        return None
    cx, cy = lay["centre"]
    if not lay["farGrass"]:
        return None
    mats = []
    for pr in big:
        src = pr["mats"][0] if pr["mats"] else None
        dry = lib["grass02_dry"] if src is not None and "grass_medium_02" in (src.name + pr["name"]) else None
        mats.append(src)
    far_mats = {}
    for i, pr in enumerate(big):
        key = mats[i].name if mats[i] is not None else "none"
        if key not in far_mats:
            far_mats[key] = E.tinted_foliage(mats[i], f"valora_field_far_{len(far_mats)}", dry_path=None,
                                             tip_rgb=BLADE_TIP[crop] if tod != "overcast" else None,
                                             per_object=DRY_SHARE[tod], translucency=TRANSLUCENT)
        mats[i] = far_mats[key]
    col = E.proto_objects(ctx.scene, "valora_field_far_protos", big, mats)
    for o in col.objects:
        P.tag(o, BLOCK)
    mean_h = sum(pr["h"] for pr in big) / len(big)
    ob = E.point_instances(ctx.scene, "valora_field_far_grass", col, lay["farGrass"], mean_h, ctx.seed % 10007)
    return P.tag(ob, BLOCK)


def _root_sway(ob):
    """valora_sway at each island's lowest vertex, the largest (the contract wants 0 everywhere)."""
    import numpy as np
    me = ob.data
    n = len(me.vertices)
    if not n:
        return 0.0
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    z = co.reshape(-1, 3)[:, 2]
    u = np.empty(n, np.float32)
    me.attributes["valora_sway"].data.foreach_get("value", u)
    ed = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get("vertices", ed)
    ed = ed.reshape(-1, 2)
    lab = np.arange(n)
    while True:                                              # label propagation: min vertex index per island
        m = np.minimum(lab[ed[:, 0]], lab[ed[:, 1]])
        new = lab.copy()
        np.minimum.at(new, ed[:, 0], m)
        np.minimum.at(new, ed[:, 1], m)
        new = new[new]
        if (new == lab).all():
            break
        lab = new
    order = np.lexsort((z, lab))                             # by island, then height
    first = np.ones(n, bool)
    first[1:] = lab[order][1:] != lab[order][:-1]
    return float(u[order][first].max())


def _trees(bpy, ctx, lay, path, haze, strength, sky=None):
    """Rigid instances of one shared tree mesh, fading into the sun haze by distance (none without it)."""
    from engine.blender import set_parts as P
    from engine.blender.env_assets import aerial, shared_mesh
    if path is None or not lay["trees"]:
        return []
    me, h0 = shared_mesh(path)
    if me is None:
        return []
    for m in me.materials:
        if m is not None:
            aerial(m, tuple(c * strength for c in haze), HAZE_HALF_M, max_mix=0.8, hdri=sky)
    out = []
    for i, (x, y, h, yaw) in enumerate(lay["trees"]):
        ob = bpy.data.objects.new(f"valora_field_tree_{i}", me)
        ctx.scene.collection.objects.link(ob)
        s = h / max(1e-3, h0)
        ob.scale = (s, s, s)
        ob.location = (x, y, -0.05)
        ob.rotation_euler[2] = math.radians(yaw)
        out.append(P.tag(ob, BLOCK))
    return out


def _library():
    from engine.assets import resolve, resolve_gltf
    lib = {"grass02": resolve_gltf("grass_medium_02_1k"), "grass01": resolve_gltf("grass_medium_01_1k"),
           "grass02_dry": resolve("grass_medium_02_dry_diff_1k"), "tree": resolve_gltf("tree_small_02_1k"),
           "ground": {k: resolve(f"withered_grass_{k}_2k") for k in ("diff", "rough", "nor_gl")},
           "green": {k: resolve(f"leafy_grass_{k}_2k") for k in ("diff", "rough", "nor_gl")},
           "dirt": {k: resolve(f"dry_ground_01_{k}_2k") for k in ("diff", "rough", "nor_gl")}}
    lib["hdri"] = {tod: resolve(name) for tod, (name, _, _) in HDRI.items()}
    return lib


def build(ctx):
    import bpy
    from engine.blender import env_assets as E
    from engine.blender import set_parts as P
    from engine.color import kelvin_to_rgb
    from engine.worlds.field_layout import layout
    p, prof = ctx.params, ctx.profile
    tod, crop = p["timeOfDay"], p["crop"]
    lay = layout(prof, ctx.seed, float(p["grassHeightM"]), crop, bool(p["track"]),
                 cameras=[tuple(c) for c in ctx.camera_positions],
                 hero=tuple(ctx.hero_pose.position) if ctx.hero_pose is not None else None)
    el, kelvin, strength, angle, _ = SUN[tod]
    sun_dir = _sun_vector(ctx, float(p["sunAzimuthDeg"]), el)
    lib = _library()
    hdri = lib["hdri"][tod]
    cx, cy = lay["centre"]
    name, tint, sky_k = HDRI[tod]
    if hdri is not None:
        sky_rot = E.rotation_for(HDRI_SUN_AZ[name], sun_dir)
        E.world_hdri(ctx.scene, "valora_field_sky", hdri, sky_rot, sky_k, tint)
    else:
        sky_rot = _sky(bpy, ctx, tod, sun_dir)

    e = lay["extent"] / 2
    photo = all(lib["ground"].values())
    gmat = (_photo_ground(bpy, lib["ground"], lib["green"], crop, tod) if photo
            else _ground_mat(bpy, "valora_field_ground", crop))
    ground = P.mesh(ctx.scene, "valora_field_ground", BLOCK,
                    [(cx - e, cy - e, 0.0), (cx + e, cy - e, 0.0), (cx + e, cy + e, 0.0), (cx - e, cy + e, 0.0)],
                    [(0, 1, 2, 3)], [gmat])
    P.tag(ground, BLOCK, ground=True)
    far = None
    sky = (hdri, sky_rot, sky_k, tint) if hdri is not None else None
    if sky is not None:
        E.aerial(gmat, HAZE[tod], HAZE_HALF_M, max_mix=1.0, hdri=sky)
        b = FAR_M / 2                                         # the meadow runs on to the photo's horizon
        far = P.mesh(ctx.scene, "valora_field_far", BLOCK,
                     [(cx - b, cy - b, -0.02), (cx + b, cy - b, -0.02), (cx + b, cy + b, -0.02),
                      (cx - b, cy + b, -0.02)], [(0, 1, 2, 3)], [gmat])
        far.visible_shadow = False
    track = None
    if lay["track"]:
        x0, y0, x1, y1 = lay["track"]
        track = P.mesh(ctx.scene, "valora_field_track", BLOCK,
                       [(x0, y0, 0.001), (x1, y0, 0.001), (x1, y1, 0.001), (x0, y1, 0.001)], [(0, 1, 2, 3)],
                       [E.pbr("valora_field_dirt", lib["dirt"], DIRT_TILE_M, tint=(0.8, 0.72, 0.62))
                        if all(lib["dirt"].values()) else P.mat("valora_field_dirt", DIRT_RGB, 0.9)])
        P.tag(track, BLOCK, ground=True)

    blades, root_sway, n_tufts, protos = _foliage(bpy, ctx, lay, crop, tod, lib)
    far_grass = _far_grass(bpy, ctx, lay, protos, crop, tod, lib, list(ctx.camera_positions)) if protos else None

    horizon = None
    if hdri is None:                                         # the photo has its own skyline
        r = lay["extent"] / 2 * 0.98                         # the silhouette ring at the field's edge
        n = len(lay["horizon"])
        v, f = [], []
        for i, hgt in enumerate(lay["horizon"]):
            a0, a1 = math.tau * i / n, math.tau * (i + 1) / n
            h0, h1 = hgt * r, lay["horizon"][(i + 1) % n] * r
            P.quad(v, f, [(cx + r * math.cos(a0), cy + r * math.sin(a0), -0.5),
                          (cx + r * math.cos(a1), cy + r * math.sin(a1), -0.5),
                          (cx + r * math.cos(a1), cy + r * math.sin(a1), h1),
                          (cx + r * math.cos(a0), cy + r * math.sin(a0), h0)])
        horizon = P.mesh(ctx.scene, "valora_field_horizon", BLOCK, v, f,
                         [P.mat("valora_field_horizon", SILHOUETTE_RGB, 0.95)])
        horizon.visible_shadow = False
    trees = _trees(bpy, ctx, lay, lib["tree"], HAZE[tod], sky_k, sky)

    ld = bpy.data.lights.new("valora_field_sun", "SUN")
    ld.energy, ld.color, ld.angle = strength, kelvin_to_rgb(kelvin), math.radians(angle)
    sun = bpy.data.objects.new("valora_field_sun", ld)
    ctx.scene.collection.objects.link(sun)
    from mathutils import Vector
    sun.rotation_euler = Vector([-c for c in sun_dir]).to_track_quat("-Z", "Y").to_euler()   # shines along -Z
    P.tag(sun, BLOCK)
    sun["valora_world_sun"] = True
    sun["valora_world_sun_soft"] = tod == "overcast"          # hard_sun keeps an overcast sun soft (chunk 4 #6)

    ctx.scene["valora_field"] = {
        "timeOfDay": tod, "crop": crop, "extent": lay["extent"], "bladeRadius": lay["bladeRadius"],
        "blades": len(lay["blades"]), "bladeRootSwayMax": float(root_sway), "track": lay["track"] is not None,
        "clearing": dict(lay["clearing"]), "sun": {"elevationDeg": el, "azimuthDeg": float(p["sunAzimuthDeg"]),
                                                   "kelvin": kelvin, "strength": strength, "angleDeg": angle,
                                                   "direction": list(sun_dir), "skyRotationDeg": sky_rot},
        "sunObject": sun.name, "sightCut": lay["sightCut"], "hdri": hdri is not None, "photoGround": photo,
        "tufts": n_tufts, "trees": len(trees), "farMeadow": far is not None, "farGrass": far_grass is not None,
        "horizonRing": horizon is not None,
        "foliageVerts": len(blades.data.vertices) if blades is not None else 0}
    return ground
