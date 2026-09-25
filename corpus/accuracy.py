"""Extraction accuracy (spec §9a): per-field agreement of extracted records with the gold subset.
A field whose agreement is below MIN_RATE (or measured on < MIN_N clips) is untrusted: corpus stats
built on it are flagged and the taste guide will not quote them."""
import json

from corpus import CORPUS_DIR

GOLD_DIR = CORPUS_DIR / "gold"
ACCURACY = CORPUS_DIR / "accuracy.json"
CUT_TOL_S = 0.25
MIN_RATE, MIN_N = 0.7, 10
TOP_FIELDS = ("subject.category", "subject.sizeClass", "format.aspect", "layout.kind", "world.type",
              "grade.contrast", "grade.saturation", "pacing.energy", "qualityEstimate")
SHOT_FIELDS = ("cameraMove", "lensClass", "cameraHeight", "focus", "subjectMotion", "renderPass")


def _get(rec, path):
    cur = rec
    for k in path.split("."):
        cur = cur.get(k) if isinstance(cur, dict) else None
    return cur


def _cuts_agree(a, b):
    a, b = list(a or []), list(b or [])
    if len(a) != len(b):
        return False
    return all(abs(x - y) <= CUT_TOL_S for x, y in zip(sorted(a), sorted(b)))


def compare(ext, gold):
    rows = [{"field": f, "agree": _get(ext, f) == _get(gold, f)} for f in TOP_FIELDS]
    rows.append({"field": "format.shotCount", "agree": _get(ext, "format.shotCount") == _get(gold, "format.shotCount")})
    rows.append({"field": "format.cutTimesS", "agree": _cuts_agree(_get(ext, "format.cutTimesS"), _get(gold, "format.cutTimesS"))})
    ls = set(_get(ext, "lighting.setup") or [])
    gs = set(_get(gold, "lighting.setup") or [])
    rows.append({"field": "lighting.setup", "agree": bool(gs) and len(ls & gs) / len(ls | gs) >= 0.5})
    es, gsh = ext.get("shots") or [], gold.get("shots") or []
    aligned = len(es) == len(gsh)
    for i, g in enumerate(gsh):
        for f in SHOT_FIELDS:
            if g.get(f) == "unclear":
                continue  # gold could not see it either: not scorable
            rows.append({"field": f"shots.{f}", "agree": aligned and es[i].get(f) == g.get(f)})
    return rows


def summarize(pairs):
    fields = {}
    for ext, gold in pairs:
        for r in compare(ext, gold):
            f = fields.setdefault(r["field"], {"agree": 0, "n": 0})
            f["n"] += 1
            f["agree"] += r["agree"]
    for f in fields.values():
        f["rate"] = round(f["agree"] / f["n"], 3) if f["n"] else None
    return {"schema": "valora.corpus-accuracy/1", "n": len(pairs),
            "fields": dict(sorted(fields.items()))}


def trusted_fields(summary, min_rate=MIN_RATE, min_n=MIN_N):
    return sorted(k for k, v in summary["fields"].items() if v["n"] >= min_n and (v["rate"] or 0) >= min_rate)


def run(refs_dir=CORPUS_DIR / "refs", gold_dir=GOLD_DIR, out=ACCURACY):
    pairs = []
    for g in sorted(gold_dir.glob("*.json")):
        ext = refs_dir / g.name
        if ext.exists():
            pairs.append((json.loads(ext.read_text(encoding="utf-8")), json.loads(g.read_text(encoding="utf-8"))))
    s = summarize(pairs)
    s["trusted"] = trusted_fields(s)
    if not pairs:
        return s  # no gold yet: leave accuracy unmeasured (stats trust stays None), write nothing
    out.write_text(json.dumps(s, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return s
