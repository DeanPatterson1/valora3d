"""Freeze the phase-3 quality baseline (run ONCE, before phase-4 code; plan Task 34). For every eval
subject x prompt x seed, the phase-3 pipeline with a refusing provider (so the fallback, no API call):
the script-level tier, the direction id, the duration and the shot count. The quality floor and the
harness compare against this file, so 'never worse than phase 3' does not drift as the code changes."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).with_name("baseline") / "phase3_tiers.json"
MODELS = ("camera_01", "cesium_man", "flighthelmet", "mid_century_lounge_chair", "pocket_watch", "sneaker",
          "sports_car", "toycar", "vintage_microscope")
PROMPTS = ("", "luxury")
SEEDS = (0, 1, 2, 3, 4)


def profile_key(profile):
    """Same formula as engine.director.variety.subject_key (Task 43 asserts they agree)."""
    return hashlib.sha256(json.dumps(profile.to_dict(), sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


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
                cases.append({"model": m, "subjectKey": profile_key(p), "prompt": prompt, "seed": seed,
                              "tier": s_tier(r.script, p, cat), "directionId": r.script["direction"]["id"],
                              "durationS": r.script["format"]["durationS"], "shots": len(r.script["shots"]),
                              "scriptSha": hashlib.sha256(json.dumps(r.script, sort_keys=True).encode()).hexdigest()})
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    return {"schema": "valora.baseline/1", "frozenAt": sha, "cases": cases}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="engine.director.baseline_phase3")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if BASELINE.exists() and not a.force:
        raise SystemExit("the phase-3 baseline is frozen; regenerate only with --force and the owner's OK")
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps(build(), indent=1), encoding="utf-8", newline="\n")
    print(f"wrote {BASELINE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
