"""Variety score (spec §9): N runs of the same model + prompt. Report-only, except that paired tier
regressions must be 0. Per group:
- direction distance (mean and min pairwise) and script distance; near-duplicates; exact repeats;
- tierRegressions: runs whose [S] tier is below the FROZEN phase-3 tier for the same (model, prompt,
  seed) (baseline/phase3_tiers.json). Cases outside the fixture (other seeds, markers) compare with
  phase3_default, which Task 41 proves still reproduces the fixture. Paired per case, so a loss is never
  offset by a gain elsewhere;
- honesty: reachable() per run, with that run's own format, seed, markers, pins and viability;
- frameDistance: only with a renderer (a hard total of 3 frames per invocation, Task 49).
Each group gets a fresh temporary memory with one issued user token, so layer 3 runs as in production.
hold_direction=True keeps the first run's direction (more like this), so only layer 1 varies."""
import itertools
import json
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

from engine.catalog import Catalog
from engine.compiler.run import compile_scene
from engine.director.baseline_phase3 import baseline_case
from engine.director.direction import interim_direction, parse_id
from engine.director.distance import direction_distance, near_duplicate, script_distance
from engine.director.floor import _RANK, phase3_default, script_tier
from engine.director.job import make_job
from engine.director.llm import FakeProvider
from engine.director.memory import VarietyMemory
from engine.director.pipeline import direct
from engine.director.variety import reachable
from harness.director_eval import MODELS, _profile, _rate, load_prompt_set, markers_for

ROOT = Path(__file__).resolve().parents[1]
SUITE = json.loads((ROOT / "harness" / "suites" / "v0" / "suite.json").read_text(encoding="utf-8"))
MAX_FRAMES_TOTAL = 3     # owner rule: at most 3 rendered frames per invocation, on this PC
TIER = "keyframes"


def _img(path, size=(36, 64)):
    return np.asarray(Image.open(path).convert("RGB").resize(size, Image.BILINEAR), dtype=np.float64) / 255.0


def frame_distance(a, b):
    """0..1: half mean luminance difference of thumbnails, half colour-histogram distance."""
    A, B = _img(a), _img(b)
    lum = lambda x: x[..., 0] * 0.2126 + x[..., 1] * 0.7152 + x[..., 2] * 0.0722  # noqa: E731
    hist = lambda x: np.histogramdd(x.reshape(-1, 3), bins=(8, 8, 8), range=((0, 1),) * 3)[0].ravel() / (x.size / 3)  # noqa: E731
    return round(0.5 * float(np.abs(lum(A) - lum(B)).mean()) + 0.25 * float(np.abs(hist(A) - hist(B)).sum()), 4)


def make_renderer(out_root, budget=MAX_FRAMES_TOTAL):
    """One mid-clip frame per run until the invocation's total budget is spent. Each frame's budget is
    reserved BEFORE compile/render and never refunded, so a failed render cannot let a later group
    exceed the total. Groups after that get None (n/a). The budget can never exceed MAX_FRAMES_TOTAL."""
    if not 0 < budget <= MAX_FRAMES_TOTAL:
        raise ValueError(f"render budget must be 1..{MAX_FRAMES_TOTAL} frames per invocation")
    left = [budget]

    def render(model, profile, scripts):
        if left[0] < 2:                       # a distance needs at least two frames
            return None
        glb, frames = ROOT / SUITE["glb"].format(m=model), []
        for k, s in enumerate(scripts):
            if left[0] <= 0:
                break
            left[0] -= 1                      # RESERVE before rendering; never refunded, even on failure
            f = max(1, round(s["format"]["durationS"] * s["format"]["fps"] / 2))
            out = Path(out_root) / f"{model}__{k}"
            try:
                compile_scene(s, profile, glb, out, tier=TIER, frames=[f])
            except Exception:                 # noqa: BLE001 - the failed frame still used its reservation
                continue
            frames.append(out / "beauty" / f"{f:04d}.png")
        ds = [frame_distance(a, b) for a, b in itertools.combinations(frames, 2)]
        return sum(ds) / len(ds) if ds else None
    return render


def _refuse(cid):
    return FakeProvider([{"stop_reason": "refusal", "text": ""}] * 3)


def _pairs(xs, f):
    return [f(a, b) for a, b in itertools.combinations(xs, 2)]


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def run_group(model, case, sets, *, runs, memory, seed_base, factory, catalog, render=None, hold_direction=False):
    profile = _profile(model)
    spec = sets.get(case.get("markers")) if case.get("markers") else None
    markers = markers_for(spec, profile) if spec else None
    res = []
    with tempfile.TemporaryDirectory() as tmp:
        mem = VarietyMemory(tmp, dev=True) if memory else None     # throwaway key in the temp root
        user = mem.issue_user_token() if mem else None
        for k in range(runs):
            like = res[0].script if hold_direction and res else None
            res.append(direct(case["prompt"], profile, provider=factory(f"{model}__{case['id']}__{k}"),
                              seed=seed_base + k, markers=markers, catalog=catalog, memory=mem, user=user, like=like))
    scripts = [r.script for r in res]
    tiers = [script_tier(s, profile, catalog) for s in scripts]
    jobs = [make_job(case["prompt"], profile, catalog, seed=seed_base + k, markers=markers,
                     duration=s["format"]["durationS"], direction=interim_direction(seed_base + k, profile, catalog))
            for k, s in enumerate(scripts)]
    btiers, bsource = [], []
    for k, j in enumerate(jobs):                  # the FROZEN phase-3 tier when this case was frozen
        fz = baseline_case(model, case["prompt"], seed_base + k) if not markers else None
        btiers.append(fz["tier"] if fz else script_tier(phase3_default(j, profile, catalog), profile, catalog))
        bsource.append("frozen" if fz else "phase3_default")
    dd = _pairs([parse_id(s["direction"]["id"]) for s in scripts], direction_distance)
    sd = _pairs(scripts, lambda a, b: script_distance(a, b, catalog))
    row = {"model": model, "prompt": case["id"], "runs": runs, "memory": memory, "holdDirection": hold_direction,
           "directions": [r.direction for r in res],
           "meanDirectionDistance": _mean(dd), "minDirectionDistance": min(dd) if dd else None,
           "meanScriptDistance": _mean(sd),
           "nearDuplicates": sum(near_duplicate(a, b, catalog) for a, b in itertools.combinations(scripts, 2)),
           "exactRepeats": runs - len({s["direction"]["id"] for s in scripts}),
           "tiers": tiers, "baselineTiers": btiers, "baselineSource": bsource,
           "tierRegressions": sum(_RANK[t] < _RANK[b] for t, b in zip(tiers, btiers)),
           "honesty": [{"seed": seed_base + k, "format": s["format"],
                        **reachable(profile, catalog, s["format"],
                                    job=make_job(case["prompt"], profile, catalog, seed=seed_base + k, markers=markers,
                                                 duration=s["format"]["durationS"]), prompt=case["prompt"])}
                       for k, s in enumerate(scripts)],
           "frameDistance": None}
    if render is not None:
        row["frameDistance"] = render(model, profile, scripts)
    return row


def run_variety(prompt_set="v1", models=None, prompt_ids=None, runs=5, memory=True, provider_factory=None,
                out_root="harness/out/variety", run_id=None, seed_base=0, render=None, hold_direction=False):
    """seed_base 0: runs 0-4 of the '' and 'luxury' prompts hit the frozen phase-3 fixture exactly."""
    prompts, sets = load_prompt_set(prompt_set)
    prompts = [p for p in prompts if not prompt_ids or p["id"] in prompt_ids]
    catalog, factory = Catalog.load(), provider_factory or _refuse
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    run_dir = Path(out_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    groups = []
    for model in models or MODELS:
        for case in prompts:
            try:
                groups.append(run_group(model, case, sets, runs=runs, memory=memory, seed_base=seed_base,
                                        factory=factory, catalog=catalog, render=render,
                                        hold_direction=hold_direction))
            except Exception as e:  # noqa: BLE001 - recorded, never skipped
                groups.append({"model": model, "prompt": case["id"], "error": f"{type(e).__name__}: {e}"})
    ok = [g for g in groups if "error" not in g]
    metrics = {"groups": len(ok), "errors": len(groups) - len(ok),
               "tierRegressions": sum(g["tierRegressions"] for g in ok),
               "meanDirectionDistance": _rate([g["meanDirectionDistance"] for g in ok]),
               "minDirectionDistance": _rate([g["minDirectionDistance"] for g in ok]),
               "meanScriptDistance": _rate([g["meanScriptDistance"] for g in ok]),
               "nearDuplicates": _rate([g["nearDuplicates"] for g in ok]),
               "exactRepeats": _rate([g["exactRepeats"] for g in ok]),
               "frameDistance": _rate([g["frameDistance"] for g in ok]),
               "singleValuedAxes": sorted({a for g in ok for h in g["honesty"] for a in h["singleValued"]})}
    summary = {"promptSet": prompt_set, "runId": run_id, "runs": runs, "memory": memory,
               "holdDirection": hold_direction, "metrics": metrics, "groups": groups}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    (run_dir / "summary.md").write_text(_md(summary), encoding="utf-8")
    return summary


def _f(v, spec=".3f"):
    return "n/a" if v is None else format(v, spec)


def _md(s):
    m = s["metrics"]
    rate = lambda r: f"{_f(r['value'])} (n={r['n']})"  # noqa: E731
    lines = [f"# Variety score {s['runId']} ({s['promptSet']}, {s['runs']} runs, memory {'on' if s['memory'] else 'off'}"
             f"{', direction held' if s['holdDirection'] else ''})", "",
             "Report-only. Distances 0..1. Tier regressions are paired per case against the no-dice run and must be 0.", "",
             f"- **Tier regressions: {m['tierRegressions']}**",
             f"- Direction distance mean {rate(m['meanDirectionDistance'])}, min {rate(m['minDirectionDistance'])}",
             f"- Script distance mean {rate(m['meanScriptDistance'])}; near-duplicate pairs {rate(m['nearDuplicates'])}",
             f"- Exact repeats {rate(m['exactRepeats'])}; frame distance {rate(m['frameDistance'])} (render only)",
             f"- Axes with one value somewhere (catalog honesty): {', '.join(m['singleValuedAxes']) or 'none'}",
             "", "| model | prompt | dir dist | script dist | repeats | near dups | tier regressions | viable |",
             "|---|---|---|---|---|---|---|---|"]
    for g in s["groups"]:
        if "error" in g:
            lines.append(f"| {g['model']} | {g['prompt']} | ERROR {g['error'][:80]} | | | | | |")
        else:
            lines.append(f"| {g['model']} | {g['prompt']} | {_f(g['meanDirectionDistance'])} | "
                         f"{_f(g['meanScriptDistance'])} | {g['exactRepeats']} | {g['nearDuplicates']} | "
                         f"{g['tierRegressions']} | {min((h.get('viable', 0) for h in g['honesty']), default='n/a')} |")
    return "\n".join(lines) + "\n"
