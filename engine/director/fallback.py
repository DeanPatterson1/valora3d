"""The safe fallback (spec §4.6): a pre-verified script for the job's direction, re-fitted to this
subject by construction and then checked. It generalises harness/suites/v0/t3_attempt.json (checked
on all nine eval subjects). If even this fails the checker the job raises FallbackError: a failing
script never renders."""
import copy
import json
import math
import random

from engine import SCHEMA
from engine.checker import check
from engine.director.capabilities import assumption_lines, clip_line, play_clip_ref, wants_clip
from engine.director.details import middle_count, reverse_travel, vary_details, vary_lengths, vary_params
from engine.issues import errors
from engine.realism import realism_defaults

PACE_TARGET_S = {"calm": 2.5, "medium": 2.2, "hype": 1.6}   # middle-shot length target (eng)
HOOK_S, HERO_S, MIN_SEQ_S = 2.0, 3.0, 6.0                    # sequence: hookMaxS 2.5, lastShotMinS 1.5
SHORT_HERO_MIN_S, SHORT_DETAIL_MIN_S = 2.5, 1.0              # short (< MIN_SEQ_S) plan (eng): hero settle >= 1 s
GLOSSY = 0.2
ARC_DEG_PER_S = 20.0   # fallback arcs sweep <= 20 deg per second of shot (T3-14 caps the peak at 80 deg/s)
SLIDE_MIN_S = 2.5      # shorter macro shots push instead of slide: a short slide swings the azimuth past 80 deg/s
DARK_MOODS = ("premium_dark", "teal_night", "noir")
NOTE = "used the safe fallback script for this direction"
MAX_SHOTS_PER_10S = 7  # T3-01 upper bound (3-7 shots per 10 s)
MIN_MIDDLE_S = 1.0     # (eng) marker details never shorten middle shots below T3-02's 1.0 s median floor
DEFAULT_OPENER = "low_hero_push"
DETAIL_SCALES = (1.0, 0.5)   # (eng) layer-1 offset scales tried before the plain script (a lower tier retries)
_TIER_RANK = {"T1": 1, "T2": 2, "T3": 3}
FALLBACK_FLOOR_GLOSS, FALLBACK_HAZE = 0.4, 0.2   # phase-3 constants; layer 1 varies around them
DETAIL_CENTRES = {"world/studio_cyc": {"floorGloss": FALLBACK_FLOOR_GLOSS},
                  "effect/haze_volume": {"density": FALLBACK_HAZE}}
OPENER_HOOK = {  # hook cameras for non-default openers (values follow slot_camera's proven ranges) (eng)
    "arc_orbit": {"id": "arc_orbit", "params": {"startAzimuthDeg": 20.0, "sweepDeg": 25.0, "lensMm": 50.0,
                                                "elevationDeg": 6.0}},
}


STUDIO = "studio_cyc"
# capability -> the motion block a detected ask names (Task 88: honoured, never invented on a vague prompt)
MOTION_FOR = {"motion.drive": "drive", "motion.drop": "drop_settle", "motion.float": "float_drift",
              "motion.spin": "plinth_spin", "motion.slide": "slide_in", "motion.roll": "roll",
              "motion.topple": "topple", "motion.tumble": "toss_tumble"}
DRIVE_KMH = 40.0      # (eng) TG-46 / drive manifest: 30-60 km/h reads best
MOTION_NOTE = "the prompt asked for movement -> {id}"


def asked_motion(job, profile, catalog):
    """(ask, motion ref) for the first detected motion ask whose block exists on the menu: ref None when this
    subject cannot take it (facts or size), so the ask is reported instead of dropped. None without a motion ask:
    vague prompts ask for nothing, so they stay static (the fallback never invents motion)."""
    for a in job.asks:
        bid = MOTION_FOR.get(a["capability"])
        m = catalog.get("motion", bid) if bid else None
        if m is None or bid not in catalog.selectable_ids("motion"):
            continue
        lo, hi = m["subjectSizeM"]
        if not catalog.applies(m, profile) or not lo <= profile.longest <= hi:
            return a, None
        return a, {"id": bid, "params": {}}
    return None


def wind_hostable(world, catalog):
    """TG-24: a wind blows only when field/wind is on this catalog's menu (the site gate) and the world is
    outdoor (the studio keeps still air, windDefault 0)."""
    return "wind" in catalog.selectable_ids("field") and bool((world or {}).get("outdoor"))


def _wind_blocked(s, job, profile, catalog):
    """A wind ask this world cannot host (field/wind is deliverable, the world is indoor): reported with the
    world-blocked note, never silently dropped. A wind the menu lacks is already reported by the job's detect."""
    from engine.director.capabilities import blocked_note
    have = catalog.capabilities(profile)
    tags = {u["capability"] for u in s.get("unsupported", [])}
    for a in job.asks:
        tag = a["capability"]
        if not tag.startswith("wind.") or tag not in have or tag in tags:
            continue
        note = blocked_note(tag, "worldNote")
        s.setdefault("unsupported", []).append({"ask": a["ask"], "capability": tag, "note": note,
                                                "source": a["source"]})
        tags.add(tag)
        at = s["assumptions"].index(NOTE) if NOTE in s["assumptions"] else len(s["assumptions"])
        if note not in s["assumptions"]:
            s["assumptions"].insert(at, note)


def _world_lighting(world, profile, catalog=None):
    """The world's own light (allowed_lighting, Task 72); reflection_rig for gloss where the world pairs it
    (TG-33/TG-34). The studio keeps its phase-4 rule (see _script)."""
    from engine.lighting.pairing import allowed_lighting
    pairs = allowed_lighting(world) or []
    if catalog is not None:   # only what this catalog's menu offers: the site gate takes ungraded rigs (rim_neon) off it
        menu = set(catalog.selectable_ids("lighting"))
        pairs = [p for p in pairs if p in menu]
    if profile.glossShare >= GLOSSY and "reflection_rig" in pairs:
        return {"id": "reflection_rig", "params": {}}
    return {"id": pairs[0], "params": {}} if pairs else None


def _world_effects(direction, world, catalog):
    """The weather package the world can host (never an effect its requiresWorld fails), plus haze where no
    package effect is an atmosphere (T2-07 wants one outside the studio)."""
    from engine.director.axes import weather_package
    from engine.weather_rules import _needs_world
    pkg = [e for e in weather_package(getattr(direction, "weather", "dry"))
           if not _needs_world(((catalog.get("effect", e["id"]) or {}).get("physics") or {}).get("requiresWorld") or {},
                               world)]
    if any((catalog.get("effect", e["id"]) or {}).get("atmosphere") for e in pkg):
        return pkg
    return [{"id": "haze_volume", "params": {}}] + pkg


def _grow_cameras(shots, pace, fam, catalog):
    """Phase-5 cameras in middle shots, outdoors only (never the studio: phase-4 scripts stay byte-identical).
    TG-45 profile_slide (vehicles, the first motion slot, a foreground card outdoors); TG-44/43 medium pace a
    handheld walk, hype one dutch accent (never both); TG-42 calm lands the last middle shot on a reveal_rise."""
    sel = set(catalog.selectable_ids("camera"))
    mids = [i for i in range(1, len(shots) - 1) if shots[i]["purpose"] != "detail"]
    used = set()

    def put(i, cam):
        if i is not None and cam["id"] in sel and i not in used:
            shots[i]["camera"] = cam
            used.add(i)
            if fam == "vehicle":
                cam["params"].setdefault("fstop", 8.0)
    if fam == "vehicle" and mids:
        put(mids[0], {"id": "profile_slide", "params": {"foreground": True}})
    free = [i for i in mids if i not in used]
    if pace == "medium" and free:
        put(free[-1], {"id": "handheld_operator", "params": {}})    # shake 0.2-0.4 from layer 1 (TG-44)
    elif pace == "hype" and free:
        put(free[-1], {"id": "dutch_hero", "params": {}})           # roll 8-15 deg from layer 1 (TG-43)
    elif pace == "calm" and mids:
        put(mids[-1], {"id": "reveal_rise", "params": {}})          # the last middle shot, never a detail


MIDDLE_FLIP = 0.5    # (eng) outdoors, the middle shots play in reverse order on half the seeds (held variety)


def _reorder_middle(shots, seed):
    """Layer-1 structure outdoors (the studio keeps phase 4's order): on a seeded coin the middle shots swap
    their content (purpose, camera, target) end for end while the cut times stay, so a held direction does
    not repeat the same shot order (chunk-7 held variety fell 0.156 -> 0.115). A detail slide that lands in a
    slot too short for it pushes instead."""
    mids = shots[1:-1]
    if len(mids) < 2 or random.Random(f"detail:{seed}:order").random() >= MIDDLE_FLIP:
        return
    keys = ("purpose", "camera", "target")
    content = [{k: sh[k] for k in keys if k in sh} for sh in mids]
    for sh, c in zip(mids, reversed(content)):
        for k in keys:
            sh.pop(k, None)
        sh.update(c)
        if sh["camera"]["id"] == "macro_detail" and sh["endS"] - sh["startS"] < SLIDE_MIN_S:
            sh["camera"]["params"]["move"] = "push"


HERO_PUSH = 0.5      # (eng) outdoors, the hero lands on a slow low push instead of the arc on half the seeds


def _hero_push(shots, seed, catalog):
    """Outdoors only: on a seeded coin the hero's arc_orbit becomes a low_hero_push that lands where the arc
    would have (its landing azimuth, distance, lens and settle kept), so held directions vary their last
    camera too. The studio keeps phase 4's arc hero."""
    hero = shots[-1]["camera"]
    if (len(shots) < 2 or hero["id"] != "arc_orbit" or "low_hero_push" not in catalog.selectable_ids("camera")
            or random.Random(f"detail:{seed}:hero").random() >= HERO_PUSH):
        return
    p = hero["params"]
    land = p.get("startAzimuthDeg", 0.0) + p.get("sweepDeg", 0.0)
    q = {"azimuthDeg": round((land + 180.0) % 360.0 - 180.0, 4), "pushFrac": 0.1, "heightFrac": 0.15,
         "easing": "in_out_cubic"}
    for k in ("distance", "lensMm", "settleFrac", "fstop"):
        if k in p:
            q[k] = p[k]
    shots[-1]["camera"] = {"id": "low_hero_push", "params": q}


def _drive(s, shots, catalog):
    """TG-46: the car drives through one middle shot shot from a tracking car (rolling_track side follows it at
    its real speed; an anchor camera would force the 80 deg/s sweep cap onto the speed) and brakes onto its mark,
    so the detail and hero shots after it see it settled."""
    k = next((i for i in range(1, len(shots) - 1) if shots[i]["purpose"] != "detail"), None)
    if k is None or "rolling_track" not in catalog.selectable_ids("camera"):
        return False
    a, b = shots[k]["startS"], shots[k]["endS"]
    s["subject"]["motion"] = {"id": "drive", "params": {"path": "straight", "accel": "brake_to_stop",
                                                        "speedKmh": DRIVE_KMH, "startS": round(a, 4),
                                                        "driveS": round(max(1.0, b - a), 4)}}
    shots[k]["camera"] = {"id": "rolling_track", "params": {"mode": "side"}}
    return True


def grow(s, job, profile, catalog, pace, *, cams=True, motion=None):
    """Phase-5 additions on a built fallback script (Task 88): world lighting and weather outside the studio,
    the rolled wind where it can blow (wind_hostable), a detected motion ask, and phase-5 cameras. A studio
    direction without a motion or wind ask is returned untouched (byte-identical to phase 4)."""
    from engine.director.axes import wind_speed
    from engine.director.family import family
    d = job.direction
    wid = s["world"]["id"]
    world = catalog.get("world", wid) or {}
    if wid != STUDIO:
        light = _world_lighting(world, profile, catalog)
        if light is not None:
            s["lighting"] = light
        s["effects"] = _world_effects(d, world, catalog)
        if cams:
            _reorder_middle(s["shots"], job.seed)
            _hero_push(s["shots"], job.seed, catalog)
            _grow_cameras(s["shots"], pace, family(profile), catalog)
    if not wind_hostable(world, catalog):
        _wind_blocked(s, job, profile, catalog)
    elif getattr(d, "wind", "calm") != "calm":
        s["wind"] = {"id": "wind", "params": {"speedMs": wind_speed(d.wind, world, job.seed)}}
    if motion is not None:
        ask, ref = motion
        if ref["id"] == "drive":
            if not _drive(s, s["shots"], catalog):
                return s
        else:
            s["subject"]["motion"] = {"id": ref["id"], "params": dict(ref["params"])}
            place = (catalog.get("motion", ref["id"]) or {}).get("placement")
            if place:
                s["subject"]["placement"] = place
        s["assumptions"].insert(-1, MOTION_NOTE.format(id=ref["id"]))
    if wid != STUDIO and family(profile) == "vehicle":
        premium_look(s, job, profile, catalog)
    if wid != STUDIO:
        subject_side(s, profile, catalog)
        small_macro_reach(s, profile, catalog)
    return s


SMALL_MACRO_M = 0.5              # a subject up to this long ...
SMALL_MACRO_FRAME_K = 0.25       # ... is macro-shot with at least this share of its length across the frame


def small_macro_reach(s, profile, catalog):
    """Outdoor fallbacks: macro_detail's distance is in subject radii, which put a 0.3 m sneaker's lens 0.07 m off
    its laces (a 2.6 cm frame, the camera inside the shoe's bounds; site sheets 2026-09-29). A hand-sized subject's
    close-up asks for enough distance that the frame (36 mm / lens x distance) spans SMALL_MACRO_FRAME_K of its length
    at the end of a push too. The studio keeps the phase-4 numbers."""
    if profile.longest > SMALL_MACRO_M:
        return
    for sh in s["shots"]:
        if sh["camera"]["id"] != "macro_detail":
            continue
        prm = sh["camera"]["params"]
        top = catalog.get("camera", "macro_detail")["params"]["distance"]["max"]
        need = SMALL_MACRO_FRAME_K * profile.longest * prm["lensMm"] / 36.0 / max(profile.radius, 1e-6)
        if prm.get("move") == "push":
            need /= max(1.0 - prm.get("pushFrac", 0.0), 0.5)
        prm["distance"] = round(min(top, max(prm.get("distance", 0.0), need)), 4)


PREMIUM_CAM_M = (0.3, 0.7)       # (eng, owner-delegated look call 2026-09-25) outdoor car heroes: camera height
PREMIUM_LENS_MM = (35.0, 50.0)   # hero / pass lens
PREMIUM_FSTOP = 5.6
PREMIUM_WIDTH = 0.82             # the car spans ~80-85% of the frame width
PREMIUM_EDGE = 0.97              # (eng, round 7) ... its silhouette at most this far out (a 1.5% edge margin): fit at the
#                                  checker's 1.02 a 3/4 hero's near bumper sat 10 px off the frame edge
PREMIUM_DETAIL_MM = 85.0         # the long end a vehicle close-up uses (macro_detail's floor is 85 mm)
PREMIUM_WET = (0.6, 0.8)         # puddle share for a wet mirror ground
PREMIUM_POOL = 1.0               # round 7: and one large mirror pool the hook sees the car standing in
SIDE_TURN_STEP = 2.5             # (eng) degrees per step when a hero's bearing swings clear of a world occluder
PREMIUM_WIDTH_TOL = 0.06         # (eng) a swung hero still lands within this of PREMIUM_WIDTH
SIDE_SWING_STEP, SIDE_SWING_MAX = 5.0, 90.0   # (eng) subject_side's coarser bearing search (it runs on every
                                              # outdoor fallback the dice tries, the hero search only on cars)
QUICK_US = (0.0, 0.5, 1.0)       # the plan pre-test's first pass before all the checker's samples
SILHOUETTE_CHAMFER = 0.2         # (eng) plan-corner cut, x the shorter plan side, for the width a car fills


def _silhouette(lo, hi):
    """The bounds box with its plan corners cut by SILHOUETTE_CHAMFER x the shorter plan side: a car's nose and
    tail are rounded in plan, so the bare box corners overstate the width it fills (look 4ced996a / f67a165d:
    box 0.81-0.84 of the frame, the car itself ~0.74; the chamfered box reads 0.73-0.76)."""
    c = SILHOUETTE_CHAMFER * min(hi[0] - lo[0], hi[1] - lo[1])
    out = []
    for x, sx in ((lo[0], 1), (hi[0], -1)):
        for y, sy in ((lo[1], 1), (hi[1], -1)):
            for z in (lo[2], hi[2]):
                out += [(x + sx * c, y, z), (x, y + sy * c, z)]
    return out


def _width_frac(sample, params, profile, aspect, u):
    """Share of the frame width the car's silhouette spans at u, or None when it leaves the frame vertically or
    passes behind the camera. The silhouette is the projected mesh (the surface samples' hull points,
    geometry.silhouette_points); a profile without samples falls back to the chamfered bounds box."""
    from engine.geometry import project, silhouette_points
    pose = sample(params, profile, u)
    outline = (silhouette_points(getattr(profile, "surfaceSamples", None))
               or _silhouette(profile.boundsMin, profile.boundsMax))
    pts = [project(pose, c, aspect) for c in outline]
    if any(dd <= 0 for _, _, dd in pts) or max(abs(y) for _, y, _ in pts) > 1.0:
        return None
    xs = [x for x, _, _ in pts]
    return (max(xs) - min(xs)) / 2.0


def _premium_hero(sh, u, rng, profile, catalog, aspect, boxes=()):
    """TG-47 on one full-framing hero/hook: a low camera (0.3-0.7 m), 35-50 mm, f/5.6, and the distance that
    puts the car at ~82% of the frame width at the shot's landing (u). The camera stays on the subject's side of
    the world's declared occluders (boxes: a kerb, pavement or curb; look 4ced996a had the low hero behind the
    street's pavement slab). When the asked bearing looks across one, or cannot frame the car near that width
    (a near-front bearing in 16:9 tops out at ~0.66), the bearing swings by the smallest turn that clears and
    lands within PREMIUM_WIDTH_TOL, the distance re-solved at each. Every candidate is one the checker frames."""
    cam = sh["camera"]
    prm = cam["params"]
    h_cam = rng.uniform(*PREMIUM_CAM_M)
    prm["lensMm"] = round(rng.uniform(*PREMIUM_LENS_MM), 1)
    prm["fstop"] = PREMIUM_FSTOP
    m = catalog.get("camera", cam["id"])
    spec = m["params"]
    sample = catalog.load_camera_path(cam["id"])
    full = {k: v["default"] for k, v in spec.items()}

    az_key = "azimuthDeg" if cam["id"] == "low_hero_push" else "startAzimuthDeg"

    def at(d, turn=0.0):
        q = {**full, **prm, "distance": d}
        q[az_key] = round((q[az_key] + turn + 180.0) % 360.0 - 180.0, 4)
        if cam["id"] == "low_hero_push":
            lo, hi = spec["heightFrac"]["min"], spec["heightFrac"]["max"]
            q["heightFrac"] = round(min(hi, max(lo, h_cam / max(profile.sizeM[2], 1e-6))), 4)
        elif cam["id"] == "arc_orbit":
            r = max(d * profile.radius, 1e-6)
            el = math.degrees(math.asin(max(-1.0, min(1.0, (h_cam - profile.center[2]) / r))))
            q["elevationDeg"] = round(min(spec["elevationDeg"]["max"], max(spec["elevationDeg"]["min"], el)), 4)
        return q
    if cam["id"] not in ("low_hero_push", "arc_orbit"):
        return
    lo, hi = spec["distance"]["min"], spec["distance"]["max"]

    from engine.checker import _across, _blocked, _shot_verdict

    def fit(turn, clear, bound=math.inf):
        """(width error, distance) nearest PREMIUM_WIDTH (and under bound) among the distances the checker frames
        (the bounds box in frame at every sample, so the checker never has to move it) and, with clear, that look
        at the subject across no declared occluder; None when none does. Candidates are judged nearest first."""
        cands = []

        def add(d):
            q = at(d, turn)
            f = _width_frac(sample, q, profile, aspect, u)
            if f is not None and abs(f - PREMIUM_WIDTH) < bound:
                cands.append((abs(f - PREMIUM_WIDTH), d, q))
        step = (hi / lo) ** (1 / 47)
        for k in range(48):
            add(round(lo * step ** k, 4))
        for _, d0, _ in sorted(cands, key=lambda c: (c[0], c[1]))[:2]:   # the log grid steps ~4% of width:
            for j in range(-3, 4):                                       # refine the nearest two to ~1%
                if j:
                    add(round(min(hi, max(lo, d0 * step ** (j / 4))), 4))
        for e, d, q in sorted(cands, key=lambda c: (c[0], c[1])):
            if clear and (_across(sample, q, profile, boxes, us=QUICK_US) or _across(sample, q, profile, boxes)):
                continue                    # on or beyond a slab: rejected before any ray is cast
            if _shot_verdict(sample, q, profile, "full", aspect, silhouette=True,
                             silhouette_limit=PREMIUM_EDGE) == "ok" and not (
                    clear and _blocked(sample, q, profile, aspect, boxes)):
                return e, d
        return None

    memo = (aspect, cam["id"], json.dumps(prm, sort_keys=True), u, h_cam, tuple(profile.boundsMin),
            tuple(profile.boundsMax), tuple(boxes), id(catalog))
    if memo in _HERO_MEMO:                  # the dice rebuilds the same hero for every direction it weighs
        turn, best = _HERO_MEMO[memo]
    else:
        turn, best = 0.0, fit(0.0, False)
        stuck = best is not None and bool(boxes) and _blocked(sample, at(best[1]), profile, aspect, boxes)
        if best is None or best[0] > PREMIUM_WIDTH_TOL or stuck:
            steps = [s * k * SIDE_TURN_STEP for k in range(1, int(180.0 / SIDE_TURN_STEP) + 1) for s in (1, -1)]
            near = None                     # the smallest swing that lands near PREMIUM_WIDTH, else the
            for t in steps:                 # clear swing that comes nearest (ties: the smaller swing)
                b = fit(t, True, near[1][0] - 1e-9 if near else math.inf)
                if b is not None:
                    near = (t, b)
                    if b[0] <= PREMIUM_WIDTH_TOL:
                        break
            if near is not None and (best is None or stuck or near[1][0] < best[0]):
                turn, best = near
            # nothing clears: the unturned solve stands (blocked: the checker reports camera_view_blocked)
        _HERO_MEMO[memo] = (turn, best)
    if best is None:                        # nothing frames: the checker's own distance repair decides
        return
    q = at(best[1], turn)
    for k in ("distance", az_key, "heightFrac" if cam["id"] == "low_hero_push" else "elevationDeg"):
        prm[k] = q[k]


_HERO_MEMO = {}   # _premium_hero's (turn, (width error, distance)) per inputs
_SIDE_MEMO = {}   # subject_side's answer per (world, aspect, camera, params, shot length, subject bounds, catalog)
AZIMUTH_KEY = {"low_hero_push": "azimuthDeg", "dutch_hero": "azimuthDeg", "handheld_operator": "azimuthDeg",
               "reveal_rise": "azimuthDeg", "arc_orbit": "startAzimuthDeg", "turntable": "startAzimuthDeg"}


def subject_side(s, profile, catalog):
    """Every full-framing shot whose camera looks at the subject across a world's declared occluder (a kerb,
    pavement or curb: engine/occluders.py) at every distance that frames it swings its bearing by the smallest
    turn (SIDE_SWING_STEP steps, either way, up to SIDE_SWING_MAX) that clears it, at the framing distance
    nearest the one asked (log space). A shot already clear, a world without occluders, or a camera without a
    bearing is untouched; a shot no turn clears is left for the checker to report (camera_view_blocked)."""
    from engine.camera_context import camera_sampler
    from engine.checker import _across, _blocked, _distance_grid, _shot_verdict
    from engine.occluders import declared
    boxes = declared(catalog.get("world", s["world"]["id"]), profile)
    if not boxes:
        return
    aspect = s["format"]["aspect"]
    for sh in s["shots"]:
        cam = sh["camera"]
        key = AZIMUTH_KEY.get(cam["id"])
        m = catalog.get("camera", cam["id"]) or {}
        if key is None or m.get("framing") != "full":
            continue
        memo = (s["world"]["id"], aspect, cam["id"], json.dumps(cam["params"], sort_keys=True),
                sh["endS"] - sh["startS"], tuple(profile.boundsMin), tuple(profile.boundsMax), id(catalog))
        if memo in _SIDE_MEMO:               # the dice rebuilds the same shots for every direction it weighs
            if _SIDE_MEMO[memo] is not None:
                cam["params"][key], cam["params"]["distance"] = _SIDE_MEMO[memo]
            continue
        _SIDE_MEMO[memo] = None
        spec = m["params"]
        sample = camera_sampler(catalog, sh, profile, None)
        base = {**{k: v["default"] for k, v in spec.items()}, **cam["params"]}

        def good(q):
            return (not _across(sample, q, profile, boxes, us=QUICK_US) and not _across(sample, q, profile, boxes)
                    and _shot_verdict(sample, q, profile, "full", aspect, silhouette=True) == "ok"
                    and not _blocked(sample, q, profile, aspect, boxes))
        if good(base):
            continue
        grid = sorted(_distance_grid(spec["distance"]["min"], spec["distance"]["max"]),
                      key=lambda d: abs(math.log(d) - math.log(base["distance"])))
        if any(good({**base, "distance": d}) for d in grid):
            continue                          # the checker's distance repair clears it
        n = int(SIDE_SWING_MAX / SIDE_SWING_STEP)
        steps = [sg * k * SIDE_SWING_STEP for k in range(1, n + 1) for sg in (1, -1)]
        for turn in steps:
            az = round((base[key] + turn + 180.0) % 360.0 - 180.0, 4)
            d = next((d for d in grid if good({**base, key: az, "distance": d})), None)
            if d is not None:
                cam["params"][key], cam["params"]["distance"] = az, d
                _SIDE_MEMO[memo] = (az, d)
                break


def premium_look(s, job, profile, catalog):
    """TG-47 (owner delegated the look call, 2026-09-25): an outdoor car is shot like a car ad, not a
    configurator. Hook and hero: low camera, 35-50 mm, f/5.6, the car ~82% of the frame width; passes (profile
    slide, tracking) at f/5.6; close-ups at 85 mm; a wet world gets a mirror ground. Outdoors only: the studio
    stays byte-identical to phase 4."""
    from engine.occluders import declared
    rng = random.Random(f"premium:{job.seed}")
    aspect = s["format"]["aspect"]
    shots = s["shots"]
    boxes = declared(catalog.get("world", s["world"]["id"]), profile)
    for i, sh in enumerate(shots):
        cid = sh["camera"]["id"]
        if i in (0, len(shots) - 1) and catalog.get("camera", cid)["framing"] == "full":
            _premium_hero(sh, 1.0 if i else 0.0, random.Random(f"premium:{job.seed}:{i}"), profile, catalog, aspect,
                          boxes)
        elif cid in ("profile_slide", "rolling_track"):
            sh["camera"]["params"]["fstop"] = PREMIUM_FSTOP
        elif cid == "macro_detail":
            sh["camera"]["params"]["lensMm"] = PREMIUM_DETAIL_MM
    for e in s.get("effects", []):
        if e.get("id") == "wet_surface":
            e.setdefault("params", {}).update({"wetness": 1.0, "puddles": round(rng.uniform(*PREMIUM_WET), 3),
                                               "pool": PREMIUM_POOL})
            wp = (catalog.get("world", s["world"]["id"]) or {}).get("params", {})
            if "wetness" in wp:
                s["world"].setdefault("params", {})["wetness"] = 0.9


class FallbackError(RuntimeError):
    pass


def _plan(duration, pace, template, seq, n_markers=0, count_seed=None, catalog=None):
    if not seq:
        return ["hook", "hero"], [duration * 0.4, duration * 0.6]
    if duration < MIN_SEQ_S:
        # Short plan (3-6 s): open on a detail, cut to the hero. Two shots keep 3-7 cuts per 10 s
        # (T3-01); detail + hero give two scales and a detail (T3-03) and a >= 1.5x scale cut (T3-04);
        # the hero is long enough for its settle to hold >= 1 s still (T3-13).
        hero = min(duration - SHORT_DETAIL_MIN_S, max(SHORT_HERO_MIN_S, duration * 0.6))
        return ["detail", "hero"], [duration - hero, hero]
    rem = duration - HOOK_S - HERO_S
    n = max(1, math.ceil(rem / PACE_TARGET_S[pace] - 1e-9))
    if count_seed is not None and not n_markers:   # layer 1: any shot count the pace's cadence allows
        n = middle_count(n, duration, rem, pace, count_seed, catalog, MAX_SHOTS_PER_10S, MIN_MIDDLE_S)
    middle = [slot["purpose"] for slot in template[1:-1]] or ["detail"]
    slots = [middle[i % len(middle)] for i in range(n)]
    # Every marker gets its own detail shot (spec §2b) while the plan stays inside T3-01 (<= 7 shots per
    # 10 s) and middle shots stay >= MIN_MIDDLE_S. Extra details are added before any slot is converted.
    n_max = min(math.floor(MAX_SHOTS_PER_10S * duration / 10.0 + 1e-9) - 2, math.floor(rem / MIN_MIDDLE_S + 1e-9))
    need = n_markers
    while slots.count("detail") < need and len(slots) < n_max:
        slots.append("detail")
    for i in range(len(slots) - 1, -1, -1):  # still short: turn later non-detail slots into details,
        if slots.count("detail") >= need or slots.count("motion") <= 1:  # keeping one motion shot
            break
        if slots[i] == "motion":
            slots[i] = "detail"
    if n_markers:  # without markers the template's own slot order stands
        slots = _alternate(slots)
    n = len(slots)
    return ["hook"] + slots + ["hero"], [HOOK_S] + [rem / n] * n + [HERO_S]


def _alternate(slots):
    """Spread the detail slots between the others (two macro shots back to back read as one)."""
    det = [s for s in slots if s == "detail"]
    rest = [s for s in slots if s != "detail"]
    out = []
    while det or rest:
        if det:
            out.append(det.pop())
        if rest:
            out.append(rest.pop(0))
    return out


def _times(lengths, fps, duration):
    bounds, t = [0], 0.0
    for length in lengths[:-1]:
        t += length
        bounds.append(round(t * fps) / fps)
    bounds.append(duration)
    return list(zip(bounds, bounds[1:]))


def slot_camera(purpose, k, fam, jitter=0.0, detail_jitter=0.0, opener=DEFAULT_OPENER):
    """Camera for a template slot. Values follow t3_attempt (known to pass the 30-degree rule and
    framing on every eval subject); vehicles get f/8 on full frames (T3-21 anti-miniature)."""
    if purpose == "detail":
        base = 20.0 if k % 2 == 0 else -25.0
        return {"id": "macro_detail", "params": {"move": "slide" if k % 2 == 0 else "push", "lensMm": 100.0,
                                                 "azimuthOffsetDeg": max(-60.0, min(60.0, base + detail_jitter))}}
    if purpose in ("hook", "establish") and opener in OPENER_HOOK:
        cam = copy.deepcopy(OPENER_HOOK[opener])
        cam["params"]["startAzimuthDeg"] += jitter
    elif purpose in ("hook", "establish"):
        cam = {"id": "low_hero_push", "params": {"azimuthDeg": 35.0 + jitter, "distance": 4.0, "lensMm": 40.0,
                                                 "heightFrac": 0.15, "pushFrac": 0.12, "easing": "in_out_cubic"}}
    elif purpose == "motion":
        cam = {"id": "arc_orbit", "params": {"startAzimuthDeg": -100.0 + jitter, "sweepDeg": 40.0, "lensMm": 70.0,
                                             "elevationDeg": 8.0}}
    else:  # hero / packshot
        cam = {"id": "arc_orbit", "params": {"startAzimuthDeg": 60.0 + jitter, "sweepDeg": -30.0, "lensMm": 55.0,
                                             "settleFrac": 0.4}}
    if fam == "vehicle":
        cam["params"]["fstop"] = 8.0
    return cam


def _world(direction, details=False, catalog=None):
    """With layer 1 on, floorGloss is left unset so vary_details seeds it around FALLBACK_FLOOR_GLOSS;
    without it (the phase-3 default) the constant stands. Another world gets the tone only through its own
    toneParam (Task 73); a tone-less world (tone 'na') gets none."""
    w = getattr(direction, "world", "studio_cyc")
    if w == "studio_cyc":
        return {"id": w, "params": {"tone": direction.tone,
                                    **({} if details else {"floorGloss": FALLBACK_FLOOR_GLOSS})}}
    tp = ((catalog.get("world", w) or {}) if catalog is not None else {}).get("toneParam")
    return {"id": w, "params": {tp: direction.tone} if tp and direction.tone != "na" else {}}


def _script(job, profile, pace, jitter, seq, catalog, skip=frozenset(), opener=DEFAULT_OPENER, details=True,
            scale=1.0, cams=True, motion=None):
    template = catalog.get("edit", "sequence")["templates"][job.family]
    purposes, lengths = _plan(job.fmt["durationS"], pace, template, seq, len(job.markers),
                              count_seed=job.seed if details and scale >= 1.0 else None, catalog=catalog)
    if details:  # layer 1: a count inside the pace's cadence (_plan), lengths inside the template windows
        lengths = vary_lengths(purposes, lengths, job.fmt["durationS"], job.seed, catalog, template, scale=scale)
    shots, d = [], 0
    for i, ((a, b), p) in enumerate(zip(_times(lengths, job.fmt["fps"], job.fmt["durationS"]), purposes)):
        sh = {"startS": a, "endS": b, "purpose": p, "focus": "subject", "transitionIn": "cut",
              "camera": slot_camera(p, d if p == "detail" else i, job.family, jitter, opener=opener)}
        prm = sh["camera"]["params"]
        settles = "settleFrac" in prm   # the slot asked for a settle (the hero), before layer 1 adds params
        if details:  # layer 1: the fallback's camera values are centres, not choices (then the caps below)
            path = f"shots[{i}].camera"
            if sh["camera"]["id"] == "arc_orbit" and p != "hook" and reverse_travel(job.seed, path):
                # Travel the other way. A motion arc covers the same angles in reverse; the hero keeps its
                # landing angle (its end frame is the pack shot) and arrives from the other side.
                shift = prm["sweepDeg"] if p == "motion" else 2.0 * prm["sweepDeg"]
                prm["startAzimuthDeg"] = round((prm["startAzimuthDeg"] + shift + 180.0) % 360.0 - 180.0, 4)
                prm["sweepDeg"] = -prm["sweepDeg"]
            if sh["camera"]["id"] == "macro_detail" and reverse_travel(job.seed, path):
                prm["azimuthOffsetDeg"] = -prm["azimuthOffsetDeg"]   # the detail seen from its other side
            vary_params(prm, "camera", sh["camera"]["id"], path, job.seed, catalog, keep=(), scale=scale,
                        family=job.family, mood=job.direction.mood, timed=True)
        if settles:  # a short hero settles longer so >= 1 s of it is still (T3-13)
            prm["settleFrac"] = round(min(0.5, max(prm["settleFrac"], 1.0 / (b - a))), 3)
        if sh["camera"]["id"] == "arc_orbit":  # the sweep happens in the moving (unsettled) part only
            cap = ARC_DEG_PER_S * (b - a) * (1.0 - prm.get("settleFrac", 0.0))
            prm["sweepDeg"] = round(max(-cap, min(cap, prm["sweepDeg"])), 1)
        if sh["camera"]["id"] == "macro_detail" and b - a < SLIDE_MIN_S:
            prm["move"] = "push"
        if p == "detail":
            if d < len(job.markers):
                sh["target"] = {"marker": job.markers[d]["id"]}
                if not job.markers[d]["anchor"].get("normal"):
                    # No surface normal: the slide's arc is aimed blind and can swing past T3-14's cap
                    # (measured 85 deg/s on cesium_man, 30 s, seed 4); a push keeps the azimuth fixed.
                    prm["move"] = "push"
            else:
                usable = [k for k in range(len(profile.detailPoints)) if k not in skip]
                if usable:
                    sh["target"] = {"detail": usable[(d - len(job.markers)) % len(usable)]}
            d += 1
        shots.append(sh)
    notes = list(job.notes) + assumption_lines(job.detected)
    if len(job.markers) > d:  # the T3-01 shot cap left no room for these markers
        notes.append(f"{len(job.markers) - d} marker(s) had no room for their own shot")
    s = {"schema": SCHEMA, "seed": job.seed, "direction": {"id": job.direction.id, "source": job.direction.source},
         "prompt": job.prompt, "format": dict(job.fmt), "assumptions": notes + [NOTE],
         "subject": {"placement": "ground", "motion": {"id": "static", "params": {}}, "finishOverrides": []},
         "world": _world(job.direction, details, catalog),
         "lighting": ({"id": "reflection_rig", "params": {}} if profile.glossShare >= GLOSSY
                      else {"id": "softbox_three_point",
                            "params": {} if details else {"rimStrength": 1.2, "fillRatio": 0.35}}),
         "effects": ([{"id": "haze_volume", "params": {} if details else {"density": FALLBACK_HAZE}}]
                     if job.direction.mood in DARK_MOODS else []),
         "grade": {"id": "mood_grade", "params": {"preset": job.direction.mood}},
         "shots": shots}
    if seq and job.fmt["durationS"] >= MIN_SEQ_S:
        s["edit"] = {"id": "sequence", "params": {"pace": pace}}
    if job.markers:
        s["markers"] = copy.deepcopy(job.markers)
    if job.detected:
        s["unsupported"] = copy.deepcopy(job.detected)
    if wants_clip(job.asks, catalog, profile):  # a supported movement ask is played, never dropped
        s["subject"]["motion"] = play_clip_ref(job.asks, profile)
        s["assumptions"].insert(-1, clip_line(profile, s["subject"]["motion"]["params"]["clip"]))
    realism = realism_defaults(profile, catalog)  # Task 12a
    if realism:
        s["realism"] = realism
    grow(s, job, profile, catalog, pace, cams=cams, motion=motion)   # phase 5 (Task 88); studio untouched
    if details:  # layer 1 (Task 40a): seeded in-range look params the script left unset
        from engine.director.details import wind_centre
        centres = {**DETAIL_CENTRES, **wind_centre(s, profile, catalog)}   # Task 89: the wind crosses the hero
        vary_details(s, job.seed, catalog, centres=centres, scale=scale, family=job.family)
    return s


def _attempts(d, jitter):
    """(pace, jitter, seq, opener) tries. Pins win over the safety tweaks: a pinned opener or pace is kept
    through every try except the last resorts, and when both are pinned one is relaxed at a time (pace
    first, the less salient) before both are dropped. An unpinned interim direction (opener
    low_hero_push) reduces to phase 3's own four tries."""
    o, pinned = getattr(d, "opener", DEFAULT_OPENER), set(getattr(d, "pinned", ()))
    attempts = [(d.pace, jitter, True, o), (d.pace, 0.0, True, o)]
    if "opener" not in pinned:
        attempts.append((d.pace, 0.0, True, DEFAULT_OPENER))
    if "pace" not in pinned:
        attempts.append(("medium", 0.0, True, o if "opener" in pinned else DEFAULT_OPENER))
    if {"pace", "opener"} <= pinned:          # relax one pin at a time: keep the opener, then keep the pace
        attempts += [("medium", 0.0, True, o), (d.pace, 0.0, True, DEFAULT_OPENER)]
    if "opener" in pinned:                    # the unsequenced plan can still open on the pinned camera
        attempts.append(("medium", 0.0, False, o))
    attempts += [("medium", 0.0, True, DEFAULT_OPENER), ("medium", 0.0, False, DEFAULT_OPENER)]  # last resorts
    return list(dict.fromkeys(attempts))


def _pin_lines(s, d, catalog):
    """An assumption line for each pinned axis the passing script does not honour."""
    out = []
    pinned = set(getattr(d, "pinned", ()))
    if "opener" in pinned and s["shots"][0]["camera"]["id"] != d.opener:
        out.append(("opener", d.opener))
    if "pace" in pinned:
        from engine.director.floor import cadence_ok   # lazy: floor imports this module
        if not cadence_ok(s, d.pace, catalog):
            out.append(("pace", d.pace))
    return [f"your {axis} request ('{value}') did not pass the quality checks for this model, so it was adjusted"
            for axis, value in out]


def _first_passing(job, profile, catalog, pace, j, seq, skip, opener, details, cams=True, motion=None):
    """Layer 1 never costs a tier: the varied script is kept only when it passes the checker at the tier of
    the plain script (T3, or no worse than plain); else a smaller DETAIL_SCALES step, then plain."""
    from engine.director.floor import script_tier   # lazy: floor imports this module
    plain = None
    for scale in (DETAIL_SCALES if details else ()):
        s = _script(job, profile, pace, j, seq, catalog, skip, opener=opener, details=True, scale=scale,
                    cams=cams, motion=motion)
        r = check(s, profile, catalog)
        if not r.ok:
            continue
        t = script_tier(r.script, profile, catalog)
        if t == "T3":
            return s, r
        if plain is None:
            ps = _script(job, profile, pace, j, seq, catalog, skip, opener=opener, details=False, cams=cams,
                         motion=motion)
            plain = (ps, check(ps, profile, catalog))
        if not plain[1].ok or _TIER_RANK[t] >= _TIER_RANK[script_tier(plain[1].script, profile, catalog)]:
            return s, r
    if plain is None:
        ps = _script(job, profile, pace, j, seq, catalog, skip, opener=opener, details=False, cams=cams,
                         motion=motion)
        plain = (ps, check(ps, profile, catalog))
    return plain


def _variants(job, profile, catalog):
    """(cams, motion) tries, richest first: phase-5 cameras and the asked motion, then each dropped. A studio
    direction has no phase-5 cameras, so a vague studio prompt tries exactly phase 4's one variant."""
    motion = asked_motion(job, profile, catalog)
    outdoor = getattr(job.direction, "world", STUDIO) != STUDIO
    stage = motion if motion and motion[1] is not None else None
    out = [(c, m) for m in ([stage, None] if stage else [None]) for c in ([True, False] if outdoor else [False])]
    return out, motion


def build_fallback(job, profile, catalog, details=True):
    if details:   # a graded world replays the owner-graded look (engine/director/graded.py); phase-3 default keeps the dice path
        from engine.director.graded import build_graded
        graded = build_graded(job, profile, catalog)
        if graded is not None:
            return graded
    jitter = round(random.Random(f"fallback:{job.seed}").uniform(-10.0, 10.0), 1)
    last = None
    variants, asked = _variants(job, profile, catalog)
    for cams, motion in variants:
        for pace, j, seq, opener in _attempts(job.direction, jitter):
            skip = set()   # detail points this subject cannot frame (e.g. the car's second glossy peak)
            while True:
                s, last = _first_passing(job, profile, catalog, pace, j, seq, frozenset(skip), opener, details,
                                         cams=cams, motion=motion)
                if last.ok:
                    out = last.script
                    lines = _pin_lines(out, job.direction, catalog) if getattr(job.direction, "pinned", ()) else []
                    if lines:
                        notes = out["assumptions"]
                        at = notes.index(NOTE) if NOTE in notes else len(notes)
                        out["assumptions"] = notes[:at] + lines + notes[at:]
                    if asked and motion is None:
                        _motion_dropped(out, asked, catalog)
                    return out
                bad = {s["shots"][int(i.path[6:i.path.index("]")])].get("target", {}).get("detail")
                       for i in errors(last.issues)
                       if i.code in ("framing_unfixable", "detail_target_off_centre") and i.path.startswith("shots[")}
                bad -= {None} | skip
                if not bad:
                    break
                skip |= bad
    raise FallbackError("; ".join(f"{i.code} at {i.path}" for i in errors(last.issues)) or "fallback failed")


def _motion_dropped(s, asked, catalog):
    """An asked motion no variant could stage at full quality: reported, never silently dropped. The note says
    why: the model (facts, size) or, for a motion this model can do that travels, a world without room for it."""
    from engine.director.capabilities import blocked_note
    ask, ref = asked
    m = catalog.get("motion", MOTION_FOR.get(ask["capability"])) or {}
    world = catalog.get("world", s["world"]["id"]) or {}
    roomless = ref is not None and (m.get("subjectMotion") or {}).get("translates") and         float(world.get("driveLaneM", 0.0)) <= 0.0
    note = blocked_note(ask["capability"], "worldNote" if roomless else "profileNote")
    if any(u["capability"] == ask["capability"] for u in s.get("unsupported", [])):
        return
    s.setdefault("unsupported", []).append({"ask": ask["ask"], "capability": ask["capability"], "note": note,
                                            "source": ask["source"]})
    at = s["assumptions"].index(NOTE) if NOTE in s["assumptions"] else len(s["assumptions"])
    if note not in s["assumptions"]:
        s["assumptions"].insert(at, note)
