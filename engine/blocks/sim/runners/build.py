"""runners: read the baked GN cache (ctx.bake) only. The zone is set to the bake's directory and absolute frame
range, so it never simulates (SimInCompile passes); a missing cache raises BakeMissing."""
from pathlib import Path

from engine.bake.run import BakeMissing


def build(ctx):
    from engine.blender import gn_sim as G
    from engine.blender import runners as BR
    b = ctx.bake
    if not b or not Path(b["dir"]).is_dir():
        raise BakeMissing(f"runners: no cache in {b and b['dir']}")
    ob = G.sim_object("valora_runners", BR.ensure(ctx, None), b["dir"], b["frames"], "sim/runners")
    ob.visible_shadow = False      # without caustics a clear drop's shadow is a dark speck
