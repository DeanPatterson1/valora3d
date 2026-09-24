"""The checker: nothing renders unless check() returns ok (spec §4.6)."""
from dataclasses import dataclass, field
from engine.geometry import box_corners, frame_stats, point_in_box
from engine.issues import Issue, errors
from engine.script import validate_and_repair

SAMPLES_PER_SHOT = 12
BOX_MARGIN = 0.10
MIN_CAMERA_Z = 0.02
MIN_COVERAGE = 0.25
STEP = 1.15
MAX_STEPS = 12


@dataclass
class CheckResult:
    ok: bool
    script: dict
    issues: list = field(default_factory=list)


def _shot_verdict(sample, params, profile, framing, aspect):
    """Return 'ok', 'out' (move camera away) or 'in' (move closer)."""
    corners = box_corners(profile.boundsMin, profile.boundsMax)
    worst_small = False
    for k in range(SAMPLES_PER_SHOT):
        pose = sample(params, profile, k / (SAMPLES_PER_SHOT - 1))
        if pose.position[2] < MIN_CAMERA_Z:
            return "out"
        if point_in_box(pose.position, profile.boundsMin, profile.boundsMax, BOX_MARGIN):
            return "out"
        if framing == "full":
            st = frame_stats(pose, corners, aspect)
            if not st["allInFront"] or not st["inFrame"]:
                return "out"
            if st["coverage"] < MIN_COVERAGE:
                worst_small = True
    return "in" if worst_small else "ok"


def _fix_shot(i, shot, catalog, profile, aspect, issues):
    ref = shot["camera"]
    m = catalog.get("camera", ref["id"])
    sample = catalog.load_camera_path(ref["id"])
    spec = m["params"]["distance"]
    params = ref["params"]
    start = params["distance"]
    tried = set()
    for _ in range(MAX_STEPS + 1):  # +1 so the last step taken is also verified
        verdict = _shot_verdict(sample, params, profile, m["framing"], aspect)
        if verdict == "ok":
            if params["distance"] != start:
                issues.append(Issue("camera_distance_adjusted", f"shots[{i}].camera.params.distance",
                                    f"{start} -> {params['distance']:.3f}", "repaired"))
            return
        nxt = params["distance"] * (STEP if verdict == "out" else 1 / STEP)
        nxt = min(max(nxt, spec["min"]), spec["max"])
        key = round(nxt, 6)
        if key in tried or nxt == params["distance"]:
            break
        tried.add(key)
        params["distance"] = nxt
    params["distance"] = start
    issues.append(Issue("framing_unfixable", f"shots[{i}].camera",
                        f"no distance in [{spec['min']}, {spec['max']}] frames the subject", "error"))


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


def check(script, profile, catalog):
    s, issues = validate_and_repair(script, catalog)
    if errors(issues):
        return CheckResult(False, s, issues)
    _compat(s, catalog, profile, issues)
    if errors(issues):
        return CheckResult(False, s, issues)
    for i, shot in enumerate(s["shots"]):
        _fix_shot(i, shot, catalog, profile, s["format"]["aspect"], issues)
    return CheckResult(not errors(issues), s, issues)
