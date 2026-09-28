"""bubbles build: the drink (a water cylinder inside the container, floor to fill line) and the same group with no
emitter, reading the disk cache only (SimInCompile). A missing cache raises BakeMissing."""
import importlib.util
from pathlib import Path

from engine.bake.run import BakeMissing


def _bake_mod():
    spec = importlib.util.spec_from_file_location("bubbles_bake", Path(__file__).with_name("bake.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def build(ctx):
    from engine.blender import gn_sim as G
    from engine.blender import particle_pack as B
    b = ctx.bake
    if not b or not (Path(b["dir"]) / "meta").is_dir():
        raise BakeMissing(f"bubbles: no GN cache in {b and b['dir']}")
    c, z0, z1 = _bake_mod()._region(ctx)
    B.drink("valora_sim_bubbles_drink", c["opening"], c["radiusM"], z0, z1, "sim/bubbles")
    G.sim_object("valora_sim_bubbles", B.bubbles_group(None, ctx.params["timeScale"]), b["dir"], b["frames"],
                 "sim/bubbles")
