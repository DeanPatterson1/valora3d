"""Checker stage for the `sequence` edit block (CATALOG-GAPS rank 2). Rules come from the block
manifest; the maths is engine.craft_rules, shared with the harness."""
import math
import statistics

from engine import craft_rules as cr
from engine.issues import Issue

AZIMUTH_PARAMS = ("azimuthDeg", "startAzimuthDeg", "azimuthOffsetDeg")
JUMP_ROTATE_DEG = 35.0


def _framing(shot, catalog):
    return catalog.get("camera", shot["camera"]["id"])["framing"]


def _fill_purposes(shots, catalog, issues):
    last = len(shots) - 1
    for i, sh in enumerate(shots):
        if "purpose" not in sh:
            p = ("hook" if i == 0 else "hero" if i == last
                 else "detail" if _framing(sh, catalog) == "detail" else "motion")
            sh["purpose"] = p
            issues.append(Issue("purpose_inferred", f"shots[{i}].purpose", p, "repaired"))


def _repair_jump(i, s, profile, catalog, issues):
    shots, markers, aspect = s["shots"], s.get("markers", []), s["format"]["aspect"]
    prm = shots[i]["camera"]["params"]
    key = next((k for k in AZIMUTH_PARAMS if k in prm), None)
    if key is None:
        return False
    spec = catalog.get("camera", shots[i]["camera"]["id"])["params"][key]
    old = prm[key]
    for step in (JUMP_ROTATE_DEG, -JUMP_ROTATE_DEG):
        prm[key] = min(max(cr._wrap(old + step), spec["min"]), spec["max"])
        if cr.cut_ok(shots[i - 1], shots[i], profile, catalog, aspect, markers, cr.motion_of(s, profile, catalog))[0]:
            issues.append(Issue("jump_cut_rotated", f"shots[{i}].camera.params.{key}", f"{old} -> {prm[key]}", "repaired"))
            return True
    prm[key] = old
    return False


def recheck_cuts(s, profile, catalog, issues):
    """After the checker re-fits distances on repaired shots, a cut can jump again: re-judge
    every cut and report any that fail and are not already reported."""
    shots, markers, aspect = s["shots"], s.get("markers", []), s["format"]["aspect"]
    reported = {i.path for i in issues if i.code == "seq_jump_cut"}
    motion = cr.motion_of(s, profile, catalog)
    for i in range(1, len(shots)):
        ok, d_az, ratio = cr.cut_ok(shots[i - 1], shots[i], profile, catalog, aspect, markers, motion)
        if not ok and f"shots[{i}]" not in reported:
            issues.append(Issue("seq_jump_cut", f"shots[{i}]",
                                f"{d_az:.0f} deg and {ratio:.2f}x from shot {i - 1} after the distance re-fit "
                                "(needs 30 deg or 1.5x)", "error"))


def _repair_ending(s, profile, catalog, issues):
    last = s["shots"][-1]
    spec = catalog.get("camera", last["camera"]["id"])["params"].get("settleFrac")
    if spec is None:
        return False
    prm, length = last["camera"]["params"], last["endS"] - last["startS"]
    old = prm["settleFrac"]
    prm["settleFrac"] = round(min(spec["max"], max(old, (cr.STILL_S + 0.1) / length)), 4)
    motion = cr.motion_of(s, profile, catalog)
    if cr.still_tail_s(last, profile, catalog, s.get("markers", []), motion=motion) >= cr.STILL_S - 1e-6:
        issues.append(Issue("ending_settled", f"shots[{len(s['shots']) - 1}].camera.params.settleFrac",
                            f"{old} -> {prm['settleFrac']}", "repaired"))
        return True
    prm["settleFrac"] = old
    return False


def check_sequence(s, profile, catalog, issues):
    """Enforce the sequence rules. Returns indices of shots whose camera params changed."""
    m = catalog.get("edit", "sequence")
    shots, dur = s["shots"], s["format"]["durationS"]
    changed = set()
    motion = cr.motion_of(s, profile, catalog)   # the compiled cameras, judged against the live subject

    def err(code, path, msg):
        issues.append(Issue(code, path, msg, "error"))

    _fill_purposes(shots, catalog, issues)
    lo, hi = m["shotsPer10s"][s["edit"]["params"]["pace"]]
    n_lo, n_hi = math.floor(lo * dur / 10.0), math.ceil(hi * dur / 10.0)
    if not n_lo <= len(shots) <= n_hi:
        err("seq_shot_count", "shots", f"{len(shots)} shots; this pace wants {n_lo}-{n_hi} in {dur} s")
    lens = [sh["endS"] - sh["startS"] for sh in shots]
    a, b = m["shotLenS"]
    for i, length in enumerate(lens):
        if not a - 1e-9 <= length <= b + 1e-9:
            err("seq_shot_length", f"shots[{i}]", f"{length:.2f} s outside {a}-{b} s")
    ma, mb = m["medianLenS"]
    if not ma <= statistics.median(lens) <= mb:
        err("seq_median_length", "shots", f"median shot outside {ma}-{mb} s")
    if (shots[0]["purpose"] not in ("hook", "establish") or _framing(shots[0], catalog) != "full"
            or lens[0] > m["hookMaxS"] + 1e-9):
        err("seq_bad_hook", "shots[0]", f"first shot: full-framing hook/establish, <= {m['hookMaxS']} s")
    if not any(_framing(sh, catalog) == "detail" for sh in shots):
        err("seq_no_detail", "shots", "needs at least one detail shot (T3-03)")
    if (shots[-1]["purpose"] not in ("hero", "packshot") or _framing(shots[-1], catalog) != "full"
            or lens[-1] < m["lastShotMinS"] - 1e-9):
        err("seq_bad_ending", f"shots[{len(shots) - 1}]", f"last shot: full-framing hero/packshot, >= {m['lastShotMinS']} s")
    for i in range(1, len(shots)):
        ok, d_az, ratio = cr.cut_ok(shots[i - 1], shots[i], profile, catalog, s["format"]["aspect"],
                                    s.get("markers", []), motion)
        if ok:
            continue
        if _repair_jump(i, s, profile, catalog, issues):
            changed.add(i)
        else:
            err("seq_jump_cut", f"shots[{i}]", f"{d_az:.0f} deg and {ratio:.2f}x from shot {i - 1} (needs 30 deg or 1.5x)")
    if cr.still_tail_s(shots[-1], profile, catalog, s.get("markers", []), motion=motion) < cr.STILL_S - 1e-6:
        if _repair_ending(s, profile, catalog, issues):
            changed.add(len(shots) - 1)
        else:
            err("seq_no_still_ending", f"shots[{len(shots) - 1}]", "last move must end in >= 1 s of stillness")
    return changed
