"""py -m harness look --script <path> --profile <name> [--frames N] [--at t,...] [--dry-run]

The budgeted look-check (plan Task 91). Owner rule: at most 3 rendered frames per invocation, RESERVED from a
RenderBudget before anything compiles and never refunded (a crash cannot free budget for a retry loop). It
compiles at the preview tier, renders exactly those frames, and writes the PNGs plus look.json (script sha,
frame times, GPU-seconds) under harness/out/look/<sha>/. --dry-run prints the frames and renders nothing: CI
and the tests use it."""
import hashlib
import json
from pathlib import Path

from engine.compiler.run import compile_scene
from harness.budget import MAX_FRAMES_TOTAL, BakeBudget, BudgetExceeded, RenderBudget
from harness.director_eval import _profile

ROOT = Path(__file__).resolve().parents[1]
SUITE = json.loads((ROOT / "harness" / "suites" / "v0" / "suite.json").read_text(encoding="utf-8"))
TIER = "preview"
OUT_ROOT = ROOT / "harness" / "out" / "look"
LAST_BUDGET = None      # the last invocation's budget (tests read it; one CLI call = one budget)
LAST_BAKE_BUDGET = None


def _default_times(fmt, n):
    """N times spread over the clip's inner span (never the first or the last frame): n = 1 -> mid-clip."""
    dur = fmt["durationS"]
    return [round(dur * (k + 1) / (n + 1), 3) for k in range(n)]


def _sim_times(script, n):
    """A script with sims: before, peak and settled of the first sim's window (its start, its midpoint, its end
    minus 0.2 s), from the same bake; one frame -> the peak, two -> before and settled."""
    ref = script["sims"][0]
    dur = script["format"]["durationS"]
    a, b = max(0.0, float(ref["startS"])), min(float(ref["endS"]), dur)
    last = min(max(a, b - 0.2), dur - 1.0 / script["format"]["fps"])
    trio = [round(a, 3), round((a + b) / 2, 3), round(last, 3)]
    return {1: [trio[1]], 2: [trio[0], trio[2]]}.get(n, trio)[:n]


def frame_of(t, fps):
    """The 1-based Blender frame showing time t (blender_main: frame = round(t * fps) + 1)."""
    return int(round(t * fps)) + 1


def run_look(script_path, profile_name, frames=1, at=None, dry_run=False, out_root=None, owner_ok=False):
    """A script with sims bakes first (stage 4b, inside compile_scene) under its own BakeBudget: a heavy bake
    over MAX_BAKE_MIN needs owner_ok. The render budget is untouched by the bake."""
    global LAST_BUDGET, LAST_BAKE_BUDGET
    if type(frames) is not int or frames < 1:
        raise ValueError("--frames must be a whole number >= 1")
    if frames > MAX_FRAMES_TOTAL:
        raise BudgetExceeded(f"{frames} frames > {MAX_FRAMES_TOTAL} per invocation (larger strips are owner-gated)")
    raw = Path(script_path).read_bytes()
    script = json.loads(raw.decode("utf-8"))
    sha = hashlib.sha256(raw).hexdigest()
    fmt = script["format"]
    times = [float(t) for t in at] if at else (_sim_times(script, frames) if script.get("sims")
                                                else _default_times(fmt, frames))
    if len(times) != frames:
        raise ValueError(f"--at lists {len(times)} times for --frames {frames}")
    if any(not 0 <= t < fmt["durationS"] for t in times):
        raise ValueError(f"every --at time must be inside the clip [0, {fmt['durationS']}) s")
    nums = [frame_of(t, fmt["fps"]) for t in times]
    out = Path(out_root or OUT_ROOT) / sha[:16]
    plan = {"scriptSha": sha, "profile": profile_name, "tier": TIER, "times": times, "frames": nums,
            "out": str(out), "dryRun": dry_run}
    if dry_run:
        return plan
    LAST_BUDGET = budget = RenderBudget(MAX_FRAMES_TOTAL)
    budget.reserve(frames)                     # BEFORE compiling; never refunded, even on failure
    profile = _profile(profile_name)
    glb = ROOT / SUITE["glb"].format(m=profile_name)
    LAST_BAKE_BUDGET = bake_budget = BakeBudget(owner_ok=owner_ok)
    res = compile_scene(script, profile, glb, out, tier=TIER, frames=nums, bake_budget=bake_budget)
    log = res.get("renderLog") or {}
    pngs = [str(out / "beauty" / f"{f:04d}.png") for f in nums]
    meta = {**plan, "pngs": pngs, "gpuSeconds": log.get("totalSeconds"), "device": log.get("device"),
            "assetFallbacks": res.get("assetFallbacks", [])}
    if res.get("bakes"):                       # PH-11: bake seconds and cache bytes per sim, apart from GPU seconds
        meta["bakes"] = {k: {x: v.get(x) for x in ("key", "fromCache", "bakeSeconds", "bytes")}
                         for k, v in res["bakes"].items()}
    (out / "look.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta
