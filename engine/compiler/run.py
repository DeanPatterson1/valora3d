"""Host side of the compiler: check, write the job, run headless Blender, read the results.
A script that fails the checker never reaches Blender (spec §4.6)."""
import json
import subprocess
from pathlib import Path

from engine.blender_cli import blender_argv
from engine.catalog import Catalog
from engine.checker import check
from engine.paint import validate_paint
from engine.clips import swept_profile
from engine.compiler.timeline import key_frames
from engine.ingest.run import preflight
from engine.issues import errors

BLENDER_MAIN = Path(__file__).with_name("blender_main.py")


class CheckFailed(ValueError):
    pass


def _tail(text, n=2000):
    return (text or "").strip()[-n:] or "(empty)"


def compile_scene(script, profile, model, out_dir, *, tier="preview", frames="key", key_limit=None,
                  render=True, save_blend=False, build_blocks=True, skip_kinds=(), probe=None,
                  realism_probe=None, catalog=None, timeout_s=3600, paint=None):
    catalog = catalog or Catalog.load()
    r = check(script, profile, catalog)
    if not r.ok:
        raise CheckFailed("; ".join(f"{i.code} at {i.path}: {i.message}" for i in errors(r.issues)))
    preflight(model)
    from engine.world_assets import check_final_assets
    fallbacks = check_final_assets(r.script, tier)   # final: the world's photographic set or AssetMissing
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if frames == "key":
        frames = key_frames(r.script, limit=key_limit, catalog=catalog)
    profile = swept_profile(profile, r.script)   # the bounds the checker framed with (a walk's travel)
    job = {"script": r.script, "profile": profile.to_dict(), "model": str(Path(model).resolve()),
           "catalogRoot": str(Path(catalog.root).resolve()),  # Blender builds from the catalog the checker used
           "tier": tier, "frames": frames, "out": str(out.resolve()), "render": render,
           "saveBlend": save_blend, "buildBlocks": build_blocks, "skipKinds": list(skip_kinds),
           "probe": probe or [], "realismProbe": list(realism_probe or []),
           "paint": validate_paint(paint)}          # None: the upload's materials stay as they came
    (out / "job.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
    done = out / "compile.json"
    done.unlink(missing_ok=True)  # a previous run's result must never pass for this run's
    proc = subprocess.run(blender_argv(BLENDER_MAIN, [out / "job.json"]), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout_s)
    if proc.returncode != 0 or not done.exists():
        raise RuntimeError(f"Blender compile failed (exit {proc.returncode})\n"
                           f"--- stdout tail ---\n{_tail(proc.stdout)}\n--- stderr tail ---\n{_tail(proc.stderr)}")
    res = json.loads(done.read_text(encoding="utf-8"))
    res["assetFallbacks"] = fallbacks                # previews: which photographic assets fell back
    return res
