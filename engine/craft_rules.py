"""TIERS.md [S] items as pure functions. The checker's sequence stage and the eval harness call
the same code, so a script the checker passes scores the same way in the harness.
Numbers marked (eng) are starting values to calibrate (see the plan's calibration table)."""
import math
import statistics
from dataclasses import dataclass

from engine.geometry import _basis, _dot, _sub, box_corners, focus_depth, frame_stats
from engine.grade_plan import changes_look
from engine.targets import resolve_target

COC_MM = 0.03            # full-frame circle of confusion
VEHICLE_SIZE_M = 2.5     # "vehicle-sized" for T3-21 / V-C02 (eng)
ARC_CAP_DEG_S = 80.0     # V-C11 (src: camera-car arm)
STILL_FRAC, STILL_S = 0.02, 1.0   # T3-13 / P-E07 (src)
SCALE_EDGES = ((0.35, "LS"), (0.6, "FS"), (0.9, "MS"), (1.3, "CS"))  # dominant-axis coverage (eng)


@dataclass(frozen=True)
class ItemResult:
    id: str
    status: str          # pass | fail | na | unmeasured
    value: object = None
    detail: str = ""


def shot_pose(shot, u, profile, catalog, markers=()):
    ref = shot["camera"]
    m = catalog.get("camera", ref["id"])
    tgt = resolve_target(shot, profile, list(markers)) if m["framing"] == "detail" else None
    return catalog.load_camera_path(ref["id"])(ref["params"], profile, u, tgt)


def azimuth_deg(pose, profile):
    cx, cy, _ = profile.center
    return math.degrees(math.atan2(pose.position[1] - cy, pose.position[0] - cx))


def coverage(pose, profile, aspect):
    return frame_stats(pose, box_corners(profile.boundsMin, profile.boundsMax), aspect)["coverage"]


def scale_class(cov):
    for edge, name in SCALE_EDGES:
        if cov < edge:
            return name
    return "ECS"


def _wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def cut_ok(prev, nxt, profile, catalog, aspect, markers=()):
    """T3-04 / V-E05: >= 30 deg azimuth change about the subject, or >= 1.5x screen size."""
    a = shot_pose(prev, 1.0, profile, catalog, markers)
    b = shot_pose(nxt, 0.0, profile, catalog, markers)
    d_az = abs(_wrap(azimuth_deg(b, profile) - azimuth_deg(a, profile)))
    ca, cb = coverage(a, profile, aspect), coverage(b, profile, aspect)
    ratio = math.inf if min(ca, cb) <= 0 else max(ca, cb) / min(ca, cb)
    return (d_az >= 30.0 or ratio >= 1.5), d_az, ratio


def _poses(shot, profile, catalog, markers, n):
    return [shot_pose(shot, k / (n - 1), profile, catalog, markers) for k in range(n)]


def still_tail_s(shot, profile, catalog, markers=(), n=121):
    """Seconds of true stillness at the end of the shot (T3-13)."""
    poses = _poses(shot, profile, catalog, markers, n)
    dt = (shot["endS"] - shot["startS"]) / (n - 1)
    speeds = [(math.dist(a.position, b.position) + math.dist(a.target, b.target)) / dt
              for a, b in zip(poses, poses[1:])]
    peak = max(speeds)
    if peak <= 0:
        return shot["endS"] - shot["startS"]
    tail = 0
    for v in reversed(speeds):
        if v >= STILL_FRAC * peak:
            break
        tail += 1
    return tail * dt


def max_arc_rate(shot, profile, catalog, markers=(), n=121):
    poses = _poses(shot, profile, catalog, markers, n)
    dt = (shot["endS"] - shot["startS"]) / (n - 1)
    az = [azimuth_deg(p, profile) for p in poses]
    return max(abs(_wrap(b - a)) / dt for a, b in zip(az, az[1:]))


def dof_ok(shot, profile, catalog, aspect, markers=()):
    """T3-21 anti-miniature (V-C07): a fully framed vehicle-sized subject is sharp end to end,
    and no high (> 30 deg) angle at fstop < 4."""
    pose = shot_pose(shot, 0.5, profile, catalog, markers)
    fwd, _, _ = _basis(pose)
    depths = [_dot(_sub(c, pose.position), fwd) for c in box_corners(profile.boundsMin, profile.boundsMax)]
    # Focus exactly where the compiler puts it (compiler.timeline._key: the detail target, else the
    # subject centre, at geometry.focus_depth = depth along the view axis).
    tgt = resolve_target(shot, profile, list(markers)) if _cam(shot, catalog)["framing"] == "detail" else None
    focus = max(focus_depth(pose, tgt.point if tgt else profile.center), 1e-3)
    f, c, n = pose.lens_mm / 1000.0, COC_MM / 1000.0, shot["camera"]["params"]["fstop"]
    hyper = f * f / (n * c) + f
    near = focus * (hyper - f) / (hyper + focus - 2 * f)
    far = math.inf if focus >= hyper else focus * (hyper - f) / (hyper - focus)
    rel = _sub(pose.position, profile.center)
    elev = math.degrees(math.asin(max(-1.0, min(1.0, rel[2] / math.sqrt(_dot(rel, rel))))))
    # Both ends sharp: the acceptable-focus band must contain the nearest and farthest corner.
    return near <= min(depths) and far >= max(depths) and not (elev > 30 and n < 4)


def _res(iid, ok, value=None, detail=""):
    return ItemResult(iid, "pass" if ok else "fail", value, detail)


def _cam(shot, catalog):
    return catalog.get("camera", shot["camera"]["id"])


def primitive(shot, catalog):
    mv = _cam(shot, catalog).get("move")
    if isinstance(mv, dict):
        return mv["map"].get(shot["camera"]["params"].get(mv["param"]))
    return mv


def score_script(s, profile, catalog):
    """Every [S] TIERS item (plus V-C02) for a checked script. [S+M] items return their S half;
    the harness ANDs it with the M half."""
    shots, aspect, dur = s["shots"], s["format"]["aspect"], s["format"]["durationS"]
    markers = s.get("markers", [])
    lens = [sh["endS"] - sh["startS"] for sh in shots]
    world = catalog.get("world", s["world"]["id"])
    light = s["lighting"]
    out = []
    # T1 signatures (a fail caps the render at T1).
    arcs = [sh for sh in shots if sh["camera"]["id"] == "arc_orbit"]
    out.append(_res("T1-X1", not (len(shots) == 1 and any(abs(sh["camera"]["params"]["sweepDeg"]) > 180 for sh in arcs))))
    flat = (light["id"] == "softbox_three_point" and light["params"]["rimStrength"] == 0
            and light["params"]["fillRatio"] > 1 / 1.5)
    out.append(_res("T1-X3", not flat))
    # T2
    out.append(_res("T2-01", bool(world.get("hasGround") or world.get("environment"))))
    eased = all(sh["camera"]["params"].get("easing", "linear") != "linear" or _cam(sh, catalog).get("linearByDesign")
                for sh in shots)
    out.append(_res("T2-03", eased))
    out.append(_res("T2-04", all(primitive(sh, catalog) not in (None, "static") for sh in shots)))
    out.append(ItemResult("T2-05", "pass", 0.5, "by construction: the compiler sets a 180-degree shutter"))
    # Owner 2026-09-24: a clean studio backdrop (world block flagged `studio: true`) meets T2-07.
    atmo = (world.get("atmosphere") or world.get("studio")
            or any(catalog.get("effect", fx["id"]).get("atmosphere") for fx in s.get("effects", [])))
    out.append(_res("T2-07", bool(atmo), detail="S half: an atmosphere block or a studio world is present"))
    out.append(ItemResult("T2-08", "pass" if changes_look(s["grade"]) else "fail", detail="S fallback: grade is not identity"))
    # T3
    per10 = len(shots) / (dur / 10.0)
    out.append(_res("T3-01", 3 <= per10 <= 7, round(per10, 2)))
    med = statistics.median(lens)
    out.append(_res("T3-02", 1.0 <= med <= 3.0 and min(lens) >= 0.5 and lens[-1] >= 1.5, round(med, 2)))
    scales = {scale_class(coverage(shot_pose(sh, 0.5, profile, catalog, markers), profile, aspect))
              if _cam(sh, catalog)["framing"] == "full" else "ECS" for sh in shots}
    has_detail = any(_cam(sh, catalog)["framing"] == "detail" for sh in shots)
    out.append(_res("T3-03", len(scales) >= 2 and has_detail, sorted(scales)))
    cuts = [cut_ok(a, b, profile, catalog, aspect, markers)[0] for a, b in zip(shots, shots[1:])]
    out.append(_res("T3-04", all(cuts), cuts))
    moving = s["subject"]["motion"]["id"] != "static"
    out.append(ItemResult("T3-05", "unmeasured" if moving else "na", detail="subject static" if not moving else ""))
    out.append(_res("T3-11", all(primitive(sh, catalog) for sh in shots)))
    tail = still_tail_s(shots[-1], profile, catalog, markers)
    out.append(_res("T3-13", tail >= STILL_S - 1e-6, round(tail, 2)))
    rate = max(max_arc_rate(sh, profile, catalog, markers) for sh in shots)
    out.append(_res("T3-14", rate <= ARC_CAP_DEG_S, round(rate, 1)))
    last = shots[-1]
    out.append(_res("T3-16", _cam(last, catalog)["framing"] == "full" and lens[-1] >= 1.5
                    and last.get("purpose", "hero") in ("hero", "packshot")))
    vehicle = profile.longest >= VEHICLE_SIZE_M
    full = [sh for sh in shots if _cam(sh, catalog)["framing"] == "full"]
    if vehicle and full:
        out.append(_res("T3-21", all(dof_ok(sh, profile, catalog, aspect, markers) for sh in full)))
        out.append(_res("V-C02", all(sh["camera"]["params"]["lensMm"] >= 28 for sh in full)))
    else:
        out.append(ItemResult("T3-21", "na", detail="not a vehicle-sized full frame"))
        out.append(ItemResult("V-C02", "na"))
    # T4 [S] halves
    out.append(ItemResult("T4-02", "na" if not moving else "fail", detail="no vehicle dynamics block yet"))
    out.append(ItemResult("T4-03", "fail", detail="no simulation blocks in v1 (spec §8)"))
    return out
