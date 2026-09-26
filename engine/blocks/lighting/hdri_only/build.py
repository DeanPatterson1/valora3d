"""hdri_only (phase 5 Task 72): the world's sky is the only light.

exposure meters the whole frame by 2^exposure the way a camera does: it is added to the grade's compositor
exposure (scene["valora_meter_ev"], read by engine/blender/grade.realise, or the view exposure when the grade is
skipped), so the sky, a world's sun, its practicals and its emissive backplates all move together (realism audit
#6: scaling only the World Background left the field's sun, the street's lamps and the courtyard's backplate at
their old level). negFill adds a matte black card beside the subject (camera-invisible, casts no shadow) that
deepens one side the way a flag does on location.

Outdoors, every shot also gets the crew's per-set-up reflection shaping (critique mat-v2 #2,
engine/lighting/location_key): a 4 x 3 m soft key on camera-left, light-linked to the subject, and a dark flag
breaking the windshield's sky reflection; a close detail gets a 1.5 x 1 m source instead. The World is never
brightened. A studio keeps the sky alone."""
import os

METER_KEY = "valora_meter_ev"


def build(ctx):
    from engine.blender.lights import black_card, facts
    from engine.lighting import rigs as R
    p, prof = ctx.params, ctx.profile
    ev = float(p["exposure"])
    ctx.scene[METER_KEY] = float(ctx.scene.get(METER_KEY, 0.0)) + ev
    w = ctx.scene.world
    strengths = [float(n.inputs["Strength"].default_value) for n in (w.node_tree.nodes if w is not None and
                 w.node_tree is not None else ()) if n.type == "BACKGROUND"]
    card = R.neg_fill_card(prof, ctx.hero_pose.position, float(p["negFill"]))
    built = []
    if card is not None:
        ob = black_card(ctx.scene, card)
        ob["valora_block"] = "lighting/hdri_only"
        # it deepens the side by blocking sky to diffuse rays only: a flag seen in glossy rays showed as a tall
        # black rectangle in every puddle of a wet set (look-check real_rw_court_r2_az90)
        ob.visible_glossy = False
        built.append(ob)
    from engine.blender.lights import is_outdoor
    shaping = {}
    if is_outdoor(ctx) and ctx.camera_keys:
        from engine.blender.location_key import build as location_key
        w = os.environ.get("VALORA_LOCATION_KEY_W")          # look-check brackets only (300 / 600 / 900)
        dw = os.environ.get("VALORA_DETAIL_KEY_W")           # (40 / 80 / 120)
        objs, shaping = location_key(ctx, "lighting/hdri_only", watts=float(w) if w else None,
                                     detail_watts=float(dw) if dw else None)
        built += objs
    ctx.scene["valora_lighting"] = {"block": "hdri_only", "exposureScale": 2.0 ** ev, "meterEv": ev,
                                    "worldStrengths": strengths, "negFill": card is not None, "lights": facts(built),
                                    **({"shaping": shaping} if shaping else {})}


def finalize(ctx):
    """Water built on the subject after the lighting (droplets) catches the per-shot key too (round 6)."""
    from engine.blender.lights import is_outdoor
    if is_outdoor(ctx) and ctx.camera_keys:
        from engine.blender.location_key import link_weather
        link_weather(ctx.scene)
