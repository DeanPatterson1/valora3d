"""Freeze the phase-3 quality baseline (plan Task 34). Two frozen files, both produced by PHASE-3 code:

- phase3_tiers.json: every eval subject x prompt x seed through the pipeline with a refusing provider (so
  the fallback, no API call): the script-level tier, the direction id, the duration and the shot count.
- phase3_t2_refs.json: genuine T2 reference cases. The provider replies, every call, with a weak but valid
  script (engine/tests/fixtures/script_valid.json: too few shots for its length), so the pipeline delivers
  its best LLM script at T2. These exist so a T2 -> T1 drop is exercised; the fallback cases are all T3.

The quality floor and the harness compare against these files, so 'never worse than phase 3' does not
drift as the code changes. The generator only runs phase-3 code: either HEAD is PINNED_REV with a clean
tracked tree, or --rev REV builds inside a temporary `git worktree` of that revision (no junctions; the
worktree is removed afterwards). The revision used is recorded in frozenAt."""
import argparse
import functools
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).with_name("baseline") / "phase3_tiers.json"
T2_REFS = Path(__file__).with_name("baseline") / "phase3_t2_refs.json"
PINNED_REV = "93f11fc91c5ee9ec243124b48db95c98f04f23eb"   # the phase-3 code the baseline was frozen from
MODELS = ("camera_01", "cesium_man", "flighthelmet", "mid_century_lounge_chair", "pocket_watch", "sneaker",
          "sports_car", "toycar", "vintage_microscope")
PROMPTS = ("", "luxury")
SEEDS = (0, 1, 2, 3, 4)
WEAK_REPLY = Path("engine/tests/fixtures/script_valid.json")   # relative to the repo being built
T2_MODELS, T2_PROMPTS, T2_SEEDS = ("pocket_watch", "sports_car", "cesium_man"), ("",), (0, 1)
_RANK = {"T1": 1, "T2": 2, "T3": 3}
_EMIT = "@@valora-baseline@@"


def profile_key(profile):
    """Same formula as engine.director.variety.subject_key (Task 43 asserts they agree)."""
    return hashlib.sha256(json.dumps(profile.to_dict(), sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def content_sha(doc):
    """Hash of a frozen file's CONTENT (canonical JSON), independent of line endings and indentation."""
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _case(m, p, prompt, seed, r, cat, s_tier):
    return {"model": m, "subjectKey": profile_key(p), "prompt": prompt, "seed": seed,
            "tier": s_tier(r.script, p, cat), "directionId": r.script["direction"]["id"],
            "durationS": r.script["format"]["durationS"], "shots": len(r.script["shots"]),
            "scriptSha": hashlib.sha256(json.dumps(r.script, sort_keys=True).encode()).hexdigest()}


def build():
    from engine.catalog import Catalog
    from engine.director.llm import FakeProvider
    from engine.director.pipeline import direct
    from harness.director_eval import _profile, s_tier
    cat, cases = Catalog.load(), []
    for m in MODELS:
        p = _profile(m)
        for prompt in PROMPTS:
            for seed in SEEDS:
                r = direct(prompt, p, provider=FakeProvider([{"stop_reason": "refusal", "text": ""}] * 3),
                           seed=seed, catalog=cat)
                cases.append(_case(m, p, prompt, seed, r, cat, s_tier))
    return {"schema": "valora.baseline/1", "cases": cases}


def build_t2_refs():
    from engine.catalog import Catalog
    from engine.director.llm import FakeProvider
    from engine.director.pipeline import direct
    from harness.director_eval import _profile, s_tier
    reply = json.loads(WEAK_REPLY.read_text(encoding="utf-8"))
    cat, cases = Catalog.load(), []
    for m in T2_MODELS:
        p = _profile(m)
        for prompt in T2_PROMPTS:
            for seed in T2_SEEDS:
                r = direct(prompt, p, provider=FakeProvider([reply] * 3), seed=seed, catalog=cat)
                cases.append({**_case(m, p, prompt, seed, r, cat, s_tier), "source": r.source})
    return {"schema": "valora.baseline_t2/1", "provider": "weak_reply", "reply": str(WEAK_REPLY.as_posix()),
            "replySha": content_sha(reply), "cases": cases}


@functools.lru_cache(maxsize=1)
def _cases():
    try:
        return tuple(json.loads(BASELINE.read_text(encoding="utf-8"))["cases"])
    except (OSError, ValueError, KeyError):
        return ()


def baseline_case(model, prompt, seed):
    return next((c for c in _cases() if (c["model"], c["prompt"], c["seed"]) == (model, prompt, seed)), None)


def _git(*args, cwd=ROOT):
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd, check=True).stdout.strip()


def _emit(which):
    doc = build() if which == "tiers" else build_t2_refs()
    sys.stdout.write("\n" + _EMIT + json.dumps(doc) + "\n")


def _build_at(rev, which):
    """Run this generator inside a temporary worktree of `rev`, so only that revision's code runs."""
    sha = _git("rev-parse", "--verify", f"{rev}^{{commit}}")
    tmp = Path(tempfile.mkdtemp(prefix="valora-baseline-"))
    wt = tmp / "wt"
    _git("worktree", "add", "--detach", str(wt), sha)
    try:   # a plain checkout: nothing is junctioned in, so removing it cannot reach the main tree
        runner = wt / "_valora_baseline_runner.py"
        shutil.copyfile(__file__, runner)
        out = subprocess.run([sys.executable, str(runner), "--emit", which], capture_output=True, text=True,
                             cwd=wt, env={**_env(), "PYTHONPATH": str(wt)}, check=True).stdout
        doc = json.loads(out.rsplit(_EMIT, 1)[1])
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=ROOT, capture_output=True)
        subprocess.run(["git", "worktree", "prune"], cwd=ROOT, capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)
    return sha, doc


def _env():
    import os
    return dict(os.environ)


def _build_here(which):
    head = _git("rev-parse", "HEAD")
    if head != PINNED_REV:
        raise SystemExit(f"HEAD is {head[:12]}, not the pinned phase-3 revision {PINNED_REV[:12]}: "
                         f"pass --rev {PINNED_REV[:12]} to build in a temporary worktree")
    if _git("status", "--porcelain", "--untracked-files=no"):
        raise SystemExit("the working tree has uncommitted changes to tracked files: commit or use --rev")
    return head, (build() if which == "tiers" else build_t2_refs())


def tier_regressions(observed, frozen):
    """Paired regressions: observed rows whose tier is below the frozen tier of the SAME case (model,
    prompt, seed). Returns [(model, prompt, seed, frozen_tier, observed_tier)]; a case missing from the
    frozen file is not paired and not counted."""
    base = {(c["model"], c["prompt"], c["seed"]): c["tier"] for c in frozen}
    return [(o["model"], o["prompt"], o["seed"], base[k], o["tier"]) for o in observed
            if (k := (o["model"], o["prompt"], o["seed"])) in base and _RANK[o["tier"]] < _RANK[base[k]]]


def regression_gate(observed, frozen):
    """The gate: zero paired tier regressions, else a list of them."""
    reg = tier_regressions(observed, frozen)
    return not reg, reg


def main(argv=None):
    ap = argparse.ArgumentParser(prog="engine.director.baseline_phase3")
    ap.add_argument("--force", action="store_true", help="overwrite an existing frozen file (owner's OK)")
    ap.add_argument("--rev", help="build from this revision in a temporary git worktree")
    ap.add_argument("--which", choices=("tiers", "t2refs"), default="tiers")
    ap.add_argument("--out", type=Path, help="write here instead of the frozen path (e.g. to verify)")
    ap.add_argument("--emit", choices=("tiers", "t2refs"), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a.emit:
        _emit(a.emit)
        return 0
    out = a.out or (BASELINE if a.which == "tiers" else T2_REFS)
    if out.exists() and not a.force:
        raise SystemExit(f"{out.name} is frozen; regenerate only with --force and the owner's OK")
    sha, doc = _build_at(a.rev, a.which) if a.rev else _build_here(a.which)
    doc = {"schema": doc.pop("schema"), "frozenAt": sha, **doc}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1), encoding="utf-8", newline="\n")
    print(f"wrote {out} from {sha[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
