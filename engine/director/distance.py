"""How different two directions / two scripts are, in [0, 1]. Direction distance is a weighted Hamming
distance over the dice axes (dice.json axisWeights). Script distance compares what a viewer would see:
world, light, grade, effects, the cut pattern and each camera's parameters normalised by the catalog
range. Used by the dice (near-duplicate penalty) and the harness variety score (spec §9)."""
from engine.director.axes import DICE
from engine.director.direction import AXES


def direction_distance(a, b, dice=None):
    w = (dice or DICE)["axisWeights"]
    return sum(w[x] for x in AXES if a.get(x) != b.get(x)) / sum(w[x] for x in AXES)


def _params_d(ra, rb, kind, catalog):
    ra, rb = ra or {}, rb or {}
    if ra.get("id") != rb.get("id"):
        return 1.0
    m = catalog.get(kind, ra.get("id")) if ra.get("id") else None
    if not m or not m["params"]:
        return 0.0
    pa, pb, ds = ra.get("params") or {}, rb.get("params") or {}, []
    for name, spec in m["params"].items():
        va, vb = pa.get(name, spec["default"]), pb.get(name, spec["default"])
        if spec["type"] == "number":
            span = (spec["max"] - spec["min"]) or 1.0
            try:
                ds.append(min(1.0, abs(float(va) - float(vb)) / span))
            except (TypeError, ValueError):
                ds.append(1.0)
        else:
            ds.append(0.0 if va == vb else 1.0)
    return sum(ds) / len(ds)


def _grade_key(s):
    g = s.get("grade") or {}
    return (g.get("id"), (g.get("params") or {}).get("preset"))


def _bounds(s):
    return [sh["endS"] for sh in s["shots"][:-1]]


def script_distance(a, b, catalog):
    sa, sb = a["shots"], b["shots"]
    dur = max(a["format"]["durationS"], b["format"]["durationS"], 1e-9)
    n = max(len(sa), len(sb))
    cam_seq = sum(1 for i in range(n) if i >= len(sa) or i >= len(sb)
                  or sa[i]["camera"]["id"] != sb[i]["camera"]["id"]) / n
    aligned = [(x["camera"], y["camera"]) for x, y in zip(sa, sb) if x["camera"]["id"] == y["camera"]["id"]]
    cam_params = sum(_params_d(x, y, "camera", catalog) for x, y in aligned) / len(aligned) if aligned else 1.0
    ba, bb = _bounds(a), _bounds(b)
    cuts = (sum(min(1.0, abs(x - y) / dur * 4) for x, y in zip(ba, bb)) / max(len(ba), len(bb))
            if ba and bb and len(ba) == len(bb) else (0.0 if ba == bb else 1.0))
    ea, eb = {e["id"] for e in a.get("effects", [])}, {e["id"] for e in b.get("effects", [])}
    parts = [  # (distance, weight)
        (0.0 if a["world"]["id"] == b["world"]["id"] else 1.0, 2), (_params_d(a["world"], b["world"], "world", catalog), 1),
        (0.0 if a["lighting"]["id"] == b["lighting"]["id"] else 1.0, 2),
        (_params_d(a["lighting"], b["lighting"], "lighting", catalog), 1),
        (0.0 if _grade_key(a) == _grade_key(b) else 1.0, 2), (_params_d(a.get("grade"), b.get("grade"), "grade", catalog), 1),
        (1.0 - len(ea & eb) / len(ea | eb) if ea | eb else 0.0, 1),
        (min(1.0, abs(len(sa) - len(sb)) / 3), 1), (cam_seq, 2), (cam_params, 1), (cuts, 1),
        (0.0 if a["format"]["durationS"] == b["format"]["durationS"] else 1.0, 1),
    ]
    return sum(d * w for d, w in parts) / sum(w for _, w in parts)


def near_duplicate(a, b, catalog, dice=None):
    return script_distance(a, b, catalog) < (dice or DICE)["nearDuplicateScript"]
