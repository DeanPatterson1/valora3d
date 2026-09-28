"""smoke_sim build: plays the baked OpenVDB sequence (ctx.bake["dir"]/data) on a Volume object whose VDB origin
(Mantaflow writes the domain's MIN corner at the origin) sits on the domain's lo corner, file 0001 at the render
frame of bake frame 1 (shift mode: render = bake + frames.offset), with the colour's Principled Volume. Reads the
cache only: no FLUID modifier reaches the compile (SimInCompile). A missing cache raises BakeMissing."""
from pathlib import Path

from engine.bake.run import BakeMissing

DENSITY = 3.0        # (eng, G10) Principled density x the grid at density 1


def build(ctx):
    from engine.blender import vdb as VB
    b = ctx.bake
    files = sorted((Path(b["dir"]) / "data").glob("fluid_data_*.vdb")) if b else []
    if not files:
        raise BakeMissing(f"smoke_sim: no VDB sequence in {b and b['dir']}")
    import importlib.util
    spec = importlib.util.spec_from_file_location("smoke_sim_bake", Path(__file__).with_name("bake.py"))
    bk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bk)
    rep = b.get("manifest") or {}
    if not rep.get("domain"):
        from engine.bake.store import BakeStore
        rep = BakeStore(Path(b["dir"]).parent).read(b["key"], verify="none") or {}
    lo = rep["domain"]["lo"]
    fr = b["frames"]
    mat = VB.volume_material("valora_sim_smoke_mat", color=bk.COLOURS[ctx.params["colour"]],
                             density=DENSITY * float(ctx.params["density"]))
    d = rep["domain"]
    voxel = max(h - l for l, h in zip(d["lo"], d["hi"])) / d["res"]
    seq = {"files": files, "native": {"widthM": 1.0, "baseM": [0.0, 0.0, 0.0], "voxelM": voxel}}
    return VB.place_vdb(seq, anchor=lo, start_frame=fr["bake_first"] + fr["offset"], name="valora_sim_smoke",
                        block="sim/smoke_sim", material=mat)
