"""hdri_only (phase 5 Task 72): the world's sky is the only light.

exposure meters the whole frame by 2^exposure the way a camera does: it is added to the grade's compositor
exposure (scene["valora_meter_ev"], read by engine/blender/grade.realise, or the view exposure when the grade is
skipped), so the sky, a world's sun, its practicals and its emissive backplates all move together (realism audit
#6: scaling only the World Background left the field's sun, the street's lamps and the courtyard's backplate at
their old level). negFill adds a matte black card beside the subject (camera-invisible, casts no shadow) that
deepens one side the way a flag does on location. No lights."""

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
        built.append(ob)
    ctx.scene["valora_lighting"] = {"block": "hdri_only", "exposureScale": 2.0 ** ev, "meterEv": ev,
                                    "worldStrengths": strengths, "negFill": card is not None, "lights": facts(built)}
