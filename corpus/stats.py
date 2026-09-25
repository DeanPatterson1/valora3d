"""Deterministic corpus statistics (spec §9a uses 2-4). Every stat carries n and a trust flag:
trusted=True when accuracy.json trusts its source field for EVERY extraction method among the records
it is built from, False when any method does not (a method never measured, e.g. in_player before its
gold pass, trusts nothing), None when accuracy has not been measured yet. The taste guide only quotes
trusted stats with n >= its minimum."""
import hashlib
import json
import statistics
from collections import Counter

FAMILIES = ("product", "furniture", "vehicle", "character", "abstract")
MIN_TIER = ("T2", "T3", "T4")
SOURCE_FIELD = {  # stat -> the accuracy field it depends on
    "shotsPer10s": "format.shotCount", "shotLenS": "format.cutTimesS", "firstShotS": "format.cutTimesS",
    "lastShotS": "format.cutTimesS", "lensClass": "shots.lensClass", "cameraMove": "shots.cameraMove",
    "cameraHeight": "shots.cameraHeight", "focus": "shots.focus", "renderPass": "shots.renderPass",
    "worldType": "world.type", "contrast": "grade.contrast", "saturation": "grade.saturation",
    "energy": "pacing.energy",
}


def eligible(records):
    return [r for r in records if (r.get("source") or {}).get("kind") != "own_render"
            and r.get("qualityEstimate") in MIN_TIER]


def _num(values):
    v = sorted(values)
    if not v:
        return {"n": 0}
    out = {"n": len(v), "median": round(statistics.median(v), 3)}
    if len(v) >= 4:
        q = statistics.quantiles(v, n=4)
        out.update(p25=round(q[0], 3), p75=round(q[2], 3))
    return out


def _shares(values):
    v = [x for x in values if x not in (None, "unclear")]
    c = Counter(v)
    return {"n": len(v), "shares": {k: round(c[k] / len(v), 3) for k in sorted(c)}} if v else {"n": 0, "shares": {}}


def _family(recs):
    shots = [sh for r in recs for sh in r["shots"]]
    lens = [sh["endS"] - sh["startS"] for sh in shots]
    return {
        "records": len(recs),
        "shotsPer10s": _num([len(r["shots"]) / (r["format"]["durationS"] / 10.0) for r in recs]),
        "shotLenS": _num(lens),
        "firstShotS": _num([r["shots"][0]["endS"] - r["shots"][0]["startS"] for r in recs]),
        "lastShotS": _num([r["shots"][-1]["endS"] - r["shots"][-1]["startS"] for r in recs]),
        "lensClass": _shares([sh["lensClass"] for sh in shots]),
        "cameraMove": _shares([sh["cameraMove"] for sh in shots]),
        "cameraHeight": _shares([sh["cameraHeight"] for sh in shots]),
        "focus": _shares([sh["focus"] for sh in shots]),
        "renderPass": _shares([sh["renderPass"] for sh in shots]),
        "worldType": _shares([r["world"]["type"] for r in recs]),
        "contrast": _shares([r["grade"]["contrast"] for r in recs]),
        "saturation": _shares([r["grade"]["saturation"] for r in recs]),
        "energy": _shares([r["pacing"]["energy"] for r in recs]),
    }


def load_trust(path):
    """{method: set(fields)} from accuracy.json, or None when accuracy has not been measured."""
    if not path.exists():
        return None
    return {m: set(v) for m, v in json.loads(path.read_text(encoding="utf-8"))["trustedByMethod"].items()}


def _trust(fam, recs, trusted):
    methods = {r.get("method") for r in recs}
    for stat, field in SOURCE_FIELD.items():
        fam[stat]["trusted"] = None if trusted is None else bool(methods) and all(
            field in trusted.get(m, ()) for m in methods)
    return fam


def compute(records, trusted=None):
    """trusted: {method: set(fields)} (load_trust) or None when accuracy is unmeasured."""
    recs = eligible(records)
    ids = sorted(r["id"] for r in recs)
    fams = {"all": _trust(_family(recs), recs, trusted)}
    for f in FAMILIES:
        sub = [r for r in recs if r["subject"]["category"] == f]
        fams[f] = _trust(_family(sub), sub, trusted)
    return {"schema": "valora.corpus-stats/1", "records": len(ids),
            "recordSetHash": hashlib.sha256("\n".join(ids).encode()).hexdigest()[:12], "families": fams}
