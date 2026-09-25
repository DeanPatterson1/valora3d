"""rim_neon (phase 5 Task 72): two coloured neon rims and a low cool fill.

The rims' hues are the world's neonHue (night_street) split by hueSplit, else the manifest's default hue; they
are area strips either side behind the subject and light the set too (their colour on wet asphalt is the
point). The low cool fill lights the subject only. The world's practicals are never touched."""
DEFAULT_HUE = 285.0         # night_street's neonHue default, for a world without one
FILL_K = 7000.0             # (eng) the cool fill


def build(ctx):
    from engine.blender.lights import area_light, facts, link_to
    from engine.blender.set_parts import hue_rgb
    from engine.lighting import rigs as R
    p, prof = ctx.params, ctx.profile
    world_hue = float((ctx.script["world"].get("params") or {}).get("neonHue", DEFAULT_HUE))
    hues = R.neon_hues(world_hue, float(p["hueSplit"]))
    a, b, fill = R.rim_neon_layout(prof, ctx.hero_pose.position, p)
    lights = []
    for spec, hue in ((a, hues[0]), (b, hues[1])):
        lo = area_light(ctx.scene, spec, 6500.0)
        lo.data.color = hue_rgb(hue)
        lo["valora_block"] = "lighting/rim_neon"
        lights.append(lo)
    f = area_light(ctx.scene, fill, FILL_K)
    f["valora_block"] = "lighting/rim_neon"
    link_to(ctx.meshes, [f], "valora_rim_neon_receivers")
    ctx.scene["valora_lighting"] = {"block": "rim_neon", "hues": list(hues), "worldHue": world_hue,
                                    "lights": facts([*lights, f])}
