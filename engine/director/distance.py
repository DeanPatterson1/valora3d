"""How different two directions / two scripts are, in [0, 1]. Direction distance is a weighted Hamming
distance over the dice axes (dice.json axisWeights). Script distance compares what a viewer would see:
world, light, grade, effects, the cut pattern and each camera's parameters normalised by the catalog
range. Used by the dice (near-duplicate penalty) and the harness variety score (spec §9)."""
import math

from engine.director.axes import DICE
from engine.director.direction import AXES

# A param difference counts in VISIBLE steps, not as a share of the catalog range: the catalog's own cut
# rule (T3-04 / TG-03) calls a 30-degree angle change or a 1.5x size change a different shot, so an angle
# param ("...Deg") saturates at 30 degrees and a lens or camera distance at a 1.5x ratio. Range-normalising
# them made a 30-degree camera move 0.083 of one param (azimuth spans 360) and a new-shot-sized lens change
# ~0.2, so seeded detail variation could never register however visible it was. Other numbers keep the
# share of their range.
ANGLE_STEP_DEG = 30.0
SIZE_STEP = math.log(1.5)
SIZE_PARAMS = ("lensMm", "distance")


# (eng) Camera params are what a viewer sees most of a shot, and _params_d averages over 8-10 params, so a
# weight of 1 capped a max param difference at 1/16 < nearDuplicateScript (0.08). At 10 of 27 (measured
# 2026-09-25 on examples/watch_luxury): every camera param at opposite range ends on every shot = 0.37,
# azimuth/lens/sweep only at opposite ends = 0.10 (neither a near-duplicate), +3mm lens / +5 deg azimuth on
# every shot = 0.002 (a near-duplicate). Re-measured with visible steps (2026-09-25, same example): 0.37 /
# 0.104 / 0.011 (still a near-duplicate).
CAM_PARAMS_W = 10
# (eng) Shared-effect params (e.g. haze density): _params_d over 4 haze params gives 0.25 for density 0 vs 1,
# so 2 of 27 adds 0.019 on its own, visible but not a new script by itself.
FX_PARAMS_W = 2


def direction_distance(a, b, dice=None):
    w = (dice or DICE)["axisWeights"]
    return sum(w[x] for x in AXES if a.get(x) != b.get(x)) / sum(w[x] for x in AXES)


def _number_d(name, spec, va, vb):
    if name.endswith("Deg"):
        return min(1.0, abs(va - vb) / ANGLE_STEP_DEG)
    if name in SIZE_PARAMS and va > 0 and vb > 0:
        return min(1.0, abs(math.log(va / vb)) / SIZE_STEP)
    return min(1.0, abs(va - vb) / ((spec["max"] - spec["min"]) or 1.0))


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
            try:
                ds.append(_number_d(name, spec, float(va), float(vb)))
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
    fa, fb = {e["id"]: e for e in a.get("effects", [])}, {e["id"]: e for e in b.get("effects", [])}
    ea, eb = set(fa), set(fb)
    shared = sorted(ea & eb)   # params of an effect both scripts use (density 0 vs 1 is a visible change)
    fx_params = sum(_params_d(fa[i], fb[i], "effect", catalog) for i in shared) / len(shared) if shared else 0.0
    parts = [  # (distance, weight)
        (0.0 if a["world"]["id"] == b["world"]["id"] else 1.0, 2), (_params_d(a["world"], b["world"], "world", catalog), 1),
        (0.0 if a["lighting"]["id"] == b["lighting"]["id"] else 1.0, 2),
        (_params_d(a["lighting"], b["lighting"], "lighting", catalog), 1),
        (0.0 if _grade_key(a) == _grade_key(b) else 1.0, 2), (_params_d(a.get("grade"), b.get("grade"), "grade", catalog), 1),
        (1.0 - len(ea & eb) / len(ea | eb) if ea | eb else 0.0, 1), (fx_params, FX_PARAMS_W),
        (min(1.0, abs(len(sa) - len(sb)) / 3), 1), (cam_seq, 2), (cam_params, CAM_PARAMS_W), (cuts, 1),
        (0.0 if a["format"]["durationS"] == b["format"]["durationS"] else 1.0, 1),
    ]
    return sum(d * w for d, w in parts) / sum(w for _, w in parts)


def near_duplicate(a, b, catalog, dice=None):
    return script_distance(a, b, catalog) < (dice or DICE)["nearDuplicateScript"]
