"""rigid_scatter build (phase 6 Task 100): reads keys.json from the bake only (never a rigid world:
SimInCompile). One object per baked piece, linked to the same procedural mesh + variant it was simulated with,
scaled by its baked jitter and keyed LINEAR (object motion blur) at render frame = bake frame + offset. Before
the window the pieces fall in on their baked velocity (pieces.key_pieces); after it they rest."""
import json
from pathlib import Path

from engine.bake.run import BakeMissing


def build(ctx):
    from engine.blender import pieces as P
    b = ctx.bake
    f = Path(b["dir"]) / "keys.json" if b else None
    if f is None or not f.is_file():
        raise BakeMissing(f"rigid_scatter: no keys.json in {b and b['dir']}")
    keys = json.loads(f.read_text(encoding="utf-8"))
    info = keys["info"]

    def one(name):
        return P.piece_object(ctx.scene, info["kind"], info["size"], info["variant"][name], name, "sim/rigid_scatter")
    P.key_pieces(ctx, keys, "sim/rigid_scatter", one)
