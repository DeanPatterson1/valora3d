"""hdri_only (phase 5 Task 72): the world's sky is the only light.

exposure scales every world Background strength by 2^exposure; negFill adds a matte black card beside the
subject (camera-invisible, casts no shadow) that deepens one side the way a flag does on location. No lights."""


def build(ctx):
    from engine.blender.lights import black_card, facts
    from engine.lighting import rigs as R
    p, prof = ctx.params, ctx.profile
    k = 2.0 ** float(p["exposure"])
    w = ctx.scene.world
    scaled = []
    if w is not None and w.node_tree is not None:
        for n in w.node_tree.nodes:
            if n.type == "BACKGROUND":
                n.inputs["Strength"].default_value *= k
                scaled.append(float(n.inputs["Strength"].default_value))
    card = R.neg_fill_card(prof, ctx.hero_pose.position, float(p["negFill"]))
    built = []
    if card is not None:
        ob = black_card(ctx.scene, card)
        ob["valora_block"] = "lighting/hdri_only"
        built.append(ob)
    ctx.scene["valora_lighting"] = {"block": "hdri_only", "exposureScale": k, "worldStrengths": scaled,
                                    "negFill": card is not None, "lights": facts(built)}
