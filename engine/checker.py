"""The checker: nothing renders unless check() returns ok (spec §4.6)."""
import math
from dataclasses import dataclass, field
from engine.catalog import _has
from engine.clips import CLIP_MAP_VERSION, clips_current
from engine.geometry import box_corners, frame_stats, point_in_box, project
from engine.issues import Issue, errors
from engine.lighting.pairing import repair_lighting
from engine.markers import check_anchors
from engine.motion_path import camera_t, horizontal_travel, is_moving, pose_fn, posed_profile, posed_target, shot_t
from engine.motion_rules import apply_motion_rules, motion_support, placement_rules
from engine.physics.applies import resolve_realism, resolve_wind
from engine.script import validate_and_repair
from engine.sequence import check_sequence, recheck_cuts
from engine.clips import swept_profile
from engine.targets import resolve_target
from engine.weather_rules import check_weather

SAMPLES_PER_SHOT = 12
BOX_MARGIN = 0.10
MIN_CAMERA_Z = 0.02
MIN_COVERAGE = 0.25
GRID_POINTS = 32
DETAIL_CENTER = 0.6         # target stays within |ndc| <= 0.6 on detail shots (eng)
DETAIL_MIN_COVERAGE = 0.6   # T3-03: a detail shot fills >= 60% or overflows the frame
SLIDE_STEP = 0.05           # macro slideFrac repair step (eng)
TRAVEL_ALLOWANCE = 0.2      # (eng) x longest: travel any world allows without a drive lane (a bob, a nudge)


@dataclass
class CheckResult:
    ok: bool
    script: dict
    issues: list = field(default_factory=list)


def _shot_verdict(sample, params, profile, framing, aspect, target=None, moving=None):
    """Return 'ok', 'out' (move away), 'in' (move closer) or 'off' (target not centred); for a moving subject
    'exit' (the subject leaves the frame: move away) is kept apart from 'out' (the camera meets the ground or
    the subject), so only a real frame exit is reported as subject_left_frame (review chunk1 #9).
    moving(u) -> (camera profile, camera target, subject profile, subject target) for a moving subject:
    the camera programme is solved against the first pair, the subject judged where it really is (second
    pair). None = the static subject, byte-identical to phase 4."""
    corners = box_corners(profile.boundsMin, profile.boundsMax)
    small = False
    for k in range(SAMPLES_PER_SHOT):
        u = k / (SAMPLES_PER_SHOT - 1)
        if moving is None:
            cam_p, cam_t, subj, subj_t = profile, target, profile, target
        else:
            cam_p, cam_t, subj, subj_t = moving(u)
            corners = box_corners(subj.boundsMin, subj.boundsMax)
        pose = sample(params, cam_p, u, cam_t)
        if pose.position[2] < MIN_CAMERA_Z:
            return "out"
        if point_in_box(pose.position, subj.boundsMin, subj.boundsMax, BOX_MARGIN):
            return "out"
        st = frame_stats(pose, corners, aspect)
        if framing == "full":
            if not st["allInFront"] or not st["inFrame"]:
                return "out" if moving is None else "exit"
            if st["coverage"] < MIN_COVERAGE:
                small = True
        else:
            x, y, depth = project(pose, subj_t.point if subj_t else subj.center, aspect)
            if depth <= 0 or max(abs(x), abs(y)) > DETAIL_CENTER:
                return "off"
            if st["allInFront"] and st["inFrame"] and st["coverage"] < DETAIL_MIN_COVERAGE:
                small = True
    return "in" if small else "ok"


def _mover(shot, profile, target, pose_at, follows, fps):
    """moving(u) for _shot_verdict, memoised per u (the distance grid re-asks the same 12 samples)."""
    memo = {}

    def at(u):
        if u not in memo:
            cam_pose, live = pose_at(camera_t(shot, follows, u, fps)), pose_at(shot_t(shot, u, fps))
            memo[u] = (posed_profile(profile, cam_pose), posed_target(target, profile, cam_pose),
                       posed_profile(profile, live), posed_target(target, profile, live))
        return memo[u]
    return at


def _distance_grid(lo, hi):
    """GRID_POINTS geometric distances spanning [lo, hi] inclusive, rounded to 4 decimals
    BEFORE they are judged, so the value written back is exactly the value that passed."""
    if lo == hi:
        return [lo]
    ratio = hi / lo
    grid = [min(max(round(lo * ratio ** (j / (GRID_POINTS - 1)), 4), lo), hi) for j in range(GRID_POINTS)]
    grid[0], grid[-1] = lo, hi
    return grid


def _narrow_slide(i, sample, params, profile, aspect, target, issues, moving=None):
    """A detail target drifts off-centre by ~slideFrac * (1 - LOOK_DRIFT) scaled by the lens, not
    by distance, so the distance search cannot fix it: shrink the slide instead. False = unfixable."""
    old = params.get("slideFrac")
    if old is not None and params.get("move", "slide") == "slide":
        frac = old
        while frac > 0:
            frac = round(max(0.0, frac - SLIDE_STEP), 4)
            if _shot_verdict(sample, {**params, "slideFrac": frac}, profile, "detail", aspect, target, moving) != "off":
                params["slideFrac"] = frac
                issues.append(Issue("detail_slide_narrowed", f"shots[{i}].camera.params.slideFrac",
                                    f"{old} -> {frac}", "repaired"))
                return True
    issues.append(Issue("detail_target_off_centre", f"shots[{i}].camera",
                        f"the target leaves the central |ndc| <= {DETAIL_CENTER} at any slide", "error"))
    return False


def _fix_shot(i, shot, catalog, profile, aspect, markers, issues, motion=None):
    """Keep a passing distance; else pick the passing grid distance nearest in log space.
    A detail shot whose target is off-centre first has its slide narrowed (distance cannot help).
    motion = (pose_at, fps) for a moving subject (engine/motion_path), else None."""
    ref = shot["camera"]
    m = catalog.get("camera", ref["id"])
    sample = catalog.load_camera_path(ref["id"])
    spec = m["params"]["distance"]
    params = ref["params"]
    start = params["distance"]
    target = resolve_target(shot, profile, markers) if m["framing"] == "detail" else None
    moving = (_mover(shot, profile, target, motion[0], m.get("follows", "anchor"), motion[1])
              if motion is not None else None)
    verdict = _shot_verdict(sample, params, profile, m["framing"], aspect, target, moving)
    if verdict == "off":
        if not _narrow_slide(i, sample, params, profile, aspect, target, issues, moving):
            return
        verdict = _shot_verdict(sample, params, profile, m["framing"], aspect, target, moving)
    if verdict == "ok":
        return
    best, verdicts = None, set()  # best: (log distance to request, -distance); ties go larger
    for d in _distance_grid(spec["min"], spec["max"]):
        v = _shot_verdict(sample, {**params, "distance": d}, profile, m["framing"], aspect, target, moving)
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
        elif moving is not None and "exit" in verdicts:
            issues.append(Issue("subject_left_frame", f"shots[{i}].camera",
                                f"the moving subject leaves the frame at every distance in [{spec['min']}, {spec['max']}]",
                                "error"))
        elif moving is not None:   # never left the frame: too small, or the camera meets the ground / subject
            why = " and ".join(w for v, w in (("in", "too small in frame"), ("out", "the camera meets the ground or "
                               "the moving subject")) if v in verdicts)
            issues.append(Issue("framing_unfixable", f"shots[{i}].camera",
                                f"no distance in [{spec['min']}, {spec['max']}] frames the moving subject ({why})", "error"))
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
    # phase 5 (amendments 74/78/79): motions and effects have size ranges too (a car does not drop in)
    refs += [("motion", "subject.motion.id", s["subject"]["motion"])]
    refs += [("effect", f"effects[{i}]", e) for i, e in enumerate(s.get("effects", []))
             if isinstance(e, dict) and catalog.get("effect", e.get("id")) is not None]
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
    req = mm.get("requiresProfile") or []
    req = [req] if isinstance(req, str) else list(req)
    # computed facts (rollAxis...) go through catalog._has; animationClips keeps its raw presence test so a
    # stale clip map still reports clip_unavailable below, not a missing fact
    missing = [r for r in req if not (getattr(profile, r, None) if r == "animationClips" else _has(profile, r))]
    if missing:  # the message names the fact, so the repair hint stays one generic line
        issues.append(Issue("motion_needs_profile", "subject.motion.id",
                            f"{motion['id']} needs a model with {', '.join(missing)}", "error"))
    elif "animationClips" in req and not clips_current(profile.animationClips):  # never a silent wrong action
        issues.append(Issue("clip_unavailable", "subject.motion.params.clip",
                            "the model's clips were measured by an older ingest (clip map "
                            f"v{CLIP_MAP_VERSION} needed): re-ingest the model", "error"))
    elif "animationClips" in req and int(round(motion["params"].get("clip", 0))) >= len(profile.animationClips):
        issues.append(Issue("clip_unavailable", "subject.motion.params.clip",
                            f"the model has {len(profile.animationClips)} clip(s)", "error"))
    else:   # the facts are there: can this shape sell the motion? (path.supports, e.g. a squat topple)
        motion_support(s, catalog, profile, issues)


def _travel(s, catalog, profile, issues):
    """path_through_world: the subject's horizontal pivot travel (turning in place never counts) must fit
    the world's drive lane, or TRAVEL_ALLOWANCE x its length where the world has none. A motion that names
    its distance param (manifest distanceParam) is scaled down instead (motion_travel_capped)."""
    motion = s["subject"]["motion"]
    dur = float(s["format"]["durationS"])
    travel = horizontal_travel(pose_fn(s, profile, catalog), 0.0, dur)
    world = catalog.get("world", s["world"]["id"]) or {}
    allow = max(float(world.get("driveLaneM", 0.0)), TRAVEL_ALLOWANCE * profile.longest)
    if travel <= allow + 1e-9:
        return
    mm = catalog.get("motion", motion["id"]) or {}
    dp = mm.get("distanceParam")
    if dp and dp in mm["params"]:
        spec, params = mm["params"][dp], motion.setdefault("params", {})
        old = float(params.get(dp, spec["default"]))
        new = max(spec["min"], math.floor(old * allow / travel * 1e4) / 1e4)
        params[dp] = new
        if horizontal_travel(pose_fn(s, profile, catalog), 0.0, dur) <= allow + 1e-9:
            issues.append(Issue("motion_travel_capped", f"subject.motion.params.{dp}",
                                f"{old} -> {new}: travel {travel:.3f} m > {allow:.3f} m in {s['world']['id']}",
                                "repaired"))
            return
        params[dp] = old
    issues.append(Issue("path_through_world", "subject.motion",
                        f"{motion['id']} travels {travel:.3f} m; {s['world']['id']} allows {allow:.3f} m", "error"))


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
            issues.append(Issue("detail_target_surface", f"shots[{i}].target",
                                "no detail points or target: the detail shot aims at the surface facing the camera",
                                "warning"))


def check(script, profile, catalog):
    s, issues = validate_and_repair(script, catalog)
    if errors(issues):
        return CheckResult(False, s, issues)
    profile = swept_profile(profile, s)   # a walk played once/pingpong is framed over the ground it covers
    if s.get("markers"):
        check_anchors(s["markers"], profile, issues)
    repair_lighting(s, catalog, issues)   # the world's own light before any size/aspect check (Task 72)
    placement_rules(s, catalog, issues)   # the motion decides float vs ground before the ground checks
    _compat(s, catalog, profile, issues)
    _targets(s, catalog, profile, issues)
    if errors(issues):
        return CheckResult(False, s, issues)
    resolve_wind(s, catalog, issues, given=script.get("wind") if isinstance(script, dict) else None)
    check_weather(s, catalog, profile, issues)   # couplings first, so realism sees the final effect list
    if errors(issues):
        return CheckResult(False, s, issues)
    if is_moving(s, profile, catalog):   # settle, rate caps, camera move, vehicle rules (Chunk 5)
        apply_motion_rules(s, catalog, profile, issues)
        if errors(issues):
            return CheckResult(False, s, issues)
    resolve_realism(s, profile, catalog, issues)
    motion = None
    if is_moving(s, profile, catalog):   # static / play_clip / no path.py: exactly the phase-4 path
        _travel(s, catalog, profile, issues)
        if errors(issues):
            return CheckResult(False, s, issues)
        motion = (pose_fn(s, profile, catalog), s["format"]["fps"])
    markers = s.get("markers", [])
    for i, shot in enumerate(s["shots"]):
        _fix_shot(i, shot, catalog, profile, s["format"]["aspect"], markers, issues, motion)
    if not errors(issues) and (s.get("edit") or {}).get("id") == "sequence":
        changed = check_sequence(s, profile, catalog, issues)
        for i in sorted(changed):
            _fix_shot(i, s["shots"][i], catalog, profile, s["format"]["aspect"], markers, issues, motion)
        if changed:
            recheck_cuts(s, profile, catalog, issues)
    return CheckResult(not errors(issues), s, issues)
