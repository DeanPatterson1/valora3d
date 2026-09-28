"""Bake our own VDB smoke/fire library once from Mantaflow (phase 6 Task 111): CC0 by construction, so the 6+ GB
JangaFX download is optional. Presets live in engine/physics/gas.PRESETS.

    py tools/bake_vdb_library.py --preset all --owner-ok
    py tools/bake_vdb_library.py --preset plume_soft campfire

Each preset bakes in its own headless Blender under the machine bake lock (var/bake/.lock) with the gas
wall-time cap (engine/bake/run.BAKE_CAP_S), into assets-in/library/valora_vdb/<preset>/ (gitignored; the flat
fluid_data_####.vdb files only). Then its row is pinned in engine/assets/manifest.json: every file's sha256 and
bytes, their digest, and the native facts a player needs (size, baseM, fps, frames, grids, res, bake seconds).
Blocks that use the library build a procedural fallback when the files are missing, so no test needs them.

--owner-ok is required for more than one preset in one call (the plan's heavy-bake rule: about 1-3 h in total,
eng). Inside Blender this same file is the bake entry (`--blender-entry <preset> <out dir>`)."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT_ROOT = REPO / "assets-in" / "library" / "valora_vdb"


def _blender_entry(preset, out_dir):
    import bpy
    from engine.blender import gas as G
    from engine.physics import gas as P
    p = P.PRESETS[preset]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = P.LIBRARY_FPS, 1.0
    sc.frame_start, sc.frame_end = 1, p["frames"]
    sx, sy, sz = p["size"]
    lo, hi = (-sx / 2, -sy / 2, 0.0), (sx / 2, sy / 2, sz)
    dom = G.domain(f"valora_lib_{preset}", lo, hi, res=p["res"], frame_start=1, frame_end=p["frames"],
                   cache_dir=out_dir, vorticity=p["vorticity"], dissolve=p.get("dissolve"))
    for i, s in enumerate(p["sources"]):
        G.source(f"valora_lib_{preset}_src{i}", s["centre"], s["radius"], kind=s["kind"],
                 temperature=s["temperature"], density=s["density"], fuel=s.get("fuel", 1.0),
                 velocity=s.get("velocity"), frames=s.get("frames"), colour=p["colour"], depth=s.get("depth"))
    secs, files = G.bake(dom, sc)
    stats = G.density_stats(dom, [f for f in range(1, p["frames"] + 1, max(1, p["frames"] // 10))],
                            stride=max(1, p["res"] // 64))
    cells = stats[-1]["res"] if stats else None
    import os
    grids = []
    if files:
        v = bpy.data.volumes.new("probe")
        v.filepath = str(files[len(files) // 2])
        v.grids.load()
        grids = sorted(g.name for g in v.grids)
    rep = {"preset": preset, "bakeSeconds": round(secs, 2), "files": len(files), "grids": grids,
           "cells": cells, "stats": stats,
           "blender": bpy.app.version_string}
    Path(out_dir, "bake_report.json").write_text(json.dumps(rep), encoding="utf-8")
    print("LIB_REPORT " + json.dumps({k: rep[k] for k in ("preset", "bakeSeconds", "files", "grids", "cells")}),
          flush=True)


def pin_row(preset, lib_dir, report, manifest_path=None):
    """Write the preset's manifest row from the files now in lib_dir; returns the row."""
    import hashlib
    from engine import assets as A
    from engine.physics import gas as P
    manifest_path = Path(manifest_path or A.MANIFEST)
    p = P.PRESETS[preset]
    files = {}
    for f in sorted(Path(lib_dir).glob("fluid_data_*.vdb")):
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        files[f.name] = {"sha256": h, "bytes": f.stat().st_size}
    row = {"path": f"valora_vdb/{preset}", "files": files, "sha256": A.sequence_digest(files), "licence": "CC0-1.0",
           "source": "owned: Valora-baked from Mantaflow by tools/bake_vdb_library.py (engine/physics/gas.PRESETS), CC0",
           "credit": None,
           "native": {"sizeM": list(p["size"]), "widthM": max(p["size"][0], p["size"][1]),
                      "baseM": list(P.base_m(p["size"])), "fps": P.LIBRARY_FPS, "frames": len(files),
                      "res": p["res"], "cells": report.get("cells"), "grids": report.get("grids"),
                      "bakeSeconds": report.get("bakeSeconds"), "blender": report.get("blender"),
                      "use": p["use"]}}
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    doc["assets"][f"valora_vdb_{preset}"] = row
    doc["assets"] = dict(sorted(doc["assets"].items()))
    A.validate_manifest(doc)
    manifest_path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    return row


def bake_preset(preset, *, lock_timeout_s=7200, run=None, out_root=None, manifest_path=None):
    import shutil
    import subprocess
    import tempfile
    from engine.bake import run as R
    from engine.bake.lock import machine_lock
    from engine.blender_cli import blender_argv
    run = run or R.run_child
    target = Path(out_root or OUT_ROOT) / preset
    with machine_lock(timeout_s=lock_timeout_s):
        tmp = Path(tempfile.mkdtemp(prefix=f"vdb_{preset}_", dir=REPO / "var"))
        try:
            try:
                proc = run(blender_argv(Path(__file__), ["--blender-entry", preset, tmp]), text=True,
                           encoding="utf-8", errors="replace", timeout=R.BAKE_CAP_S["gas_vdb"])
            except subprocess.TimeoutExpired:
                raise R.BakeTimeout(f"bake_timeout: library preset {preset} ran past "
                                    f"{R.BAKE_CAP_S['gas_vdb']} s") from None
            rep_f = tmp / "bake_report.json"
            if proc.returncode != 0 or not rep_f.exists():
                raise R.BakeFailed(f"{preset}: exit {proc.returncode}\n{(proc.stdout or '')[-2000:]}\n"
                                   f"{(proc.stderr or '')[-2000:]}")
            report = json.loads(rep_f.read_text(encoding="utf-8"))
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True)
            for f in sorted((tmp / "data").glob("fluid_data_*.vdb")):
                shutil.move(str(f), target / f.name)
            (target / "bake_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    row = pin_row(preset, target, report, manifest_path)
    mb = sum(f["bytes"] for f in row["files"].values()) / 1e6
    print(f"{preset}: {report['bakeSeconds']} s, {len(row['files'])} files, {mb:.0f} MB, cells {report['cells']}",
          flush=True)
    return row


def main(argv=None):
    import argparse
    from engine.physics import gas as P
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--preset", nargs="+", required=True, help="preset names or 'all'")
    ap.add_argument("--owner-ok", action="store_true")
    a = ap.parse_args(argv)
    names = [n for n in P.PRESETS if not n.startswith("_")] if a.preset == ["all"] else a.preset
    for n in names:
        if n not in P.PRESETS:
            ap.error(f"unknown preset {n}; known: {', '.join(P.PRESETS)}")
    if len(names) > 1 and not a.owner_ok:
        ap.error("more than one preset is a heavy bake: pass --owner-ok")
    for n in names:
        bake_preset(n)
    return 0


if __name__ == "__main__":
    if "--blender-entry" in sys.argv:
        args = sys.argv[sys.argv.index("--blender-entry") + 1:]
        _blender_entry(args[0], args[1])
    else:
        sys.exit(main())
