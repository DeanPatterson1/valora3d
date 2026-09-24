"""Host side of the compiler: check, write the job, run headless Blender, read the results.
A script that fails the checker never reaches Blender (spec §4.6)."""
import json
import subprocess
from pathlib import Path

from engine.blender_cli import blender_argv
from engine.catalog import Catalog
from engine.checker import check
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
                  catalog=None, timeout_s=3600):
    r = check(script, profile, catalog or Catalog.load())
    if not r.ok:
        raise CheckFailed("; ".join(f"{i.code} at {i.path}: {i.message}" for i in errors(r.issues)))
    preflight(model)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if frames == "key":
        frames = key_frames(r.script, limit=key_limit)
    job = {"script": r.script, "profile": profile.to_dict(), "model": str(Path(model).resolve()),
           "tier": tier, "frames": frames, "out": str(out.resolve()), "render": render,
           "saveBlend": save_blend, "buildBlocks": build_blocks, "skipKinds": list(skip_kinds),
           "probe": probe or []}
    (out / "job.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
    proc = subprocess.run(blender_argv(BLENDER_MAIN, [out / "job.json"]), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout_s)
    done = out / "compile.json"
    if proc.returncode != 0 or not done.exists():
        raise RuntimeError(f"Blender compile failed (exit {proc.returncode})\n"
                           f"--- stdout tail ---\n{_tail(proc.stdout)}\n--- stderr tail ---\n{_tail(proc.stderr)}")
    return json.loads(done.read_text(encoding="utf-8"))
