"""Calibration tooling. REPORT-ONLY: it writes proposals to harness/out/calibration-<date>-<kind>.json
and never edits thresholds.json. A human (Claude plus the owner's sign-off) moves a threshold and
flips `calibrated`, one item at a time, citing the proposal file and its n.

    py -m harness.calibrate cuts                 # T3-01 cut detector vs corpus cut times
    py -m harness.calibrate refs                 # mask-free stats on the owner's reference frames
    py -m harness.calibrate separate --run <id>  # owner grades vs metric values on our renders
"""
import argparse
import datetime
import json
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from harness.metrics import lum

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "harness" / "out"
GRADES = ROOT / "harness" / "grades" / "owner-grades.jsonl"
THRESHOLDS = ROOT / "harness" / "thresholds.json"
SWEEP = [0.08, 0.10, 0.12, 0.15, 0.18, 0.2, 0.25, 0.3, 0.35, 0.4]
UNION = (0.12, 0.3)  # TIERS T3-01: union of the two scene thresholds
TIER_RANK = {"T1": 1, "T2": 2, "T3": 3, "T4": 4}
DICT_KEY = {"maxBrightShare": "bright", "minDarkShare": "dark", "centroidInside": "centroidInside"}  # dict-valued metrics: the primary half
GROUND_TRUTH_CAVEAT = ("cutTimesS were vision-extracted in the pilot, so the ground truth itself has error; "
                       "treat P/R/F1 as indicative, not exact")


# ---------- pure helpers ----------

def match_cuts(pred, truth, tol_s):
    """Greedy one-to-one matching within tol_s, closest pairs first. Returns (tp, fp, fn)."""
    pairs = sorted((abs(p - t), i, j) for i, p in enumerate(pred) for j, t in enumerate(truth) if abs(p - t) <= tol_s)
    used_p, used_t = set(), set()
    for _, i, j in pairs:
        if i not in used_p and j not in used_t:
            used_p.add(i)
            used_t.add(j)
    tp = len(used_p)
    return tp, len(pred) - tp, len(truth) - tp


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return round(p, 4), round(r, 4), round(2 * p * r / (p + r), 4) if p + r else 0.0


def separation(good, bad, op):
    """op '>=': good values should sit above bad ones; '<=' mirrors it. A midpoint is proposed only
    when every good value is strictly on the good side of every bad value."""
    n = {"nGood": len(good), "nBad": len(bad)}
    if not good or not bad:
        return {"status": "insufficient", "proposed": None, **n}
    lo_good, hi_bad = (min(good), max(bad)) if op == ">=" else (-max(good), -min(bad))
    if lo_good > hi_bad:
        mid = (min(good) + max(bad)) / 2 if op == ">=" else (max(good) + min(bad)) / 2
        return {"status": "separable", "proposed": round(mid, 6), **n}
    return {"status": "overlap", "proposed": None, **n}


def parse_scene_scores(stderr):
    """[(pts_time, scene_score)] from ffmpeg `select='gte(scene,0)',metadata=print` output."""
    out, t = [], None
    for line in stderr.splitlines():
        m = re.search(r"pts_time:([0-9.eE+-]+)", line)
        if m:
            t = float(m.group(1))
            continue
        m = re.search(r"lavfi\.scene_score=([0-9.eE+-]+)", line)
        if m and t is not None:
            out.append((t, float(m.group(1))))
            t = None
    return out


def load_owner_grades(path=GRADES):
    """{case: tier} from lines with "by": "owner" only. Never the harness's or a judge's verdicts."""
    out = {}
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            g = json.loads(line)
            if g.get("by") == "owner":
                out[g["case"]] = g["tier"]
    return out


# ---------- ffmpeg ----------

def scene_scores(clip):
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(clip), "-vf", "select='gte(scene,0)',metadata=print",
                           "-an", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return parse_scene_scores(proc.stderr)


def detect_cuts(clip, threshold, scores=None):
    """Cut times where the scene score exceeds threshold (same rule as select='gt(scene,T)')."""
    scores = scene_scores(clip) if scores is None else scores
    return [t for t, s in scores if s > threshold]


def _union(a, b, tol):
    out = sorted(a)
    for t in b:
        if all(abs(t - u) > tol for u in out):
            out.append(t)
    return sorted(out)


# ---------- subcommands ----------

def calibrate_cuts(refs_dir=ROOT / "research" / "corpus" / "refs", clips_dir=ROOT / "assets-in" / "refs" / "clips"):
    rows = []
    for ref in sorted(Path(refs_dir).glob("*.json")):
        doc = json.loads(ref.read_text(encoding="utf-8"))
        fmt = doc.get("format", {})
        clip = Path(clips_dir) / f"{doc.get('id', ref.stem)}.mp4"
        if "cutTimesS" not in fmt or not clip.exists():
            continue
        rows.append({"id": doc.get("id", ref.stem), "truth": fmt["cutTimesS"], "fps": fmt.get("fps", 30),
                     "scores": scene_scores(clip)})
    result = {"kind": "cuts", "nClips": len(rows), "nTruthCuts": sum(len(r["truth"]) for r in rows),
              "tolerance": "+-2 frames", "caveat": GROUND_TRUTH_CAVEAT, "sweep": []}
    if not rows:
        result["note"] = "no clips with cut times present (assets-in/refs/clips and research/corpus/refs are local)"
        return result

    def score(pred_of):
        tp = fp = fn = 0
        for r in rows:
            a, b, c = match_cuts(pred_of(r), r["truth"], 2.0 / r["fps"])
            tp, fp, fn = tp + a, fp + b, fn + c
        p, rc, f1 = prf(tp, fp, fn)
        return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": rc, "f1": f1}

    for th in SWEEP:
        result["sweep"].append({"threshold": th, **score(lambda r, th=th: detect_cuts(None, th, r["scores"]))})
    result["sweep"].append({"threshold": f"union{UNION}", **score(lambda r: _union(
        detect_cuts(None, UNION[0], r["scores"]), detect_cuts(None, UNION[1], r["scores"]), 2.0 / r["fps"]))})
    best = max(result["sweep"], key=lambda s: s["f1"])
    result["bestF1"] = {"threshold": best["threshold"], "f1": best["f1"]}
    return result


def _dist(v):
    a = np.asarray(v, dtype=np.float64)
    q = np.percentile(a, [0, 10, 50, 90, 100])
    return {"n": int(a.size), "min": round(q[0], 4), "p10": round(q[1], 4), "median": round(q[2], 4),
            "p90": round(q[3], 4), "max": round(q[4], 4)}


def calibrate_refs(frames_dir=ROOT / "assets-in" / "refs" / "frames"):
    th = json.loads(THRESHOLDS.read_text(encoding="utf-8"))
    stats = {"B-01 meanLum": [], "B-02 brightShare": [], "B-02 darkShare": [], "lumStd": []}
    paths = sorted(Path(frames_dir).glob("*.jpg"))
    for p in paths:
        L = lum(np.asarray(Image.open(p).convert("RGB"), dtype=np.float32) / 255.0)
        stats["B-01 meanLum"].append(float(L.mean()))
        stats["B-02 brightShare"].append(float((L >= th["B-02"]["bright"]).mean()))
        stats["B-02 darkShare"].append(float((L <= th["B-02"]["dark"]).mean()))
        stats["lumStd"].append(float(L.std()))
    return {"kind": "refs", "nFrames": len(paths),
            "note": ("owner references are known-good but JPEG-compressed; mask-based items (gloss, subject, "
                     "separation) cannot be computed on refs because there are no masks"),
            "stats": {k: _dist(v) for k, v in stats.items() if v}}


def _case_scalar(item, th):
    """One number per case: the worst frame on the threshold's primary value."""
    val = item.get("value")
    key = DICT_KEY.get(th["primary"])
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, list):
        return None
    nums = []
    for row in val:
        v = row[1] if isinstance(row, list) and len(row) >= 2 else None
        if isinstance(v, dict) and key:
            v = v.get(key)
        if isinstance(v, (int, float)):
            nums.append(float(v))
    if not nums:
        return None
    return min(nums) if th["op"] == ">=" else max(nums)


def calibrate_separate(run_id, out_root=OUT, grades_path=GRADES):
    grades = load_owner_grades(grades_path)
    th = json.loads(THRESHOLDS.read_text(encoding="utf-8"))
    run_dir = Path(out_root) / run_id
    per_item = {iid: {"good": [], "bad": [], "t2": []} for iid in th}
    graded = 0
    for rep in sorted(run_dir.glob("*/report.json")):
        tier = grades.get(f"{run_id}/{rep.parent.name}")
        if tier is None:
            continue
        graded += 1
        items = json.loads(rep.read_text(encoding="utf-8"))["items"]
        group = "good" if TIER_RANK[tier] >= 3 else ("bad" if tier == "T1" else "t2")
        for iid, t in th.items():
            v = _case_scalar(items.get(iid, {}), t)
            if v is not None:
                per_item[iid][group].append(v)
    out = {"kind": "separate", "run": run_id, "nGradedCases": graded,
           "rule": "good = owner tier >= T3, bad = owner tier T1; T2 reported separately; owner grades only",
           "items": {}}
    for iid, g in per_item.items():
        out["items"][iid] = {**separation(g["good"], g["bad"], th[iid]["op"]), "op": th[iid]["op"],
                             "current": th[iid][th[iid]["primary"]], "nT2": len(g["t2"])}
    return out


def write_proposal(result, out_root=OUT):
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    p = out_root / f"calibration-{datetime.date.today().isoformat()}-{result['kind']}.json"
    p.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(prog="harness.calibrate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("cuts")
    sub.add_parser("refs")
    s = sub.add_parser("separate")
    s.add_argument("--run", required=True)
    a = ap.parse_args(argv)
    result = {"cuts": calibrate_cuts, "refs": calibrate_refs}[a.cmd]() if a.cmd != "separate" \
        else calibrate_separate(a.run)
    p = write_proposal(result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("sweep", "items", "stats")}, indent=2))
    print(f"proposal written: {p} (report-only; thresholds.json unchanged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
