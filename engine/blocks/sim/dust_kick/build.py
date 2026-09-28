"""dust_kick build: the same group with no emitter, reading the disk cache only (SimInCompile). A missing cache
raises BakeMissing."""
from pathlib import Path

from engine.bake.run import BakeMissing


def build(ctx):
    from engine.blender import gn_sim as G
    from engine.blender import road_spray as B
    b = ctx.bake
    if not b or not (Path(b["dir"]) / "meta").is_dir():
        raise BakeMissing(f"dust_kick: no GN cache in {b and b['dir']}")
    G.sim_object("valora_sim_dust_kick", B.group("dust", None, ctx.params["timeScale"]), b["dir"], b["frames"], "sim/dust_kick")
