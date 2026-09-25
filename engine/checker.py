"""The checker: nothing renders unless check() returns ok (spec §4.6)."""
import math
from dataclasses import dataclass, field
from engine.geometry import box_corners, frame_stats, point_in_box, project
from engine.issues import Issue, errors
from engine.markers import check_anchors
from engine.physics.applies import resolve_realism, resolve_wind
from engine.script import validate_and_repair
from engine.sequence import check_sequence, recheck_cuts
from engine.targets import resolve_target

SAMPLES_PER_SHOT = 12
BOX_MARGIN = 0.10
MIN_CAMERA_Z = 0.02
MIN_COVERAGE = 0.25
GRID_POINTS = 32
DETAIL_CENTER = 0.6         # target stays within |ndc| <= 0.6 on detail shots (eng)
DETAIL_MIN_COVERAGE = 0.6   # T3-03: a detail shot fills >= 60% or overflows the frame
SLIDE_STEP = 0.05           # macro slideFrac repair step (eng)


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


def _narrow_slide(i, sample, params, profile, aspect, target, issues):
    """A detail target drifts off-centre by ~slideFrac * (1 - LOOK_DRIFT) scaled by the lens, not
    by distance, so the distance search cannot fix it: shrink the slide instead. False = unfixable."""
    old = params.get("slideFrac")
    if old is not None and params.get("move", "slide") == "slide":
        frac = old
        while frac > 0:
            frac = round(max(0.0, frac - SLIDE_STEP), 4)
            if _shot_verdict(sample, {**params, "slideFrac": frac}, profile, "detail", aspect, target) != "off":
                params["slideFrac"] = frac
                issues.append(Issue("detail_slide_narrowed", f"shots[{i}].camera.params.slideFrac",
                                    f"{old} -> {frac}", "repaired"))
                return True
    issues.append(Issue("detail_target_off_centre", f"shots[{i}].camera",
                        f"the target leaves the central |ndc| <= {DETAIL_CENTER} at any slide", "error"))
    return False


def _fix_shot(i, shot, catalog, profile, aspect, markers, issues):
    """Keep a passing distance; else pick the passing grid distance nearest in log space.
    A detail shot whose target is off-centre first has its slide narrowed (distance cannot help)."""
    ref = shot["camera"]
    m = catalog.get("camera", ref["id"])
    sample = catalog.load_camera_path(ref["id"])
    spec = m["params"]["distance"]
    params = ref["params"]
    start = params["distance"]
    target = resolve_target(shot, profile, markers) if m["framing"] == "detail" else None
    verdict = _shot_verdict(sample, params, profile, m["framing"], aspect, target)
    if verdict == "off":
        if not _narrow_slide(i, sample, params, profile, aspect, target, issues):
            return
        verdict = _shot_verdict(sample, params, profile, m["framing"], aspect, target)
    if verdict == "ok":
        return
    best, verdicts = None, set()  # best: (log distance to request, -distance); ties go larger
    for d in _distance_grid(spec["min"], spec["max"]):
        v = _shot_verdict(sample, {**params, "distance": d}, profile, m["framing"], aspect, target)
        verdicts.add(v)
        if v != "ok":
            continue
        key = (abs(math.log(d) - math.log(start)), -d)
        if best is None or key < best[0]:
            best = (key, d)
    if best is None:
        if verdicts == {"off"}:
            issues.append(Issue("detail_target_off_centre", f"shots[{i}].camera",
                                f"the target leaves the central |ndc| <= {DETAIL_CENTER} at every distance", "error"))
        else:
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
    motion = s["subject"]["motion"]
    mm = catalog.get("motion", motion["id"])
    req = mm.get("requiresProfile")
    if req and not getattr(profile, req, None):
        issues.append(Issue("motion_needs_animation", "subject.motion.id",
                            f"{motion['id']} needs a model with {req}", "error"))
    elif req == "animationClips" and int(round(motion["params"].get("clip", 0))) >= len(profile.animationClips):
        issues.append(Issue("clip_unavailable", "subject.motion.params.clip",
                            f"the model has {len(profile.animationClips)} clip(s)", "error"))


def _targets(s, catalog, profile, issues):
    markers = s.get("markers", [])
    for i, sh in enumerate(s["shots"]):
        t = sh.get("target")
        if t is not None and resolve_target(sh, profile, markers) is None:
            issues.append(Issue("unknown_target", f"shots[{i}].target", f"{t} does not exist", "error"))
        elif t is None and catalog.get("camera", sh["camera"]["id"])["framing"] == "detail" and profile.detailPoints:
            sh["target"] = {"detail": 0}
            issues.append(Issue("detail_target_defaulted", f"shots[{i}].target", "best detail point", "repaired"))
        elif t is None and catalog.get("camera", sh["camera"]["id"])["framing"] == "detail":
            issues.append(Issue("detail_target_centre", f"shots[{i}].target",
                                "no detail points or target: the detail shot aims at the subject centre", "warning"))


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
    resolve_wind(s, catalog, issues, given=script.get("wind") if isinstance(script, dict) else None)
    resolve_realism(s, profile, catalog, issues)
    markers = s.get("markers", [])
    for i, shot in enumerate(s["shots"]):
        _fix_shot(i, shot, catalog, profile, s["format"]["aspect"], markers, issues)
    if not errors(issues) and (s.get("edit") or {}).get("id") == "sequence":
        changed = check_sequence(s, profile, catalog, issues)
        for i in sorted(changed):
            _fix_shot(i, s["shots"][i], catalog, profile, s["format"]["aspect"], markers, issues)
        if changed:
            recheck_cuts(s, profile, catalog, issues)
    return CheckResult(not errors(issues), s, issues)
