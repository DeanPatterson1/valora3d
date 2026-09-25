"""Shared subject-motion rules (phase 5 Chunk 5). The checker calls them around the motion-path gates:
placement_rules before the compatibility checks (the placement decides the ground checks), motion_support
with them, apply_motion_rules after the weather rules and before realism and the travel gate. Pure.

A motion manifest may declare (validated in engine/catalog.py):
- placement "ground" | "float": float_drift repairs a ground script to float (placement_for_motion); a
  ground-contact motion in a float script is motion_needs_ground (error);
- rateCap {degS, repair: [{param, dir, integer?}]}: the peak angular rate of the subject, measured on the
  pose track (so it is the PERCEIVED rate, after any timeScale), is held under degS by walking the repair
  params (spin_rate_cap, repaired; motion_too_fast when no param can do it);
- shorten [{param, dir}]: a motion that stops or lands must be at rest SETTLE_BEFORE_END_S before the clip
  ends (TG-06 hero stillness): its startS moves earlier, else these params shorten it (motion_ends_unsettled,
  repaired; motion_too_long when nothing fits);
- needsCameraMove: plinth_spin never plays under a locked or constant-speed camera, the turntable negative
  control (spin_needs_camera_move);
- vehicle: the drive rules (vehicle_nose_uncertain, vehicle_speed_cap, wheel_strobe, spray_unavailable).
path.py may define supports(params, profile) -> (ok, note) (a shape the motion cannot sell, e.g. a squat
subject that cannot topple: motion_needs_profile with the note) and rest_s(params, profile, duration)."""
import math

from engine.camera_context import camera_sampler
from engine.issues import Issue
from engine.motion_path import camera_profile, pose_fn, posed_profile, rotation_matrix, shot_t

SPIN_CAP_DEG_S = 45.0          # P-C11: a subject turn reads as a turntable above this
SETTLE_BEFORE_END_S = 0.8      # TG-06: the hero holds still for the last 0.8 s
RATE_DT = 1.0 / 120.0          # pose sampling step for rates and rest times (s)
REST_TOL = 1e-5                # m / rad: a pose this close to the final one is at rest
CAMERA_RATE_CAP_DEG_S = 80.0   # T3-14: a subject may not sweep across the view faster than this
SPEED_STEP = 0.05              # vehicle_speed_cap lowers speedKmh in 5% steps
SPOKES = (5, 6, 7, 10)         # (eng) the spoke count is unknown: check the common ones (vehicles.md V-M01)
STROBE_BAND = 0.1              # frac(n omega / (2 pi fps)) within 0.1 of a whole number strobes
STROBE_NUDGE, STROBE_MAX = 0.03, 0.09   # (eng) nudge speedKmh in 3% steps, at most 9%
BISECT_STEPS = 16


def _mm(s, catalog):
    motion = s["subject"]["motion"]
    return motion, (catalog.get("motion", motion["id"]) or {})


def _path_attr(catalog, bid, name):
    if not catalog.has_motion_path(bid):
        return None
    catalog.load_motion_path(bid)
    return catalog._module_attr("motion", bid, "path.py", name)


def placement_rules(s, catalog, issues):
    """The motion decides where the subject is: float_drift floats (repaired), a ground-contact motion never
    plays floating (error)."""
    motion, mm = _mm(s, catalog)
    want, pl = mm.get("placement"), s["subject"].get("placement")
    if want == "float" and pl == "ground":
        s["subject"]["placement"] = "float"
        issues.append(Issue("placement_for_motion", "subject.placement",
                            f"{motion['id']} floats: placement 'ground' -> 'float'", "repaired"))
    elif want == "ground" and pl == "float":
        issues.append(Issue("motion_needs_ground", "subject.placement",
                            f"{motion['id']} needs the subject on the ground, not floating", "error"))


def motion_support(s, catalog, profile, issues):
    """path.supports(params, profile): a shape the motion cannot sell is reported with the block's own note."""
    motion, _ = _mm(s, catalog)
    fn = _path_attr(catalog, motion["id"], "supports")
    if fn is None:
        return
    ok, note = fn(motion.get("params") or {}, profile)
    if not ok:
        issues.append(Issue("motion_needs_profile", "subject.motion.id", f"{motion['id']}: {note}", "error"))


# --- pose-track measurements ----------------------------------------------------------------------------

def _times(t0, t1, dt=RATE_DT):
    n = max(1, int(math.ceil((t1 - t0) / dt)))
    return [t0 + (t1 - t0) * k / n for k in range(n + 1)]


def _angle(a, b):
    """Rotation angle (rad) between two 3x3 rotation matrices."""
    tr = sum(a[k][i] * b[k][i] for i in range(3) for k in range(3))     # trace(a^T b)
    return math.acos(max(-1.0, min(1.0, (tr - 1.0) / 2.0)))


def peak_rate_deg_s(pose_at, t0, t1, dt=RATE_DT):
    """The subject's peak angular rate (deg/s) over [t0, t1] from its pose track."""
    ts = _times(t0, t1, dt)
    mats = [rotation_matrix(pose_at(t)) for t in ts]
    return max((math.degrees(_angle(a, b)) / (t2 - t1_) for a, b, t1_, t2 in zip(mats, mats[1:], ts, ts[1:])),
               default=0.0)


def _pose_gap(a, b):
    return max(max(abs(a.offset[i] - b.offset[i]) for i in range(3)), _angle(rotation_matrix(a), rotation_matrix(b)))


REST_HORIZON_S = 30.0          # a motion still moving at the clip end is followed this far to find its rest


def rest_time(pose_at, duration, dt=RATE_DT):
    """The first time after which the pose never changes again (s): the motion is at rest from there. A motion
    still moving at the clip end is followed past it (up to REST_HORIZON_S), so the time it would need is known."""
    end_t = duration + REST_HORIZON_S
    ts = _times(0.0, end_t, dt)
    end = pose_at(end_t)
    last = 0.0
    for t in ts:
        if _pose_gap(pose_at(t), end) > REST_TOL:
            last = t
    return last + dt if last > 0.0 else 0.0


def _rest(s, catalog, profile):
    motion = s["subject"]["motion"]
    dur = float(s["format"]["durationS"])
    fn = _path_attr(catalog, motion["id"], "rest_s")
    if fn is not None:
        return fn(motion.get("params") or {}, profile, dur)
    return rest_time(pose_fn(s, profile, catalog), dur)


def _bisect(get_bad, lo, hi):
    """Smallest step from `lo` toward `hi` that makes get_bad False (get_bad(hi) must be False)."""
    for _ in range(BISECT_STEPS):
        mid = (lo + hi) / 2.0
        if get_bad(mid):
            lo = mid
        else:
            hi = mid
    return hi


def _walk(s, params, spec_of, repairs, bad):
    """Try each repair param in turn (dir down/up; integer steps of 1), keeping the others' changes; True
    when `bad` clears. The script is changed in place only on success of the whole walk."""
    for r in repairs:
        k, spec = r["param"], spec_of(r["param"])
        if spec is None:
            continue
        cur = float(params.get(k, spec["default"]))
        end = spec["min"] if r.get("dir", "down") == "down" else spec["max"]
        if r.get("integer"):
            step = -1 if end < cur else 1
            v = int(round(cur))
            while (v - end) * step < 0:
                v += step
                params[k] = v
                if not bad():
                    return True
            continue                   # keep the most helpful value; the next param builds on it
        params[k] = end
        if bad():
            continue
        def at(v, k=k):   # noqa: E306
            params[k] = round(v, 4)
            return bad()
        best = _bisect(at, cur, end)
        params[k] = round(best, 4)
        if bad():                      # rounding: step to the end rather than fail
            params[k] = end
        return True
    return False


def settle_rule(s, catalog, profile, issues):
    """motion_ends_unsettled: a stopping/landing motion reaches rest >= SETTLE_BEFORE_END_S before the end."""
    from engine.physics.applies import motion_flags
    motion, mm = _mm(s, catalog)
    flags = motion_flags(s, catalog)
    if not (flags.get("stops") or flags.get("lands")):
        return
    dur = float(s["format"]["durationS"])
    limit = dur - SETTLE_BEFORE_END_S
    params = motion.setdefault("params", {})
    before = dict(params)
    rest = _rest(s, catalog, profile)
    if rest <= limit + 1e-9:
        return
    spec_of = lambda k: mm["params"].get(k)          # noqa: E731
    fixed = False
    if "startS" in mm["params"]:
        spec = mm["params"]["startS"]
        start = float(params.get("startS", spec["default"]))
        params["startS"] = round(max(spec["min"], start - (rest - limit)), 4)
        fixed = _rest(s, catalog, profile) <= limit + 1e-9
    if not fixed:
        fixed = _walk(s, params, spec_of, mm.get("shorten", []), lambda: _rest(s, catalog, profile) > limit + 1e-9)
    changed = {k: (before.get(k), params[k]) for k in params if before.get(k) != params[k]}
    if fixed:
        issues.append(Issue("motion_ends_unsettled", "subject.motion.params",
                            f"{motion['id']} was still moving {rest:.2f} s into a {dur:g} s clip; "
                            f"{', '.join(f'{k} {a} -> {b}' for k, (a, b) in changed.items())}", "repaired"))
        return
    params.clear()
    params.update(before)
    issues.append(Issue("motion_too_long", "subject.motion",
                        f"{motion['id']} comes to rest at {rest:.2f} s; a {dur:g} s clip needs it still by "
                        f"{limit:.2f} s", "error"))


def rate_rule(s, catalog, profile, issues):
    """spin_rate_cap: the peak perceived turn rate stays under the manifest's rateCap.degS."""
    motion, mm = _mm(s, catalog)
    cap = mm.get("rateCap")
    if not cap:
        return
    dur = float(s["format"]["durationS"])
    params = motion.setdefault("params", {})
    before = dict(params)
    win = _path_attr(catalog, motion["id"], "window")      # where the turn happens (else the whole clip)

    def rate():
        t0, t1 = win(params, profile, dur) if win else (0.0, dur)
        return peak_rate_deg_s(pose_fn(s, profile, catalog), max(0.0, t0), min(dur, t1))
    peak = rate()
    bad = lambda: rate() > cap["degS"] + 1e-6   # noqa: E731
    if peak <= cap["degS"] + 1e-6:
        return
    if _walk(s, params, lambda k: mm["params"].get(k), cap.get("repair", []), bad):
        changed = {k: (before.get(k), params[k]) for k in params if before.get(k) != params[k]}
        issues.append(Issue("spin_rate_cap", "subject.motion.params",
                            f"{motion['id']} turned at {peak:.0f} deg/s (cap {cap['degS']:g}); "
                            f"{', '.join(f'{k} {a} -> {b}' for k, (a, b) in changed.items())}", "repaired"))
        return
    params.clear()
    params.update(before)
    issues.append(Issue("motion_too_fast", "subject.motion",
                        f"{motion['id']} turns at {peak:.0f} deg/s, over the {cap['degS']:g} deg/s cap", "error"))


def _locked(shot, catalog, profile, markers):
    """A camera that does not move over the shot, or a constant-speed programme (the turntable)."""
    from engine.targets import resolve_target
    m = catalog.get("camera", shot["camera"]["id"]) or {}
    if m.get("constantSpeed"):
        return True
    sample = camera_sampler(catalog, shot)
    tgt = resolve_target(shot, profile, markers) if m.get("framing") == "detail" else None
    a, b = sample(shot["camera"]["params"], profile, 0.0, tgt), sample(shot["camera"]["params"], profile, 1.0, tgt)
    return math.dist(a.position, b.position) < 1e-6 and math.dist(a.target, b.target) < 1e-6


def camera_move_rule(s, catalog, profile, issues):
    """spin_needs_camera_move: the turn plays while a camera moves, and never under a constant-speed one."""
    motion, mm = _mm(s, catalog)
    if not mm.get("needsCameraMove"):
        return
    window = _path_attr(catalog, motion["id"], "window")
    dur = float(s["format"]["durationS"])
    t0, t1 = window(motion.get("params") or {}, profile, dur) if window else (0.0, dur)
    shots = [sh for sh in s["shots"] if sh["startS"] < t1 and sh["endS"] > t0]
    locked = [_locked(sh, catalog, profile, s.get("markers", [])) for sh in shots]
    const = [sh["camera"]["id"] for sh in shots if (catalog.get("camera", sh["camera"]["id"]) or {}).get("constantSpeed")]
    if const or (shots and all(locked)):
        why = f"{', '.join(const)} is a constant-speed programme" if const else "every camera is locked"
        issues.append(Issue("spin_needs_camera_move", "shots",
                            f"{motion['id']} turns during {t0:.1f}-{t1:.1f} s while {why} (the turntable look)",
                            "error"))


# --- vehicles (Task 79) ---------------------------------------------------------------------------------

def _wheel_r(profile):
    ws = sorted(w["radius"] for w in (profile.wheels or []) if w.get("radius"))
    return ws[len(ws) // 2] if ws else None


def strobes(speed_kmh, radius, fps, spokes=SPOKES):
    """The spoke counts whose image repeats (or nearly) frame to frame at this speed: wagon-wheel risk."""
    omega = speed_kmh / 3.6 / radius
    out = []
    for n in spokes:
        f = (n * omega / (2.0 * math.pi * fps)) % 1.0
        if f <= STROBE_BAND or f >= 1.0 - STROBE_BAND:
            out.append(n)
    return out


def strobe_rule(s, profile, issues, shutter=None):
    """wheel_strobe: with a short shutter, nudge speedKmh by 3% steps (at most 9%) to the nearest clear speed;
    with a long one (the default 180 deg blurs the spokes) only record the risk."""
    from engine.compiler.tiers import SHUTTER
    shutter = SHUTTER if shutter is None else shutter
    params = s["subject"]["motion"].setdefault("params", {})
    r, fps = _wheel_r(profile), s["format"]["fps"]
    v = float(params.get("speedKmh", 0.0))
    if not r or v <= 0 or not strobes(v, r, fps):
        return
    if shutter >= 0.5:
        issues.append(Issue("wheel_strobe_risk", "subject.motion.params.speedKmh",
                            f"{v:g} km/h repeats {strobes(v, r, fps)}-spoke wheels frame to frame; the "
                            f"{shutter:g} shutter blurs them", "info"))
        return
    k = 1
    while k * STROBE_NUDGE <= STROBE_MAX + 1e-9:
        for sign in (1, -1):
            cand = round(v * (1 + sign * k * STROBE_NUDGE), 3)
            if not strobes(cand, r, fps):
                params["speedKmh"] = cand
                issues.append(Issue("wheel_strobe", "subject.motion.params.speedKmh",
                                    f"{v:g} -> {cand:g} km/h: clear of the wagon-wheel strobe", "repaired"))
                return
        k += 1
    issues.append(Issue("wheel_strobe_risk", "subject.motion.params.speedKmh",
                        f"no speed within 9% of {v:g} km/h is clear of the strobe", "info"))


def _bearing_rate(s, catalog, profile):
    """Peak rate (deg/s) at which the subject's centre sweeps across each anchor camera's view."""
    pose_at, fps, peak = pose_fn(s, profile, catalog), s["format"]["fps"], 0.0
    for sh in s["shots"]:
        m = catalog.get("camera", sh["camera"]["id"]) or {}
        if m.get("follows", "anchor") != "anchor":
            continue                                  # a tracking camera follows: exempt (rolling_track)
        sample = camera_sampler(catalog, sh)
        cam_p = camera_profile(sh, profile, pose_at, "anchor", fps=fps)
        prev = None
        for k in range(13):
            u = k / 12
            t = shot_t(sh, u, fps)
            cam = sample(sh["camera"]["params"], cam_p, u, None)
            c = posed_profile(profile, pose_at(t)).center
            b = math.atan2(c[1] - cam.position[1], c[0] - cam.position[0])
            if prev is not None and t > prev[1]:
                d = (b - prev[0] + math.pi) % (2 * math.pi) - math.pi
                peak = max(peak, abs(math.degrees(d)) / (t - prev[1]))
            prev = (b, t)
    return peak


def speed_rule(s, catalog, profile, issues):
    """vehicle_speed_cap: the distance driven in the window fits the world's drive lane, and an anchor camera
    never sees the car sweep faster than 80 deg/s (T3-14): speedKmh comes down in 5% steps."""
    motion, mm = _mm(s, catalog)
    params = motion.setdefault("params", {})
    spec = mm["params"]["speedKmh"]
    old = float(params.get("speedKmh", spec["default"]))
    lane = float((catalog.get("world", s["world"]["id"]) or {}).get("driveLaneM", 0.0))
    dist = _path_attr(catalog, motion["id"], "lane_distance")
    why = []
    if dist is not None and lane > 0 and dist(params, profile) > lane + 1e-9:
        d0 = dist(params, profile)
        good, bad = spec["min"], old                   # the fastest speed whose drive still fits the lane
        for _ in range(BISECT_STEPS + 8):
            mid = (good + bad) / 2.0
            if dist({**params, "speedKmh": mid}, profile) > lane + 1e-9:
                bad = mid
            else:
                good = mid
        params["speedKmh"] = max(spec["min"], math.floor(good * 1000.0) / 1000.0)
        why.append(f"{d0:.1f} m > the {lane:g} m lane")
    rate = _bearing_rate(s, catalog, profile)
    while rate > CAMERA_RATE_CAP_DEG_S and params["speedKmh"] > spec["min"] + 1e-9:
        params["speedKmh"] = round(max(spec["min"], params["speedKmh"] * (1 - SPEED_STEP)), 3)
        if not why or "deg/s" not in why[-1]:
            why.append(f"the view sweeps {rate:.0f} deg/s > {CAMERA_RATE_CAP_DEG_S:g} on an anchor camera "
                       "(a rolling_track camera keeps the real speed)")
        rate = _bearing_rate(s, catalog, profile)
    if params.get("speedKmh", old) != old:
        issues.append(Issue("vehicle_speed_cap", "subject.motion.params.speedKmh",
                            f"{old:g} -> {params['speedKmh']:g} km/h: {'; '.join(why)}", "repaired"))


def nose_rule(s, catalog, profile, issues):
    """H5: which end leads comes from nose_sign; when it is low confidence and facing is auto, the drive is a
    straight side pass-by (an arc would show the ambiguous nose leading into the turn)."""
    from engine.physics.shape import nose_sign
    params = s["subject"]["motion"].setdefault("params", {})
    _, conf = nose_sign(profile)
    if conf == "high" or params.get("facing", "auto") != "auto":
        return
    msg = "which end is the nose is uncertain: a straight side pass-by"
    if params.get("path", "straight") not in ("straight", "stop"):
        msg += f" (path {params['path']} -> straight)"
        params["path"] = "straight"
    issues.append(Issue("vehicle_nose_uncertain", "subject.motion.params.path", msg, "info"))


def spray_rule(s, issues):
    """VD-12 tyre spray is phase 6: a drive in the wet says so (info), the render goes ahead."""
    ids = {e.get("id") for e in s.get("effects", []) if isinstance(e, dict)}
    wet = bool(ids & {"rain", "wet_surface"}) or float((s["world"].get("params") or {}).get("wetness", 0.0) or 0.0) > 0
    if wet:
        issues.append(Issue("spray_unavailable", "subject.motion",
                            "Road spray isn't available yet; the car drives through the wet without spray", "info"))


def apply_motion_rules(s, catalog, profile, issues):
    """After weather, before realism and the travel gate: vehicle rules, settle, rate cap, camera move."""
    _, mm = _mm(s, catalog)
    if mm.get("vehicle"):
        nose_rule(s, catalog, profile, issues)
        speed_rule(s, catalog, profile, issues)
        strobe_rule(s, profile, issues)
        spray_rule(s, issues)
    settle_rule(s, catalog, profile, issues)
    rate_rule(s, catalog, profile, issues)
    camera_move_rule(s, catalog, profile, issues)
