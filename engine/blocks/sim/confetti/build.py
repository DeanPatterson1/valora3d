"""confetti build: the same group (cards instanced after the zone) with no emitter and no proxy, reading the disk
cache only (SimInCompile). A missing cache raises BakeMissing."""
from pathlib import Path

from engine.bake.run import BakeMissing


def build(ctx):
    from engine.blender import gn_sim as G
    from engine.blender import particle_pack as B
    b = ctx.bake
    if not b or not (Path(b["dir"]) / "meta").is_dir():
        raise BakeMissing(f"confetti: no GN cache in {b and b['dir']}")
    G.sim_object("valora_sim_confetti", B.confetti_group(None, None, ctx.params["timeScale"]), b["dir"], b["frames"],
                 "sim/confetti")
