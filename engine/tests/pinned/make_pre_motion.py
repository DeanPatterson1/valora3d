"""Pinned pre-motion expectations (review chunk1 #11). Produced by the code at PRE_REV (2eed2f2, the commit
before phase-5 motion landed), never by the current tree, so a general phase-3/4 regression in the checker or
the camera timeline cannot hide behind a comparison of the current code with itself.

    git archive 2eed2f2 | tar -x -C <dir>
    py engine/tests/pinned/make_pre_motion.py <dir> engine/tests/fixtures/pre_motion_2eed2f2.json

collect() only calls APIs that exist at PRE_REV, so the same function measures the current tree in
engine/tests/test_pre_motion_pinned.py."""
import copy
import hashlib
import json
import sys
from pathlib import Path

PRE_REV = "2eed2f2"
PROFILES = ("pocket_watch", "sports_car", "mid_century_lounge_chair")


def _keys_digest(keys):
    rows = [[k.frame, k.shot, list(k.pose.position), list(k.pose.target), k.pose.lens_mm, k.fstop, k.focusM,
             list(k.target) if k.target is not None else None] for k in keys]
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest(), len(rows)


def collect():
    from engine.catalog import Catalog
    from engine.checker import check
    from engine.compiler.timeline import camera_keys
    from engine.director.baseline_phase3 import BASELINE
    from engine.director.direction import interim_direction
    from engine.director.floor import phase3_default
    from engine.director.job import make_job
    from engine.director.rulebook import EXAMPLES_DIR
    from engine.tests.test_director_package import _p
    cat = Catalog.load()
    out = {"rev": PRE_REV, "baseline": [], "checks": []}
    for case in json.loads(BASELINE.read_text(encoding="utf-8"))["cases"]:
        p = _p(case["model"])
        d = interim_direction(case["seed"], p, cat)
        s = phase3_default(make_job(case["prompt"], p, cat, seed=case["seed"], direction=d), p, cat)
        dig, n = _keys_digest(camera_keys(s, p, cat))
        again = check(copy.deepcopy(s), p, cat)       # the checker re-run on its own output (sequence stage)
        out["baseline"].append({"model": case["model"], "prompt": case["prompt"], "seed": case["seed"],
                                "script": s, "keys": dig, "nKeys": n, "recheckOk": again.ok,
                                "recheckIssues": [i.to_dict() for i in again.issues]})
    fix = Path(EXAMPLES_DIR).resolve().parents[1] / "tests" / "fixtures"
    scripts = [(f.name, json.loads(f.read_text(encoding="utf-8"))) for f in sorted(Path(EXAMPLES_DIR).glob("*.json"))]
    scripts.append(("script_valid.json", json.loads((fix / "script_valid.json").read_text(encoding="utf-8"))))
    for name, doc in scripts:
        for prof in PROFILES:
            p = _p(prof)
            r = check(copy.deepcopy(doc.get("script", doc)), p, cat)
            row = {"name": name, "profile": prof, "ok": r.ok, "script": r.script,
                   "issues": [i.to_dict() for i in r.issues]}
            if r.ok:
                row["keys"], row["nKeys"] = _keys_digest(camera_keys(r.script, p, cat))
            out["checks"].append(row)
    return out

COMPILE_KEYS = ("placedBounds", "built", "motionEvents", "realism", "realismScene", "clearance", "probe",
                "objects", "frameEnd", "shutter", "cameraPositions")


def collect_compile(model, out_dir):
    """One static compile (toycar, script_realism, no render, no grade): the compiled values phase-5 motion
    could have moved for a static script. Returns the COMPILE_KEYS of compile.json."""
    from engine.compiler.run import compile_scene
    from engine.profile import SubjectProfile
    import engine
    fix = Path(engine.__file__).resolve().parent / "tests" / "fixtures"
    prof = SubjectProfile.from_dict(json.loads((fix / "profiles" / "toycar.json").read_text(encoding="utf-8")))
    s = json.loads((fix / "script_realism.json").read_text(encoding="utf-8"))
    res = compile_scene(s, prof, model, out_dir, render=False, skip_kinds=("grade",), probe=[1, 45, 90])
    return {k: res.get(k) for k in COMPILE_KEYS}


if __name__ == "__main__":
    # py make_pre_motion.py <old tree> <out.json>                  the checker + camera-key expectations
    # py make_pre_motion.py <old tree> <out.json> --compile <glb>  the static Blender compile expectations
    root = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(root))
    import engine
    assert Path(engine.__file__).resolve().parents[1] == root, engine.__file__   # the OLD tree, never HEAD
    if "--compile" in sys.argv:
        import tempfile
        res = collect_compile(Path(sys.argv[sys.argv.index("--compile") + 1]), Path(tempfile.mkdtemp()))
        Path(sys.argv[2]).write_text(json.dumps({"rev": PRE_REV, **res}, sort_keys=True, indent=0), encoding="utf-8")
    else:
        Path(sys.argv[2]).write_text(json.dumps(collect(), sort_keys=True, separators=(",", ":")), encoding="utf-8")
