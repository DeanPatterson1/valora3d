"""lens_drops: rain drops on the lens for one shot (M-COMP; plan Task 68).

The compositor is built after the camera and the grade, so this build only records what to add: the shot's
frame range, the amount and the seed (scene valora_fx_lens_drops). engine/blender/lens_drops.apply inserts
the optical stage right after the render layers (before the grade): a seeded Voronoi bead field over the frame
displaces and softly blurs the image inside each bead, mixed in by a factor keyed 0 / amount / 0 at the shot's
cut subframes with constant interpolation, so no other shot's exposure ever sees a drop (cuts sit in the
closed-shutter gap, compiler/timeline)."""


def build(ctx):
    k = int(round(ctx.params["shot"]))
    fps = ctx.script["format"]["fps"]
    sh = ctx.script["shots"][k]
    first, last = int(round(sh["startS"] * fps)) + 1, int(round(sh["endS"] * fps))
    ctx.scene["valora_fx_lens_drops"] = {"shot": k, "first": first, "last": last,
                                         "amount": float(ctx.params["amount"]), "seed": int(ctx.seed % 997)}
    return None
