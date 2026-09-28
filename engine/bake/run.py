"""Stage 4b BAKE, host side (phase 6 Task 98): between the checker and the compiler, every sim whose manifest
bakes (bake.method != "none") is simulated once in its own headless Blender (engine/bake/blender_bake.py) and
committed to the BakeStore under a content-addressed key. The compile only READS those caches (a sim's
build(ctx) gets ctx.bake), so the preview and the final render share one bake (METHODS R2, R9): the key never
contains the tier. A cache hit starts no Blender at all.

The key's env (engine/bake/key.bake_key): the sim's own seed (block_seed), the profile key, the model file's
sha256, the pinned Blender version, the sha256 of the block's bake.py + build.py + the engine modules its bake imports, the clip's fps, the wind ref,
the subject motion ref and the world ref (its ground). An upgraded Blender or an edited block is a new key, so a
stale cache is never reused."""
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from engine.bake.key import bake_key, sha256_file, sha256_files
from engine.bake.window import bake_frames_for
from engine.blender_pin import PINNED_BLENDER

BLENDER_BAKE = Path(__file__).with_name("blender_bake.py")
REPORT = "bake_report.json"


class BakeMissing(RuntimeError):
    """A compile asked for a bake that is not in the store (or failed its check). The compile never bakes."""


class SimInCompile(RuntimeError):
    """A compiled scene holds a live simulation (a rigid body world, CLOTH / FLUID, an unbaked sim zone)."""


class BakeFailed(RuntimeError):
    pass


@dataclass
class BakeJob:
    ref_id: str
    ref: dict
    method: str
    key: str
    frames: dict            # engine.bake.window.BakeFrames as a dict
    estimate_s: float
    proxies: list


def block_sha(catalog, bid):
    """sha256 over the sim block's bake.py, build.py and every engine module bake.py imports, transitively
    (engine/bake/deps.bake_sources): an edited block OR an edited helper (engine/blender/pieces.py, gn_sim.py,
    engine/physics/*) is a new key, with no hand-kept revision number to bump."""
    from engine.bake.deps import bake_sources
    return sha256_files(bake_sources(Path(catalog.root) / "sim" / bid))


def bake_env(script, profile, model_sha, catalog, ref):
    from engine.compiler.context import block_seed
    from engine.director.baseline_phase3 import profile_key
    return {"seed": block_seed(script["seed"], "sim", ref["id"]), "profileKey": profile_key(profile),
            "modelSha": model_sha, "blender": PINNED_BLENDER, "blockSha": block_sha(catalog, ref["id"]),
            "fps": script["format"]["fps"], "wind": script.get("wind"), "motion": script["subject"]["motion"],
            "ground": script["world"]}


def plan_bakes(script, profile, model, catalog, model_sha=None):
    """One BakeJob per sim ref of a CHECKED script whose block bakes; [] for a script without sims."""
    sims = [r for r in (script.get("sims") or []) if (catalog.get("sim", r["id"]) or {}).get("bake", {}).get("method", "none") != "none"]
    if not sims:
        return []
    model_sha = model_sha or sha256_file(model)
    jobs = []
    for ref in sims:
        b = catalog.get("sim", ref["id"])["bake"]
        fr = bake_frames_for(b["method"], ref["startS"], ref["endS"], script["format"]["fps"], b["prerollS"],
                             b["maxFrames"])
        key = bake_key(ref, bake_env(script, profile, model_sha, catalog, ref))
        jobs.append(BakeJob(ref["id"], ref, b["method"], key, asdict(fr), float(b["estimateS"]),
                            list(b.get("proxies", ["shell"]))))
    return jobs


def _entry(store, job, manifest, from_cache):
    return {"key": job.key, "dir": str(store.path(job.key)), "method": job.method, "frames": job.frames,
            "fromCache": from_cache, "bakeSeconds": manifest.get("bakeSeconds"),
            "bytes": sum(f["bytes"] for f in manifest["files"].values())}


def bake_sims(script, profile, model, *, catalog, store=None, budget=None, timeout_s=3600, lock_timeout_s=3600,
              verify="full", run=None, checked=False):
    """Check, plan, then bake every miss (one at a time on the machine, under the BakeBudget). Returns
    {sim id: {key, dir, method, frames, fromCache, bakeSeconds, bytes}}. `run` is subprocess.run (tests mock it)."""
    from engine.bake.lock import machine_lock
    from engine.bake.store import BakeStore, CacheCorrupt
    from engine.blender_cli import blender_argv
    from engine.checker import check
    from engine.issues import errors
    run = run or subprocess.run
    if checked:                                   # compile_scene passes the script its checker returned
        s = script
    else:
        r = check(script, profile, catalog)
        if not r.ok:
            raise ValueError("; ".join(f"{i.code} at {i.path}: {i.message}" for i in errors(r.issues)))
        s = r.script
    store = store or BakeStore()
    model_sha = sha256_file(model) if s.get("sims") else None
    jobs = plan_bakes(s, profile, model, catalog, model_sha=model_sha)
    out = {}
    for job in jobs:
        try:
            hit = store.read(job.key, verify=verify)
        except CacheCorrupt:
            store.delete(job.key)
            hit = None
        if hit is not None:
            out[job.ref_id] = _entry(store, job, hit, True)
            continue
        with machine_lock(timeout_s=lock_timeout_s):
            hit = store.read(job.key, verify="size")    # another process may have baked it while we waited
            if hit is not None:
                out[job.ref_id] = _entry(store, job, hit, True)
                continue
            if budget is not None:
                budget.reserve_s(job.estimate_s)          # reserved before the bake, never refunded
            with store.writer(job.key) as w:
                spec = {"script": s, "profile": profile.to_dict(), "model": str(Path(model).resolve()),
                        "catalogRoot": str(Path(catalog.root).resolve()), "ref": job.ref, "method": job.method,
                        "frames": job.frames, "dir": str(w.dir), "proxies": job.proxies,
                        "storeRoot": str(Path(store.root).resolve()), "modelSha": model_sha}
                jf = w.dir.parent / f"{w.dir.name}.job.json"
                jf.write_text(json.dumps(spec), encoding="utf-8")
                try:
                    proc = run(blender_argv(BLENDER_BAKE, [jf]), capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=timeout_s)
                finally:
                    jf.unlink(missing_ok=True)
                rep = w.dir / REPORT
                if proc.returncode != 0 or not rep.exists():
                    raise BakeFailed(f"bake of {job.ref_id} failed (exit {proc.returncode})\n"
                                     f"{(proc.stdout or '')[-2000:]}\n{(proc.stderr or '')[-2000:]}")
                report = json.loads(rep.read_text(encoding="utf-8"))
                rep.unlink()
                w.report({**report, "ref": job.ref, "method": job.method, "frames": job.frames})
        out[job.ref_id] = _entry(store, job, store.read(job.key, verify="size"), False)
    return out
