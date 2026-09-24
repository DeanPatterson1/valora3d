"""The checker: nothing renders unless check() returns ok (spec §4.6)."""
import math
from dataclasses import dataclass, field
from engine.geometry import box_corners, frame_stats, point_in_box, project
from engine.issues import Issue, errors
from engine.markers import check_anchors
from engine.script import validate_and_repair
from engine.targets import resolve_target

SAMPLES_PER_SHOT = 12
BOX_MARGIN = 0.10
MIN_CAMERA_Z = 0.02
MIN_COVERAGE = 0.25
GRID_POINTS = 32
DETAIL_CENTER = 0.6         # target stays within |ndc| <= 0.6 on detail shots (eng)
DETAIL_MIN_COVERAGE = 0.6   # T3-03: a detail shot fills >= 60% or overflows the frame


@dataclass
class CheckResult:
    ok: bool
    script: dict
    issues: list = field(default_factory=list)


def _shot_verdict(sample, params, profile, framing, aspect, target=None):
    """Return 'ok', 'out' (move away), 'in' (move closer) or 'off' (target not centred)."""
    corners = box_corners(profile.boundsMin, profile.boundsMax)
    small = False
    for k in range(SAMPLES_PER_SHOT):
        pose = sample(params, profile, k / (SAMPLES_PER_SHOT - 1), target)
        if pose.position[2] < MIN_CAMERA_Z:
            return "out"
        if point_in_box(pose.position, profile.boundsMin, profile.boundsMax, BOX_MARGIN):
            return "out"
        st = frame_stats(pose, corners, aspect)
        if framing == "full":
            if not st["allInFront"] or not st["inFrame"]:
                return "out"
            if st["coverage"] < MIN_COVERAGE:
                small = True
        else:
            x, y, depth = project(pose, target.point if target else profile.center, aspect)
            if depth <= 0 or max(abs(x), abs(y)) > DETAIL_CENTER:
                return "off"
            if st["allInFront"] and st["inFrame"] and st["coverage"] < DETAIL_MIN_COVERAGE:
                small = True
    return "in" if small else "ok"


def _distance_grid(lo, hi):
    """GRID_POINTS geometric distances spanning [lo, hi] inclusive, rounded to 4 decimals
    BEFORE they are judged, so the value written back is exactly the value that passed."""
    if lo == hi:
        return [lo]
    ratio = hi / lo
    grid = [min(max(round(lo * ratio ** (j / (GRID_POINTS - 1)), 4), lo), hi) for j in range(GRID_POINTS)]
    grid[0], grid[-1] = lo, hi
    return grid


def _fix_shot(i, shot, catalog, profile, aspect, markers, issues):
    """Keep a passing distance; else pick the passing grid distance nearest in log space."""
    ref = shot["camera"]
    m = catalog.get("camera", ref["id"])
    sample = catalog.load_camera_path(ref["id"])
    spec = m["params"]["distance"]
    params = ref["params"]
    start = params["distance"]
    target = resolve_target(shot, profile, markers) if m["framing"] == "detail" else None
    if _shot_verdict(sample, params, profile, m["framing"], aspect, target) == "ok":
        return
    best = None  # (log distance to request, -distance) — ties go to the larger distance
    for d in _distance_grid(spec["min"], spec["max"]):
        if _shot_verdict(sample, {**params, "distance": d}, profile, m["framing"], aspect, target) != "ok":
            continue
        key = (abs(math.log(d) - math.log(start)), -d)
        if best is None or key < best[0]:
            best = (key, d)
    if best is None:
        issues.append(Issue("framing_unfixable", f"shots[{i}].camera",
                            f"no distance in [{spec['min']}, {spec['max']}] frames the subject", "error"))
        return
    params["distance"] = best[1]
    issues.append(Issue("camera_distance_adjusted", f"shots[{i}].camera.params.distance",
                        f"{start} -> {params['distance']}", "repaired"))


def _compat(s, catalog, profile, issues):
    aspect = s["format"]["aspect"]
    size = profile.longest
    refs = [("world", "world", s["world"]), ("lighting", "lighting", s["lighting"])]
    refs += [("camera", f"shots[{i}].camera", sh["camera"]) for i, sh in enumerate(s["shots"])]
    for kind, path, ref in refs:
        m = catalog.get(kind, ref["id"])
        lo, hi = m["subjectSizeM"]
        if not lo <= size <= hi:
            issues.append(Issue("subject_size_unsupported", path,
                                f"{ref['id']} supports {lo}-{hi} m, subject is {size:.3f} m", "error"))
        if aspect not in m["aspects"]:
            issues.append(Issue("aspect_unsupported", path, f"{ref['id']} does not support {aspect}", "error"))
    if s["subject"]["placement"] == "ground" and not catalog.get("world", s["world"]["id"]).get("hasGround"):
        issues.append(Issue("world_has_no_ground", "world.id", "placement 'ground' needs a world with a ground", "error"))


def _targets(s, catalog, profile, issues):
    markers = s.get("markers", [])
    for i, sh in enumerate(s["shots"]):
        t = sh.get("target")
        if t is not None and resolve_target(sh, profile, markers) is None:
            issues.append(Issue("unknown_target", f"shots[{i}].target", f"{t} does not exist", "error"))
        elif t is None and catalog.get("camera", sh["camera"]["id"])["framing"] == "detail" and profile.detailPoints:
            sh["target"] = {"detail": 0}
            issues.append(Issue("detail_target_defaulted", f"shots[{i}].target", "best detail point", "repaired"))


def check(script, profile, catalog):
    s, issues = validate_and_repair(script, catalog)
    if errors(issues):
        return CheckResult(False, s, issues)
    if s.get("markers"):
        check_anchors(s["markers"], profile, issues)
    _compat(s, catalog, profile, issues)
    _targets(s, catalog, profile, issues)
    if errors(issues):
        return CheckResult(False, s, issues)
    markers = s.get("markers", [])
    for i, shot in enumerate(s["shots"]):
        _fix_shot(i, shot, catalog, profile, s["format"]["aspect"], markers, issues)
    return CheckResult(not errors(issues), s, issues)
