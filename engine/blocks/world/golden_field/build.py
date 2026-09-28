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
# round 11 golden 3200 -> 3700 K (owner's r10 review: "a warm grade instead of a physical sunset"; r11a measured the
# foreground grass at r:g:b .56:.31:.12, every blade orange): the low sun is golden, the shade takes the sky's blue
SUN = {"dawn": (5.0, 3500.0, 2.5, 1.5, 0.55), "golden": (8.0, 3700.0, 3.5, 1.5, 0.75),
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
HAUSDORF_SUN_AZ = 144.1      # hausdorf_meadow_8k (overcast): its brightest cloud, same luminance-centroid
                             # measure and convention as the others (kloppenheim re-measured to within 0.1 deg);
                             # the treeline then runs ~110-200 deg round from the soft sun
# art pass (all eng). timeOfDay -> the pinned HDRI, its tint and strength; the photo's sun azimuth (deg, atan2
# of the brightest region's direction, measured 2026-09-25 with a luminance centroid over the 4k files)
HDRI = {"golden": ("evening_field_4k", (0.97, 0.98, 1.0), 0.5),   # round 11: 0.36 warm-tinted -> 0.5 neutral: the open
        # shade under a clear evening sky is cool; at 0.36 the 18 W/m^2 sun left the shade colourless  # round 10: evening_field (owner's r9 review: "the sky
        # is smooth and cloudless"): a golden-hour sky with warm-lit cloud streaks on both sides of the sun (the side-lit
        # hook frames the sky ~70 degrees round from it; belfast_sunset was smooth there) over a bare treeline; its
        # 15-40 degree band is 1.07x magalies', so 0.36 keeps it where magalies at 0.38 had it.
        # Was magalies_field_sunset_4k x 0.38; round 9 0.38 (the sky read "bright,
        # washed out and dead" over a dark car: a quieter sky under a stronger sun); round 8: was (1, .94, .84) x 0.8, a sky
        # so bright AgX rolled it to white and the tint made it one warm grey; at 0.5 its own warm horizon and cooler
        # upper sky stay in the mid-tones (in the paint too), and the low sun keys the set against a quieter sky
        "dusk": ("plains_sunset_4k", (1.0, 0.86, 0.74), 0.35), "dawn": ("plains_sunset_4k", (0.86, 0.9, 1.0), 0.45),
        "overcast": ("hausdorf_meadow_8k", (1.0, 1.0, 1.0), 1.6)}     # kloppenheim's 2.0 x the irradiance ratio
                              # 0.944 / 1.391 = 1.36 left the meadow ~5 stops under the sky (r2 frames: sky 190-215,
                              # grass 12-50 of 255); 1.6 with the brighter dry share below
HDRI_SUN_AZ = {"magalies_field_sunset_4k": 143.77, "evening_field_4k": 145.85, "plains_sunset_4k": 142.98, "kloppenheim_01_4k": 144.31,
               "hausdorf_meadow_8k": HAUSDORF_SUN_AZ}
FAR_M = 1200.0               # the far meadow plane: the photo's own ground is never projected (these HDRIs
                             # stand in tall grass: its near-horizon band is stalks, which smear when projected)
GROUND_TILE_M = 2.0          # withered_grass / leafy_grass tile (dry_ground_01 for the track)
GREEN_SHARE = {"golden": 0.45, "dusk": 0.3, "dawn": 0.45, "overcast": 0.6}    # leafy_grass patches (round 11: golden
#   0.22 -> 0.45, owner's r10 review "the grass shouldn't be uniformly brown": a golden-hour meadow is still green
GROUND_TINT = {"grass": (0.52, 0.42, 0.25), "wheat": (0.5, 0.4, 0.22),   # round 10 grass (0.42, 0.33, 0.19): gaps read black
               "wildflowers": (0.38, 0.34, 0.18)}                  # dark: the gaps between tufts read as shade
MACRO_M = 9.0                # large-scale brightness patches across the meadow (breaks the tile repeat)
HAZE = {"golden": (0.95, 0.66, 0.40), "dusk": (0.55, 0.36, 0.28), "dawn": (0.62, 0.62, 0.70),
        "overcast": (0.55, 0.58, 0.60)}            # aerial-perspective colour (x HDRI strength)
TREE_HAZE_HALF_M, TREE_HAZE_MAX = 110.0, 0.6   # (eng, round 10) the treelines 18-45 m off: golden-hour air lifts them
                             # toward the skyline (owner's r9 review: the field lacks the courtyard's aerial haze; at
                             # 350 m a 30 m stand kept 94% of its contrast and read as a black cut-out)
HAZE_HALF_M = 350.0          # distance at which the meadow / a tree is half haze (toward a low sun the horizon
                             # is many times brighter than the lit ground: a short half-distance fogs it out)
TINY_EVERY = 2               # one trampled / cleared blade in TINY_EVERY roots a tiny tuft (ground cover)
TINY_VERT_CAP = 400_000
TRANSLUCENT = 0.3            # share of translucent (backlit glow) in the grass (critique r4: 15-25%; round 10 0.3: under
                             # the side-back sun the r9 blades read as opaque brown string)
# round 3 (eng): the procedural plants' colour classes (field_plants GREEN, STRAW, BROWN, SEED): root -> tip
# colour, roughness. Dry grass 0.6-0.85 rough (critique r4); the crop tints the green and straw classes.
PLANT_RGB = {"green": ((0.035, 0.065, 0.016), (0.21, 0.26, 0.09)), "straw": ((0.12, 0.095, 0.04), (0.60, 0.48, 0.25)),
             "brown": ((0.04, 0.026, 0.012), (0.19, 0.12, 0.055)), "seed": ((0.36, 0.28, 0.13), (0.56, 0.45, 0.23))}
PLANT_ROUGH = (0.62, 0.78, 0.84, 0.72)
PRESSED_RGB = ((0.10, 0.08, 0.04), (0.30, 0.24, 0.12))     # flattened dead stems: dark to bleached straw
PRESSED_W = 0.003                                           # stem width, m
SOIL_PAD_M = 0.35            # the pressed soil patch reaches this past the footprint and the tyre patches
SOIL_TYRE_K = 0.6            # (eng, round 13) soil shows within this x the trample ramp of a tyre patch, no further
BLADE_KEEP = 2               # with the library, one procedural blade in BLADE_KEEP stays (fine fill under tufts)
TUFT_EVERY = 3               # one blade in TUFT_EVERY is a candidate tuft root (round 10: 4 -> 3, denser tufts)
TUFT_VERT_CAP = 1_700_000    # the foliage probe walks every edge: keep the joined mesh bounded
TUFT_VERTS = 400             # a mid-distance tuft is collapsed to about this many vertices
# LOD by projected size (engine/worlds/foliage_lod): a tuft >= FULL_PX tall in frame keeps its full scan
# (300-2600 verts), below MID_PX it collapses to FAR_VERTS; the budget first covers every chosen root at its
# cheap LOD, then upgrades the largest on screen to full detail while TUFT_VERT_CAP allows.
TUFT_SCALE = (0.7, 1.3)      # (eng, critique r4) a scanned tuft is never blown up past 1.3 x (its blades become
                             # ribbons): each root takes a scan near its height; far tufts are capped the same way
FAR_SCALE_NEAR_M, FAR_SCALE_RAMP_M, FAR_SCALE_MAX = 20.0, 40.0, 2.4   # (eng) past 20 m the cap eases to 2.4 x
                             # by 60 m: there a tuft is a few pixels and the meadow must still hide its flat plane
TUFT_CONE_DEG = 38.0         # tufts go first where a camera looks (within this of its line to the subject)
TUFT_MIN_H = 0.05            # blades shorter than this (the clearing, a sight cut) never root a tuft
DRY_SHARE = {"golden": 0.42, "dusk": 0.72, "dawn": 0.55, "overcast": 0.6}   # mean tint toward the dry texture (round
#   11: golden 0.6 -> 0.42, a mixed green and straw meadow)
FAR_SPECIES = 0.28           # (eng, round 12) the cover's green / straw instancers sit this either side of DRY_SHARE
SPECIES_K = 1.1              # (eng, round 12) a tuft's dry share follows the meadow's species drifts (field_layout.species)
#   this strongly (owner's r11 review "same detail everywhere": green stands beside straw stands, not a salt-and-pepper mix)
TUFT_SPLIT = {"golden": (0.42, 0.62)}   # (eng, round 11) near tufts: the per-tuft tint remapped over this band, so a
#   tuft is mostly green or mostly straw (mixed species), not every one the same half-dry brown
BLADE_ROOT = {"grass": (0.05, 0.075, 0.02), "wheat": (0.30, 0.22, 0.08), "wildflowers": (0.05, 0.08, 0.02)}
BLADE_TIP = {"grass": (0.52, 0.42, 0.18), "wheat": (0.78, 0.60, 0.28), "wildflowers": (0.30, 0.34, 0.12)}


SIDE_LIGHT_DEG = 70.0   # (eng, round 9) a low sun asked within this of straight behind swings to it: side-back light


def _sun_vector(ctx, azimuth_deg, elevation_deg, tod=None):
    """Unit vector from the subject toward the sun. Round 8: measured from the HOOK's camera (the frame a feed
    shows; the hero pose is a later shot, so a 'behind' sun lit the hook from the side and left its sky neutral),
    and a near-behind ask swings to rigs.SUN_CLEAR_DEG toward the tail: side-back light on the roof edge and rear
    shoulder, the sun's glow at the frame's edge, its disc out of frame.

    Round 9 (owner's r8 grade: "the sky, the dark car and the warm grass tell three stories"): at 32 degrees the
    camera-facing flank stood in its own shade, so a black car read near-black with studio reflections against a
    bright sky. A low sun (dawn / golden / dusk) now swings out to SIDE_LIGHT_DEG: still behind the car's far end,
    but far enough round that the flank the camera sees takes the same warm light as the grass (measured on the
    field hook: the sun's dot with the visible flank 0.03 -> 0.64), and the grass shadows rake across the frame."""
    cx, cy, _ = ctx.profile.center
    from engine.lighting.rigs import backlight_azimuth, sun_vector
    keys = [k for k in (ctx.camera_keys or []) if k.shot == 0]
    ref = keys[len(keys) // 2].pose.position if keys else (ctx.hero_pose.position if ctx.hero_pose else None)
    if ref is None:
        return sun_vector(ctx.profile, (cx, cy - 1.0, 0.0), azimuth_deg, elevation_deg)
    from engine.lighting.rigs import SUN_CLEAR_DEG
    clear = SIDE_LIGHT_DEG if tod in ("dawn", "golden", "dusk") else SUN_CLEAR_DEG
    return sun_vector(ctx.profile, ref, backlight_azimuth(ctx.profile, ref, azimuth_deg, clear), elevation_deg)


GLOW = {"golden": ((1.35, 0.92, 0.60), 1.0), "dusk": ((1.3, 0.82, 0.58), 0.75), "dawn": ((1.2, 0.95, 0.82), 0.5)}
# the upper sky away from the glow: a low sun's sky is a deeper blue overhead than a hazy noon's (r9b: the photo's
# pale upper sky, lit up by the grade, read "washed out and dead")
UPPER_SKY = {"golden": (0.78, 0.84, 0.96), "dusk": (0.72, 0.78, 0.94), "dawn": (0.85, 0.88, 0.97)}
GLOW_TOP = 0.45              # (eng) sine of the elevation where the horizon glow has faded out (~27 degrees)
GLOW_TOWARD_SUN = 0.6        # (eng) share of the glow that follows the sun's side (the rest rings the whole horizon)


def _horizon_glow(w, tod, sun_dir):
    """Round 9 (owner's r8 grade: "the sky is bright, washed out and dead, the grass says warm sunset"): under a low
    sun the whole lower sky carries the sun's colour through the long air path, strongest on the sun's side, fading
    to the photo's own sky by ~27 degrees up. The HDRI (a hazy sunset) keeps its warmth only in a narrow glow round
    its sun, which the side-lit hero never frames, so the lower sky is multiplied toward GLOW's tint by up to its
    weight. It is the World: the paint and the grass see the same warm horizon the camera does."""
    if tod not in GLOW:
        return
    tint, weight = GLOW[tod]
    nt = w.node_tree
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    link = next((l for l in nt.links if l.to_socket == bg.inputs["Color"]), None)
    if link is None:
        return
    tc = next((n for n in nt.nodes if n.type == "TEX_COORD"), None) or nt.nodes.new("ShaderNodeTexCoord")
    unit = nt.nodes.new("ShaderNodeVectorMath")
    unit.operation = "NORMALIZE"
    nt.links.new(tc.outputs["Generated"], unit.inputs[0])
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(unit.outputs[0], sep.inputs[0])
    low = nt.nodes.new("ShaderNodeMapRange")
    low.interpolation_type = "SMOOTHSTEP"
    low.inputs["From Min"].default_value, low.inputs["From Max"].default_value = 0.0, GLOW_TOP
    low.inputs["To Min"].default_value, low.inputs["To Max"].default_value = 1.0, 0.0
    nt.links.new(sep.outputs["Z"], low.inputs["Value"])
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    nt.links.new(unit.outputs[0], dot.inputs[0])
    dot.inputs[1].default_value = (sun_dir[0], sun_dir[1], 0.0)
    side = nt.nodes.new("ShaderNodeMapRange")
    side.inputs["From Min"].default_value, side.inputs["From Max"].default_value = -1.0, 1.0
    side.inputs["To Min"].default_value, side.inputs["To Max"].default_value = 1.0 - GLOW_TOWARD_SUN, 1.0
    nt.links.new(dot.outputs["Value"], side.inputs["Value"])
    f = nt.nodes.new("ShaderNodeMath")
    f.operation = "MULTIPLY"
    nt.links.new(low.outputs["Result"], f.inputs[0])
    nt.links.new(side.outputs["Result"], f.inputs[1])
    g = nt.nodes.new("ShaderNodeMath")
    g.operation = "MULTIPLY"
    nt.links.new(f.outputs[0], g.inputs[0])
    g.inputs[1].default_value = weight
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
    mix.name = "valora_field_horizon_glow"
    nt.links.new(g.outputs[0], mix.inputs["Factor"])
    nt.links.new(link.from_socket, mix.inputs[6])
    mix.inputs[7].default_value = (*tint, 1.0)
    up = nt.nodes.new("ShaderNodeMapRange")                   # 0 at the glow's top, 1 by ~40 degrees up
    up.interpolation_type = "SMOOTHSTEP"
    up.inputs["From Min"].default_value, up.inputs["From Max"].default_value = GLOW_TOP * 0.6, 0.65
    nt.links.new(sep.outputs["Z"], up.inputs["Value"])
    deep = nt.nodes.new("ShaderNodeMix")
    deep.data_type, deep.blend_type = "RGBA", "MULTIPLY"
    deep.name = "valora_field_upper_sky"
    nt.links.new(up.outputs["Result"], deep.inputs["Factor"])
    nt.links.new(mix.outputs[2], deep.inputs[6])
    deep.inputs[7].default_value = (*UPPER_SKY[tod], 1.0)
    nt.links.new(deep.outputs[2], bg.inputs["Color"])


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
    """The procedural plants as flat arrays (engine/worlds/field_plants: fine blades, broad leaves, bent stalks,
    seed heads, dead blades, low weeds; 1.5-6 mm wide), each its own island with sway 0 at its root. Material
    slots 0..3 are the colour classes (green, straw, brown, seed), 4.. the flowers."""
    import numpy as np
    from engine.worlds import field_plants as FP
    co, lv, ps, u, ln, pm, tint = [], [], [], [], [], [], []
    for x, y, yaw, h, lean, flower, pick in lay["blades"]:
        v, polys, uu, cols = FP.blade(x, y, yaw, h, lean, pick)
        k = len(co)
        co += v
        for q, c in zip(polys, cols):
            ps.append(len(lv))
            lv += [k + i for i in q]
            pm.append(c)
        u += uu
        top = max(z for *_, z in v)
        ln += [max(top, 1e-4)] * len(v)
        tint += [pick] * len(v)
        if flower:
            tip = max(range(len(v)), key=lambda i: v[i][2])
            tx, ty, tz = v[tip]
            a = math.radians(yaw)
            dx, dy = math.cos(a), math.sin(a)
            f = FLOWER_M
            q = len(co)
            co += [(tx + f * dx - f * dy, ty + f * dy + f * dx, tz + 0.3 * f),
                   (tx + f * dx + f * dy, ty + f * dy - f * dx, tz + 0.3 * f)]
            ps.append(len(lv))
            lv += [k + tip, q, q + 1]
            u += [1.0, 1.0]
            ln += [max(top, 1e-4)] * 2
            tint += [pick] * 2
            pm.append(4 + int(pick * len(FLOWER_RGB)) % len(FLOWER_RGB))
    f32, i64 = np.float32, np.int64
    return {"co": np.asarray(co, f32).reshape(-1, 3), "lv": np.asarray(lv, i64), "ps": np.asarray(ps, i64),
            "u": np.asarray(u, f32), "len": np.asarray(ln, f32), "pm": np.asarray(pm, i64),
            "tint": np.asarray(tint, f32), "uv": np.zeros((len(lv), 2), f32)}


GAP_COVER_EVERY = 4          # (eng, round 14) one plant in this many that falls in a clump gap becomes low cover
#                              (4: the foliage probe's 2.3M-vertex budget; 1 measured 2.44M)


def _cover_arrays(blades):
    """The gap plants as low cover (field_plants.cover: clover, broadleaf rosettes, lying thatch), in the blade
    arrays' layout and colour-class slots, each its own island with sway 0 at its root."""
    import numpy as np
    from engine.worlds import field_plants as FP
    co, lv, ps, u, ln, pm, tint = [], [], [], [], [], [], []
    for x, y, yaw, h, lean, flower, pick in blades:
        v, polys, uu, cols = FP.cover(x, y, yaw, h, pick)
        k = len(co)
        co += v
        for q, c in zip(polys, cols):
            ps.append(len(lv))
            lv += [k + i for i in q]
            pm.append(c)
        u += uu
        top = max(z for *_, z in v)
        ln += [max(top, 1e-4)] * len(v)
        tint += [pick] * len(v)
    f32, i64 = np.float32, np.int64
    return {"co": np.asarray(co, f32).reshape(-1, 3), "lv": np.asarray(lv, i64), "ps": np.asarray(ps, i64),
            "u": np.asarray(u, f32), "len": np.asarray(ln, f32), "pm": np.asarray(pm, i64),
            "tint": np.asarray(tint, f32), "uv": np.zeros((len(lv), 2), f32)}


def _plant_mat(bpy, name, root, tip, rough):
    """A plant colour class: root -> tip along valora_sway, jittered per plant by valora_tint (value and a little
    hue), dry roughness, and a TRANSLUCENT share of translucency (thin blades glow when backlit)."""
    from engine.blender.env_assets import TINT_ATTR
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    sh = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    sh.inputs["Roughness"].default_value = rough
    sh.inputs["Specular IOR Level"].default_value = 0.3
    sw, tn = nt.nodes.new("ShaderNodeAttribute"), nt.nodes.new("ShaderNodeAttribute")
    sw.attribute_name, tn.attribute_name = "valora_sway", TINT_ATTR
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*root, 1.0)
    ramp.color_ramp.elements[1].color = (*tip, 1.0)
    nt.links.new(sw.outputs["Fac"], ramp.inputs["Fac"])
    hsv = nt.nodes.new("ShaderNodeHueSaturation")
    nt.links.new(ramp.outputs["Color"], hsv.inputs["Color"])
    for sock, lo, hi in (("Value", 0.65, 1.3), ("Hue", 0.47, 0.53), ("Saturation", 0.8, 1.15)):
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = lo, hi
        src = tn.outputs["Fac"]
        if sock != "Value":                                   # decorrelated from the value jitter
            fr = nt.nodes.new("ShaderNodeMath")
            fr.operation = "FRACT"
            mul = nt.nodes.new("ShaderNodeMath")
            mul.operation = "MULTIPLY"
            mul.inputs[1].default_value = 7.0 if sock == "Hue" else 13.0
            nt.links.new(src, mul.inputs[0])
            nt.links.new(mul.outputs[0], fr.inputs[0])
            src = fr.outputs[0]
        nt.links.new(src, mr.inputs["Value"])
        nt.links.new(mr.outputs["Result"], hsv.inputs[sock])
    col = hsv.outputs["Color"]
    nt.links.new(col, sh.inputs["Base Color"])
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    nt.links.new(col, tr.inputs["Color"])
    mx = nt.nodes.new("ShaderNodeMixShader")
    mx.inputs["Fac"].default_value = TRANSLUCENT
    nt.links.new(sh.outputs[0], mx.inputs[1])
    nt.links.new(tr.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    return m


def _blade_mats(bpy, crop):
    """Slots 0..3: the plant colour classes (green and straw tinted toward the crop), 4..: the flowers."""
    from engine.blender import set_parts as P

    def toward(c, t, k):
        return tuple(a + (b - a) * k for a, b in zip(c, t))
    mats = []
    for i, cls in enumerate(("green", "straw", "brown", "seed")):
        root, tip = PLANT_RGB[cls]
        if cls in ("green", "straw"):
            root, tip = toward(root, BLADE_ROOT[crop], 0.3), toward(tip, BLADE_TIP[crop], 0.3)
        mats.append(_plant_mat(bpy, f"valora_field_{crop}_{cls}", root, tip, PLANT_ROUGH[i]))
    mats += [P.mat(f"valora_field_flower_{i}", c, 0.5) for i, c in enumerate(FLOWER_RGB)]
    return mats


def _tuft_sites(lay, protos, tod, cameras, lenses=(), seed=0, wind_deg=0.0):
    """Photoscanned tufts rooted at candidate blades (every TUFT_EVERY-th), as tall as that blade (so the
    clearing, the edge taper and every sight cut carry over), never reaching into the subject's footprint.
    The vertex budget goes first to roots a camera looks across (within TUFT_CONE_DEG of its line through the
    subject, either side of it), nearest the subject first; the rest of the field keeps the procedural blades.
    Protos carrying "lods" ([full, mid, far] proto indices) get their LOD by projected size from the camera keys
    (foliage_lod): the cheap LOD first for every root, then the largest on screen upgraded to full detail."""
    import random
    from engine.worlds import field_layout as FL
    from engine.worlds import foliage_lod as LOD
    cx, cy = lay["centre"]
    hx, hy = lay["footprint"]
    rng = random.Random(len(lay["blades"]))
    cams = [(c[0] - cx, c[1] - cy) for c in cameras if math.hypot(c[0] - cx, c[1] - cy) > 1e-6]
    cos_cone = math.cos(math.radians(TUFT_CONE_DEG))
    cands = []
    base = [pr for pr in protos if not pr.get("lodExtra")]
    for i, (x, y, yaw, h, lean, flower, pick) in enumerate(lay["blades"]):
        if i % TUFT_EVERY or h < TUFT_MIN_H:
            continue
        pi = int(pick * 997) % len(base)
        if not base[pi].get("tiny"):                          # a scan that stands this tall at 0.7-1.3 x its size
            fit = [k for k, q in enumerate(base) if not q.get("tiny") and TUFT_SCALE[0] <= h / q["h"] <= TUFT_SCALE[1]]
            if fit:
                pi = fit[int(pick * 7919) % len(fit)]
        pr = protos[pi]
        s = min(TUFT_SCALE[1], h / pr["h"])
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
    big = [i for i, pr in enumerate(protos) if not pr.get("tiny") and not pr.get("lodExtra")]
    cands = [c for c in cands if c[5] in big]
    cams3 = [tuple(c) for c in cameras]
    lod_px = []                                              # per site: (projected px, [full, mid, far])
    for _, _, x, y, s, pi in cands:
        lods = protos[pi].get("lods")
        if lods:
            px = LOD.projected_px((x, y, 0.5 * s * protos[pi]["h"]), s * protos[pi]["h"], cams3, list(lenses))
            pi = lods[max(1, LOD.pick(px))]                  # cheap first: full detail is an upgrade below
        else:
            px = 0.0
        n = len(protos[pi]["co"])
        if verts + n > TUFT_VERT_CAP:
            continue
        verts += n
        t = min(1.0, max(0.0, dry + SPECIES_K * (FL.species(x, y, seed) - 0.5) + rng.gauss(0.0, 0.1)))
        sites.append((x, y, rng.uniform(0.0, 360.0), s, pi, t, *FL.lodge(x, y, seed, wind_deg, (x * 7.13 + y * 3.71) % 1.0)))
        lod_px.append((px, lods))
    for k in sorted(range(len(sites)), key=lambda k: -lod_px[k][0]):
        px, lods = lod_px[k]
        if not lods or LOD.pick(px) != 0:
            break
        x, y, yaw, s, pi, t, tilt, toward = sites[k]
        extra = len(protos[lods[0]]["co"]) - len(protos[pi]["co"])
        if verts + extra > TUFT_VERT_CAP:
            break
        verts += extra
        sites[k] = (x, y, yaw, s, lods[0], t, tilt, toward)
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
            sites.append((x, y, rng.uniform(0.0, 360.0), s, pi, min(1.0, max(0.0, rng.gauss(dry, 0.25))), 0.0, 0.0))
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
    from engine.worlds import foliage_lod as LOD
    protos, extra = [], []

    def with_lods(path, keep=None):
        """Mid-LOD protos (the list the layout's picks index), each with "lods" = [full, mid, far] indices into
        the final protos list; the full and far twins are appended after every base proto ("lodExtra")."""
        mid = E.load_protos(path, keep=keep, target_verts=TUFT_VERTS)
        full = E.load_protos(path, keep=keep)
        far = E.load_protos(path, keep=keep, target_verts=LOD.FAR_VERTS)
        for m, f, r in zip(mid, full, far):
            f["lodExtra"] = r["lodExtra"] = True
            m["twins"] = (f, r)
        return mid
    if lib["grass02"] is not None:
        protos += with_lods(lib["grass02"])
    if lib["grass01"] is not None:
        protos += with_lods(lib["grass01"], keep=("mid", "small", "tall"))
        for pr in E.load_protos(lib["grass01"], keep=("tiny",)):
            pr["tiny"] = True
            protos.append(pr)
    for i, pr in enumerate(list(protos)):
        if "twins" in pr:
            f, r = pr.pop("twins")
            pr["lods"] = [len(protos), i, len(protos) + 1]
            protos += [f, r]
    from engine.worlds import field_plants as FP
    from engine.worlds.field_layout import cover_mask
    if lib["flora"].get("fine") and any(lib["flora"]["fine"]):   # round 15: where the fine grass has its patch it
        from engine.worlds.field_layout import _hash01          # takes over from the coarse stems (see FINE_TAKES)
        lay = dict(lay, blades=[bl for bl in lay["blades"] if bl[4] > 1.0 or bl[5] or _hash01(
            int(bl[0] * 1000.0), int(bl[1] * 1000.0), ctx.seed ^ 0xF1E) >= FINE_TAKES * cover_mask(bl[0], bl[1], ctx.seed, "fine")])
    blades = [b for b in lay["blades"] if b[4] > 1.0 or b[5] or FP.clump(b[0], b[1], ctx.seed) >= FP.CLUMP_KEEP]
    if protos and blades:                                     # clumps with gaps; pressed and flowering stay
        blades = [b for i, b in enumerate(blades) if i % BLADE_KEEP == 0 or b[5] or b[4] > 1.0]
    parts = [_blade_arrays({"blades": blades}, crop)] if blades else []
    gap = [b for i, b in enumerate(lay["blades"]) if i % GAP_COVER_EVERY == 0 and b[4] <= 1.0 and not b[5]
           and b[3] > 0.004 and FP.clump(b[0], b[1], ctx.seed) < FP.CLUMP_KEEP]
    gap += [b for i, b in enumerate(lay.get("floor") or []) if i % GAP_COVER_EVERY == 0]   # and on the bare soil
    if gap:                                                   # round 14: the meadow floor between the clumps
        parts.append(_cover_arrays(gap))
    if protos and lay["blades"]:
        tuft_mats = {}
        for pr in protos:
            src = pr["mats"][0] if pr["mats"] else None
            key = src.name if src is not None else "none"
            if key not in tuft_mats:
                dry = lib["grass02_dry"] if "grass_medium_02" in key else None
                tuft_mats[key] = E.tinted_foliage(src, f"valora_field_tuft_{len(tuft_mats)}", dry_path=dry,
                                                  tip_rgb=BLADE_TIP[crop] if tod != "overcast" else None,
                                                  translucency=TRANSLUCENT, split=TUFT_SPLIT.get(tod))
            pr["mats"] = [tuft_mats[key]]
        clumped = dict(lay, blades=[b if FP.clump(b[0], b[1], ctx.seed) >= FP.CLUMP_KEEP - 0.08 else
                                    (b[0], b[1], b[2], 0.0, b[4], b[5], b[6]) for b in lay["blades"]])
        wind = ((ctx.script or {}).get("wind") or {}).get("params") or {}
        sites = _tuft_sites(clumped, protos, tod, list(ctx.camera_positions), list(ctx.camera_lenses_mm), ctx.seed,
                            float(wind.get("directionDeg", 0.0)) + 180.0)
        arr = E.scatter(protos, sites)
        if arr is not None:
            arr["pm"] = arr["pm"] + len(mats)
            mats += arr.pop("mats")
            parts.append(arr)
            n_tufts = len(sites)
            lod_of = {i: k for pr in protos for k, i in enumerate(pr.get("lods", ()))}
            ctx.scene["valora_field_tuft_lods"] = [sum(1 for st in sites if lod_of.get(st[4]) == k) for k in range(3)]
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
    big = [pr for pr in protos if not pr.get("tiny") and not pr.get("lodExtra")]
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
    from engine.worlds import field_layout as FL
    mean_h = sum(pr["h"] for pr in big) / len(big)
    cx, cy = lay["centre"]

    def cap(x, y):                                           # instances pick a random scan: cap its scale, 1.3 x
        t = min(1.0, max(0.0, (math.hypot(x - cx, y - cy) - FAR_SCALE_NEAR_M) / FAR_SCALE_RAMP_M))
        return (TUFT_SCALE[1] + t * (FAR_SCALE_MAX - TUFT_SCALE[1])) * mean_h   # near, more where it is a few px
    wind = ((ctx.script or {}).get("wind") or {}).get("params") or {}
    wdeg = float(wind.get("directionDeg", 0.0)) + 180.0
    # round 12 (owner's r11 review: "same detail everywhere"): the static cover and far meadow follow the species
    # drifts (a green instancer and a straw one, FAR_SPECIES either side of the time of day's dry share) and lie over
    # in the lodged patches, like the near tufts
    groups = ([], [])
    fine = bool(lib["flora"].get("fine") and any(lib["flora"]["fine"]))
    for x, y, yaw, h, w in lay["farGrass"]:
        if fine and FL._hash01(int(x * 1000.0), int(y * 1000.0), ctx.seed ^ 0xF1E) <                 FINE_TAKES * FL.cover_mask(x, y, ctx.seed, "fine"):
            continue                                          # round 15: the fine grass's patch (FINE_TAKES)
        sp = FL.species(x, y, ctx.seed)
        groups[sp >= 0.5].append((x, y, yaw, min(h, cap(x, y)), min(w, cap(x, y)),
                                  *FL.lodge(x, y, ctx.seed, wdeg, (x * 7.13 + y * 3.71) % 1.0)))
    out = None
    for g, sites in enumerate(groups):
        if not sites:
            continue
        dry = min(0.95, max(0.05, DRY_SHARE[tod] + (FAR_SPECIES if g else -FAR_SPECIES)))
        far_mats, gm = {}, list(mats)
        for i, pr in enumerate(big):
            key = gm[i].name if gm[i] is not None else "none"
            if key not in far_mats:
                far_mats[key] = E.tinted_foliage(gm[i], f"valora_field_far_{g}_{len(far_mats)}", dry_path=None,
                                                 tip_rgb=BLADE_TIP[crop] if tod != "overcast" else None,
                                                 per_object=dry, translucency=TRANSLUCENT)
            gm[i] = far_mats[key]
        col = E.proto_objects(ctx.scene, f"valora_field_far_protos_{g}", big, gm)
        for o in col.objects:
            P.tag(o, BLOCK)
        ob = E.point_instances(ctx.scene, "valora_field_far_grass" + ("_straw" if g else ""), col, sites, mean_h,
                               (ctx.seed + g) % 10007)
        out = out or P.tag(ob, BLOCK)
        P.tag(ob, BLOCK)
    return out


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


def _trees(bpy, ctx, lay, paths, haze, strength, sky=None):
    """Rigid instances of the pinned trees (one shared mesh per model, each tree picking one), fading into the
    sun haze by distance; none without them."""
    from engine.blender import set_parts as P
    from engine.blender.env_assets import aerial, shared_mesh
    paths = [p for p in paths if p is not None]
    if not paths or not lay["trees"]:
        return []
    models = []
    for path in paths:
        me, h0 = shared_mesh(path)
        if me is None:
            continue
        for m in me.materials:
            if m is not None:
                aerial(m, tuple(c * strength for c in haze), TREE_HAZE_HALF_M, max_mix=TREE_HAZE_MAX, hdri=sky)
        models.append((me, h0))
    if not models:
        return []
    out = []
    for i, (x, y, h, yaw, pick) in enumerate(lay["trees"]):
        me, h0 = models[int(pick * len(models)) % len(models)]
        ob = bpy.data.objects.new(f"valora_field_tree_{i}", me)
        ctx.scene.collection.objects.link(ob)
        s = h / max(1e-3, h0)
        ob.scale = (s, s, s)
        ob.location = (x, y, -0.05)
        ob.rotation_euler[2] = math.radians(yaw)
        out.append(P.tag(ob, BLOCK))
    return out


POST_RGB, POLE_RGB, WIRE_RGB = (0.085, 0.072, 0.058), (0.07, 0.058, 0.045), (0.05, 0.05, 0.05)   # (eng) old wood, steel
POST_W, POLE_R, WIRE_W = 0.09, 0.13, 0.008    # (eng) post section, pole radius, wire thickness (m)


def _box_between(v, f, a, b, w, up=(0.0, 0.0, 1.0)):
    """A square-section beam from a to b, w wide (4 side faces)."""
    ax, ay, az = a
    d = [b[i] - a[i] for i in range(3)]
    ln = math.sqrt(sum(c * c for c in d)) or 1.0
    d = [c / ln for c in d]
    s = [d[1] * up[2] - d[2] * up[1], d[2] * up[0] - d[0] * up[2], d[0] * up[1] - d[1] * up[0]]
    sn = math.sqrt(sum(c * c for c in s))
    if sn < 1e-6:
        s = [1.0, 0.0, 0.0]
        sn = 1.0
    s = [c / sn * w / 2 for c in s]
    u = [d[1] * s[2] - d[2] * s[1], d[2] * s[0] - d[0] * s[2], d[0] * s[1] - d[1] * s[0]]
    k = len(v)
    for p in (a, b):
        for sx, ux in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
            v.append(tuple(p[i] + sx * s[i] + ux * u[i] for i in range(3)))
    for q in range(4):
        f.append((k + q, k + (q + 1) % 4, k + 4 + (q + 1) % 4, k + 4 + q))


def _sag(a, b, sag, n=8):
    """Points along a wire from a to b, hanging `sag` metres at its middle."""
    return [tuple(a[i] + (b[i] - a[i]) * t for i in range(2)) + (a[2] + (b[2] - a[2]) * t - sag * 4 * t * (1 - t),)
            for t in (j / n for j in range(n + 1))]


def _boundary(bpy, ctx, haze, strength, sky):
    """Round 10: the field's post-and-wire fence and a distant utility-pole line (field_layout.boundary_props),
    weathered wood and dark steel, fading into the tree lines' aerial haze. Static, no shadow on the set."""
    from engine.blender import set_parts as P
    from engine.blender.env_assets import aerial
    from engine.worlds.field_layout import boundary_props
    cams = [tuple(k.pose.position) for k in (ctx.camera_keys or []) if k.shot == 0][:1] or [
        tuple(c) for c in ctx.camera_positions][:1]
    lay = boundary_props(ctx.profile, ctx.seed, cams)
    if not lay["posts"]:
        return []
    mats = [P.mat("valora_field_post", POST_RGB, 0.92), P.mat("valora_field_wire", WIRE_RGB, 0.5, 0.6)]
    for m in mats:
        aerial(m, tuple(c * strength for c in haze), TREE_HAZE_HALF_M, max_mix=TREE_HAZE_MAX, hdri=sky)
    v, f, mi = [], [], []

    def add(a, b, w, m):
        n0 = len(f)
        _box_between(v, f, a, b, w)
        mi.extend([m] * (len(f) - n0))
    tops = []
    for x, y, h, lx, ly, _ in lay["posts"]:
        top = (x + h * math.tan(math.radians(lx)), y + h * math.tan(math.radians(ly)), h)
        add((x, y, -0.1), top, POST_W, 0)
        tops.append((x, y, top))
    for i, j in lay["wires"]:
        for k in (0.5, 0.9):
            (xa, ya, ta), (xb, yb, tb) = tops[i], tops[j]
            a = (xa + (ta[0] - xa) * k, ya + (ta[1] - ya) * k, ta[2] * k)
            b = (xb + (tb[0] - xb) * k, yb + (tb[1] - yb) * k, tb[2] * k)
            pts = _sag(a, b, 0.04, 4)
            for p0, p1 in zip(pts, pts[1:]):
                add(p0, p1, WIRE_W, 1)
    poles = lay["poles"]
    ends = []
    for x, y, h, yaw in poles:
        add((x, y, -0.3), (x, y, h), 2 * POLE_R, 0)
        c, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        ox, oy = -s_ * 0.9, c * 0.9                           # the crossarm runs across the line
        add((x - ox, y - oy, h - 0.35), (x + ox, y + oy, h - 0.35), 0.1, 0)
        ends.append([(x + ox * k, y + oy * k, h - 0.3) for k in (-0.85, 0.0, 0.85)])
    for e0, e1 in zip(ends, ends[1:]):
        for a, b in zip(e0, e1):
            pts = _sag(a, b, 0.9, 10)
            for p0, p1 in zip(pts, pts[1:]):
                add(p0, p1, 0.02, 1)
    ob = P.mesh(ctx.scene, "valora_field_boundary", BLOCK, v, f, mats, mat_idx=mi)
    ob.visible_shadow = False
    return [ob]


SHRUBS = ("shrub_03_a", "shrub_03_b", "shrub_03_c", "shrub_03_d")
HEDGE_HAZE = (55.0, 0.62)          # (eng) the hedgerow 44 m off: a softer, lifted band (r11a at the trees' 110 m read black)


def _horizon_layers(bpy, ctx, haze, strength, sky):
    """Round 11 (owner's r10 review: "weak horizon, too much empty sky"): a hedgerow of shrub_03 behind the fence
    (field_layout.horizon_layers) in its own aerial haze, between the fence and the tree stands. Static, no shadow.
    (A hazed far ridge of hills was tried in r11b and read as a flat grey wall: the HDRI keeps its own skyline.)"""
    from engine.assets import resolve_gltf
    from engine.blender import set_parts as P
    from engine.blender.env_assets import aerial, shared_mesh
    from engine.worlds.field_layout import horizon_layers
    cams = [tuple(k.pose.position) for k in (ctx.camera_keys or []) if k.shot == 0][:1] or [
        tuple(c) for c in ctx.camera_positions][:1]
    lay = horizon_layers(ctx.profile, ctx.seed, cams)
    out = []
    path = resolve_gltf("shrub_03_1k")
    shrubs = []
    if path is not None and lay["hedge"]:
        for name in SHRUBS:
            me, h0 = shared_mesh(path, lambda n, name=name: n == name)
            if me is not None:
                for m in me.materials:
                    if m is not None and not m.get("valora_hazed"):
                        aerial(m, tuple(c * strength for c in haze), HEDGE_HAZE[0], max_mix=HEDGE_HAZE[1], hdri=sky)
                        m["valora_hazed"] = True
                shrubs.append((me, h0))
    for i, (x, y, h, yaw, pick) in enumerate(lay["hedge"] if shrubs else []):
        me, h0 = shrubs[int(pick * len(shrubs)) % len(shrubs)]
        ob = bpy.data.objects.new(f"valora_field_hedge_{i}", me)
        ctx.scene.collection.objects.link(ob)
        s = h / max(1e-3, h0)
        ob.scale = (s * (0.9 + 0.5 * pick), s * (0.9 + 0.5 * pick), s)
        ob.location = (x, y, -0.05)
        ob.rotation_euler[2] = math.radians(yaw)
        ob.visible_shadow = False
        out.append(P.tag(ob, BLOCK))
    return out


UNDERBODY = {"reach": 0.45, "shade": 0.42, "pad": 0.06}   # (eng, round 11) under and just round the car the grass
#   sees no sky: plants within `pad` + `reach` m of the footprint darken to `shade` of their colour at the footprint's
#   edge and inside it (the contact shadow of the grass itself; contact_ground only darkens the ground plane)


def _underbody(mats, prof):
    """Round 11 (owner's r10 review: "the tyre contact doesn't sell weight"): each plant / soil material's base colour
    x a footprint occlusion factor from world position (the subject is parked, so placed = world here)."""
    lo, hi = prof.boundsMin, prof.boundsMax
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    hx, hy = (hi[0] - lo[0]) / 2 + UNDERBODY["pad"], (hi[1] - lo[1]) / 2 + UNDERBODY["pad"]
    done = 0
    for m in mats:
        if m is None or not m.use_nodes or m.get("valora_underbody"):
            continue
        nt = m.node_tree
        sh = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if sh is None:
            continue
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(geo.outputs["Position"], sep.inputs[0])

        def m_(op, a, b):
            n = nt.nodes.new("ShaderNodeMath")
            n.operation = op
            for i, v in enumerate((a, b)):
                if isinstance(v, (int, float)):
                    n.inputs[i].default_value = float(v)
                else:
                    nt.links.new(v, n.inputs[i])
            return n.outputs[0]
        ox = m_("MAXIMUM", m_("SUBTRACT", m_("ABSOLUTE", m_("SUBTRACT", sep.outputs["X"], cx), 0.0), hx), 0.0)
        oy = m_("MAXIMUM", m_("SUBTRACT", m_("ABSOLUTE", m_("SUBTRACT", sep.outputs["Y"], cy), 0.0), hy), 0.0)
        d = m_("SQRT", m_("ADD", m_("MULTIPLY", ox, ox), m_("MULTIPLY", oy, oy)), 0.0)
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.interpolation_type = "SMOOTHSTEP"
        mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = 0.0, UNDERBODY["reach"]
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = UNDERBODY["shade"], 1.0
        nt.links.new(d, mr.inputs["Value"])
        base = sh.inputs["Base Color"]
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type, mul.blend_type = "RGBA", "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        if base.is_linked:
            nt.links.new(base.links[0].from_socket, mul.inputs[6])
        else:
            mul.inputs[6].default_value = tuple(base.default_value)
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        for ax in ("X", "Y", "Z"):
            nt.links.new(mr.outputs["Result"], comb.inputs[ax])
        nt.links.new(comb.outputs[0], mul.inputs[7])
        nt.links.new(mul.outputs[2], base)
        m["valora_underbody"] = True
        done += 1
    return done


COVER_LOOK = {"fine": (0.35, 0.35), "clover": (0.15, 0.45), "moss": (0.2, 0.3), "broadleaf": (0.25, 0.4)}
#   (eng, round 15) the floor species (field_layout.COVER_KINDS): mean dry share per plant, backlit translucency
FINE_TAKES = 0.7     # (eng, round 15) inside a fine-grass patch this share of the coarse stems, tufts and static cover
#                      gives way to it,
#                      so the meadow changes species across the frame (r15c: added under the coarse grass it only
#                      showed between the stems)
COVER_NO_SHADOW = ("fine", "clover", "moss")   # (eng, round 15) the low floor species cast no shadow: under the 8 degree
#   golden sun ~100k of them laid long shadows over the whole foreground and r15b's field went a stop darker than
#   r14's (the owner's brief: keep the grass brightness); the standing grass above them still shades them


def _cut_out(mat, alpha_path):
    """Round 15: Poly Haven's 1k glTF packs its leaf cards' colour as JPEG, so the importer's alpha link reads 1
    everywhere and a card renders as an opaque black square (r15a: the moss and bermuda cover darkened the whole
    foreground). The asset's own Alpha map, sampled with the colour's UVs, cuts each card out again."""
    import bpy
    if mat is None or alpha_path is None or not mat.use_nodes:
        return mat
    nt = mat.node_tree
    sh = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    col = next((l.from_node for l in nt.links if sh is not None and l.to_socket == sh.inputs["Base Color"]
                and l.from_node.type == "TEX_IMAGE"), None)
    if col is None:
        return mat
    im = nt.nodes.new("ShaderNodeTexImage")
    im.image = bpy.data.images.load(str(alpha_path), check_existing=True)
    im.image.colorspace_settings.name = "Non-Color"
    if col.inputs["Vector"].is_linked:
        nt.links.new(col.inputs["Vector"].links[0].from_socket, im.inputs["Vector"])
    nt.links.new(im.outputs["Color"], sh.inputs["Alpha"])
    return mat


def _flora(bpy, ctx, lay, lib):
    """Round 2: low weeds everywhere under the grass (what a trampled lane still has) and flowering plants,
    as static instances of the pinned plants at the layout's sites; none without them."""
    from engine.blender import env_assets as E
    from engine.blender import set_parts as P
    out = {}
    for kind, paths in lib["flora"].items():
        sites = lay["flora"].get(kind) or []
        protos = []
        for path in paths:
            if path is not None:
                protos += E.load_protos(path)
        if not protos or not sites:
            continue
        mats = [pr["mats"][0] if pr["mats"] else None for pr in protos]
        if kind in COVER_LOOK:                                # round 15: the floor species glow when backlit and
            dry, tr = COVER_LOOK[kind]                        # vary per plant like the tufts
            alpha = (lib.get("alpha") or {}).get(kind)
            mats = [E.tinted_foliage(_cut_out(m, alpha), f"valora_field_{kind}_{i}", per_object=dry, translucency=tr)
                    for i, m in enumerate(mats)]
        col = E.proto_objects(ctx.scene, f"valora_field_{kind}_protos", protos, mats)
        for o in col.objects:
            P.tag(o, BLOCK)
        mean_h = sum(pr["h"] for pr in protos) / len(protos)
        pts = [(x, y, yaw, s * mean_h, s * mean_h) for x, y, yaw, s in sites]
        ob = E.point_instances(ctx.scene, f"valora_field_{kind}", col, pts, mean_h, (ctx.seed + len(kind)) % 10007)
        if kind in COVER_NO_SHADOW:                           # round 15: see COVER_NO_SHADOW
            ob.visible_shadow = False
        out[kind] = P.tag(ob, BLOCK)
    return out


def _library():
    from engine.assets import resolve, resolve_gltf
    lib = {"grass02": resolve_gltf("grass_medium_02_1k"), "grass01": resolve_gltf("grass_medium_01_1k"),
           "grass02_dry": resolve("grass_medium_02_dry_diff_1k"),
           "trees": [resolve_gltf(t) for t in ("tree_small_02_1k", "island_tree_01_1k", "island_tree_02_1k")],
           "flora": {"weeds": [resolve_gltf("weed_plant_02_1k"), resolve_gltf("celandine_01_1k")],
                     "flowers": [resolve_gltf("flower_empodium_1k"), resolve_gltf("dandelion_01_1k")],
                     # round 15: the meadow floor's own species (field_layout.COVER_KINDS), each in its patches
                     "fine": [resolve_gltf("grass_bermuda_01_1k")], "clover": [resolve_gltf("shrub_sorrel_01_1k")],
                     "moss": [resolve_gltf("moss_01_1k")], "broadleaf": [resolve_gltf("nettle_plant_1k")]},
           "ground": {k: resolve(f"withered_grass_{k}_2k") for k in ("diff", "rough", "nor_gl")},
           "green": {k: resolve(f"leafy_grass_{k}_2k") for k in ("diff", "rough", "nor_gl")},
           "dirt": {k: resolve(f"dry_ground_01_{k}_2k") for k in ("diff", "rough", "nor_gl")}}
    lib["alpha"] = {k: resolve(f"{slug}_Alpha_1k") for k, slug in (("fine", "grass_bermuda_01"), ("clover", "shrub_sorrel_01"),
                                                                      ("moss", "moss_01"), ("broadleaf", "nettle_plant"))}
    lib["hdri"] = {tod: resolve(name) for tod, (name, _, _) in HDRI.items()}
    return lib


DIP_GRID_M = 0.03             # (eng, round 13) the dipped ground grid round the subject: cell size ...
DIP_PAD_M = 0.6               # ... reaching this past the footprint (every dip and rim lies inside it)


def _ground_mesh(lay, e, prof, seed):
    """(verts, faces) of the field ground: the extent square at z = 0 with a rectangular hole round the subject,
    filled by a DIP_GRID_M grid carrying field_layout.ground_dz (a dip under each tyre, sized by the weight it
    carries). The grid's border sits at z = 0 on the hole's edges, so the two meet without a step. A subject without
    wheels gets the plain square."""
    from engine.worlds import field_layout as FL
    cx, cy = lay["centre"]
    square = [(cx - e, cy - e, 0.0), (cx + e, cy - e, 0.0), (cx + e, cy + e, 0.0), (cx - e, cy + e, 0.0)]
    dips = FL.tyre_dips(prof)
    if not dips:
        return square, [(0, 1, 2, 3)]
    hx, hy = lay["footprint"]
    x0, y0, x1, y1 = cx - hx - DIP_PAD_M, cy - hy - DIP_PAD_M, cx + hx + DIP_PAD_M, cy + hy + DIP_PAD_M
    v = square + [(x0, y0, 0.0), (x1, y0, 0.0), (x1, y1, 0.0), (x0, y1, 0.0)]
    f = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]       # the ring round the hole
    nx, ny = max(2, int(round((x1 - x0) / DIP_GRID_M))), max(2, int(round((y1 - y0) / DIP_GRID_M)))
    base = len(v)
    for i in range(nx + 1):
        for j in range(ny + 1):
            x, y = x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny
            edge = i in (0, nx) or j in (0, ny)
            v.append((x, y, 0.0 if edge else FL.ground_dz(x, y, dips, seed)))
    for i in range(nx):
        for j in range(ny):
            q = base + i * (ny + 1) + j
            f.append((q, q + ny + 1, q + ny + 2, q + 1))
    return v, f


def _pressed(bpy, ctx, lay, lib):
    """Ground contact under a wheeled subject (critique r4 #1): a pressed-soil patch (dry_ground_01 dirt showing
    through on the tyre patches alone, broken by noise, following each tyre's dip - round 13) and the
    layout's flattened dead stems lying on it. Static, neither ground nor foliage. None without wheels."""
    import numpy as np
    from engine.blender import env_assets as E
    from engine.blender import set_parts as P
    from engine.blender.realism_rig import write_attr
    from engine.worlds import field_layout as FL
    stems = lay.get("trample") or []
    if not stems:
        return []
    zones = FL.tyre_zones(ctx.profile)
    dips = FL.tyre_dips(ctx.profile)
    cx, cy = lay["centre"]
    hx, hy = lay["footprint"]
    out = []
    # the soil patch: a 4 cm grid, mask 1 on the tyre patches only (round 13), following the dipped ground
    ex, ey = hx + SOIL_PAD_M, hy + SOIL_PAD_M
    nx, ny = max(2, int(2 * ex / 0.04)), max(2, int(2 * ey / 0.04))
    v, f, mask = [], [], []
    for i in range(nx + 1):
        for j in range(ny + 1):
            x, y = cx - ex + 2 * ex * i / nx, cy - ey + 2 * ey * j / ny
            # round 13 (owner's r12 review: "the bare dirt strip under the front bumper"): soil shows only where a tyre
            # pressed it (was also 0.75 under and round the whole body); it follows the tyre's dip
            tyre = max(0.0, 1.0 - FL._zone_dist(x, y, zones) / (SOIL_TYRE_K * FL.TRAMPLE_RAMP_M)) if zones else 0.0
            v.append((x, y, 0.0015 + FL.ground_dz(x, y, dips, ctx.seed)))
            mask.append(tyre)
    for i in range(nx):
        for j in range(ny):
            q = i * (ny + 1) + j
            f.append((q, q + ny + 1, q + ny + 2, q + 1))
    photo = all(lib["dirt"].values())
    m = (E.pbr("valora_field_pressed_soil", lib["dirt"], DIRT_TILE_M, tint=(0.62, 0.55, 0.46), rough_min=0.85)
         if photo else P.mat("valora_field_pressed_soil", DIRT_RGB, 0.9))
    nt = m.node_tree
    out_n = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    surf = next(l for l in nt.links if l.to_socket == out_n.inputs["Surface"]).from_socket
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = "valora_press"
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 9.0                     # ~10 cm breakup of the soil's edge
    nz.inputs["Detail"].default_value = 6.0
    nt.links.new(geo.outputs["Position"], nz.inputs["Vector"])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nt.links.new(at.outputs["Fac"], mul.inputs[0])
    nt.links.new(nz.outputs["Fac"], mul.inputs[1])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = 0.22, 0.38
    nt.links.new(mul.outputs[0], mr.inputs["Value"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mx = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(mr.outputs["Result"], mx.inputs["Fac"])
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(surf, mx.inputs[2])
    nt.links.new(mx.outputs[0], out_n.inputs["Surface"])
    soil = P.mesh(ctx.scene, "valora_field_pressed_soil", BLOCK, v, f, [m])
    write_attr(soil, "valora_press", np.asarray(mask, np.float32), "FLOAT")
    soil.visible_shadow = False
    out.append(soil)
    # the flattened stems: thin strips lying on the soil, arched a few millimetres, pointing away from the centre
    v, f, tint = [], [], []
    for x, y, yaw, length, pick in stems:
        a = math.radians(yaw)
        dx, dy = math.cos(a), math.sin(a)
        wx, wy = -dy * PRESSED_W / 2, dx * PRESSED_W / 2
        arch = 0.002 + 0.008 * ((pick * 7.31) % 1.0)
        k = len(v)
        for t in (0.0, 0.35, 0.7, 1.0):
            px, py = x + dx * length * t, y + dy * length * t
            z = 0.002 + arch * math.sin(math.pi * t) + FL.ground_dz(px, py, dips, ctx.seed)
            taper = 1.0 - 0.8 * t
            v += [(px - wx * taper, py - wy * taper, z), (px + wx * taper, py + wy * taper, z)]
            tint += [pick, pick]
        for r in range(3):
            q = k + 2 * r
            f.append((q, q + 1, q + 3, q + 2))
    sm = bpy.data.materials.new("valora_field_pressed_stems")
    sm.use_nodes = True
    snt = sm.node_tree
    sh = next(n for n in snt.nodes if n.type == "BSDF_PRINCIPLED")
    sh.inputs["Roughness"].default_value = 0.8
    ta = snt.nodes.new("ShaderNodeAttribute")
    ta.attribute_name = E.TINT_ATTR
    ramp = snt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*PRESSED_RGB[0], 1.0)
    ramp.color_ramp.elements[1].color = (*PRESSED_RGB[1], 1.0)
    snt.links.new(ta.outputs["Fac"], ramp.inputs["Fac"])
    snt.links.new(ramp.outputs["Color"], sh.inputs["Base Color"])
    ob = P.mesh(ctx.scene, "valora_field_pressed_stems", BLOCK, v, f, [sm])
    write_attr(ob, E.TINT_ATTR, np.asarray(tint, np.float32), "FLOAT")
    out.append(ob)
    return out


def build(ctx):
    import bpy
    from engine.blender import env_assets as E
    from engine.blender import set_parts as P
    from engine.color import kelvin_to_rgb
    from engine.worlds.field_layout import layout
    p, prof = ctx.params, ctx.profile
    tod, crop = p["timeOfDay"], p["crop"]
    el, kelvin, strength, angle, _ = SUN[tod]
    sun_dir = _sun_vector(ctx, float(p["sunAzimuthDeg"]), el, tod)
    lay = layout(prof, ctx.seed, float(p["grassHeightM"]), crop, bool(p["track"]),
                 cameras=[tuple(c) for c in ctx.camera_positions],
                 hero=tuple(ctx.hero_pose.position) if ctx.hero_pose is not None else None,
                 sun=None if tod == "overcast" else tuple(sun_dir))   # the trees never shade a low sun's subject
    lib = _library()
    hdri = lib["hdri"][tod]
    cx, cy = lay["centre"]
    name, tint, sky_k = HDRI[tod]
    if hdri is not None:
        sky_rot = E.rotation_for(HDRI_SUN_AZ[name], sun_dir)
        _horizon_glow(E.world_hdri(ctx.scene, "valora_field_sky", hdri, sky_rot, sky_k, tint), tod, sun_dir)
    else:
        sky_rot = _sky(bpy, ctx, tod, sun_dir)

    e = lay["extent"] / 2
    photo = all(lib["ground"].values())
    gmat = (_photo_ground(bpy, lib["ground"], lib["green"], crop, tod) if photo
            else _ground_mat(bpy, "valora_field_ground", crop))
    gv, gf = _ground_mesh(lay, e, ctx.profile, ctx.seed)       # round 13: each tyre sits in its own dip
    ground = P.mesh(ctx.scene, "valora_field_ground", BLOCK, gv, gf, [gmat])
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
    trees = _trees(bpy, ctx, lay, lib["trees"], HAZE[tod], sky_k, sky)
    flora = _flora(bpy, ctx, lay, lib)
    pressed = _pressed(bpy, ctx, lay, lib)
    boundary = _boundary(bpy, ctx, HAZE[tod], sky_k, sky)
    layers = _horizon_layers(bpy, ctx, HAZE[tod], sky_k, sky)
    under = 0
    if getattr(prof, "wheels", None):
        plant_mats = list(blades.data.materials) if blades is not None else []
        for ob in [*pressed, *flora.values()]:
            plant_mats += list(ob.data.materials) if ob.type == "MESH" else []
        under = _underbody(plant_mats, prof)

    ld = bpy.data.lights.new("valora_field_sun", "SUN")
    ld.energy, ld.color, ld.angle = strength, kelvin_to_rgb(kelvin), math.radians(angle)
    sun = bpy.data.objects.new("valora_field_sun", ld)
    ctx.scene.collection.objects.link(sun)
    from mathutils import Vector
    sun.rotation_euler = Vector([-c for c in sun_dir]).to_track_quat("-Z", "Y").to_euler()   # shines along -Z
    P.tag(sun, BLOCK)
    sun["valora_world_sun"] = True
    sun["valora_world_sun_k"] = kelvin                        # hard_sun's rim takes the sun's own colour
    sun["valora_world_sun_soft"] = tod == "overcast"          # hard_sun keeps an overcast sun soft (chunk 4 #6)

    ctx.scene["valora_field"] = {
        "timeOfDay": tod, "crop": crop, "extent": lay["extent"], "bladeRadius": lay["bladeRadius"],
        "blades": len(lay["blades"]), "bladeRootSwayMax": float(root_sway), "track": lay["track"] is not None,
        "clearing": dict(lay["clearing"]), "sun": {"elevationDeg": el, "azimuthDeg": float(p["sunAzimuthDeg"]),
                                                   "kelvin": kelvin, "strength": strength, "angleDeg": angle,
                                                   "direction": list(sun_dir), "skyRotationDeg": sky_rot},
        "sunObject": sun.name, "sightCut": lay["sightCut"], "hdri": hdri is not None, "photoGround": photo,
        "tufts": n_tufts, "tuftLods": list(ctx.scene.get("valora_field_tuft_lods", [0, 0, 0])), "trees": len(trees), "farMeadow": far is not None, "farGrass": far_grass is not None, "flora": sorted(flora),
        "horizonRing": horizon is not None, "boundaryProps": len(boundary), "horizonLayers": len(layers), "underbodyShaded": under, "pressedStems": len(lay.get("trample") or []) if pressed else 0,
        "foliageVerts": len(blades.data.vertices) if blades is not None else 0}
    return ground
