"""sparks build: the same node group with no emitter and no proxy, reading the bake's disk cache only (the zone
never simulates in a compile: SimInCompile). A missing cache raises BakeMissing."""
from pathlib import Path

from engine.bake.run import BakeMissing


def build(ctx):
    from engine.blender import gn_sim as G
    from engine.blender import particle_pack as B
    b = ctx.bake
    if not b or not (Path(b["dir"]) / "meta").is_dir():
        raise BakeMissing(f"sparks: no GN cache in {b and b['dir']}")
    G.sim_object("valora_sim_sparks", B.sparks_group(None, None, ctx.params["timeScale"], ctx.scene.render.fps), b["dir"], b["frames"],
                 "sim/sparks")
