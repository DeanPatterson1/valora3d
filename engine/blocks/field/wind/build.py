"""The wind field (TAXONOMY WD-01; METHODS §2.9). Records the params on the scene for Python consumers,
then builds the one shared wind from them (engine/blender/wind_field.py): the Geometry Nodes group
`valora_wind` (Position -> Wind, m/s) and the WIND force field `valora_wind_field` (hand-off H4).
Consumers call wind_field.ensure_wind_group, never their own noise."""


def build(ctx):
    from engine.blender.wind_field import ensure_force_field, ensure_wind_group
    p = ctx.params
    ctx.scene["valora_wind"] = {"directionDeg": p["directionDeg"], "speedMs": p["speedMs"],
                                "gustiness": p["gustiness"], "turbulence": p["turbulence"]}
    ensure_wind_group(p, ctx.seed)
    ensure_force_field(p, ctx.seed)
