"""Per-shot reflection shaping on location (critique mat-v2 top-5 #2, 2026-09-25). Pure.

An overcast sky alone describes the sky, not the car: the hood and windshield become one pale reflection and the
side and wheels merge into the dark. A location crew keeps the overcast and, per set-up, adds one large soft key
on the camera's left across the visible side and a dark flag where the windshield would mirror the bright sky. The key goes where the visible side panel mirrors it
(a black car shows light only as reflection), else camera-left.
Each shot gets its own (the crew re-rigs between set-ups); the World is never brightened.

Numbers (critique mat-v2): hero key 4 x 3 m, 3-4 m out on camera-left, ~2.5 m high, bracketed 300 / 600 / 900 W
and stopped where the door and the front wheel separate by ~1/2 stop; a close detail gets a 1.5 x 1 m source
1-1.5 m from the detail, a little above it (bracket 40 / 80 / 120 W); the flag is 2 x 3 m, diffuse 0.01,
roughness 1. Sizes and distances are for a car and scale with the subject's radius (geometry.REF_RADIUS_M);
watts scale with the area, so the key's radiance is the same at any subject size."""
import math

from engine.geometry import REF_RADIUS_M

HERO_KEY = {"sizeM": (4.0, 3.0), "distM": 3.5, "heightM": 2.5, "sideDeg": 70.0, "watts": 35.0}
# The hero key's watts are where the bracket stopped (look-check 2026-09-25, rain_courtyard hero, final, door vs front
# wheel mean linear luminance): 60 W +1.33 stops, 120 W +1.80, 200 W +1.85, 600 W +1.55 (brighter base world);
# 20 W measured -0.17 stops (the band left the door), so the ~1/2-stop point sits between: 35 W. The critique's 300-900 W
# bracket assumed a real sky's exposure; in this scene's units 300 W already turned the door white.
DETAIL_KEY = {"sizeM": (1.5, 1.0), "distM": 1.25, "aboveM": 0.3, "sideDeg": 60.0, "watts": 40.0}   # bracket low end:
#   80 W washed the matte wheel-arch aero white in the wheel close-up (real_r5_court 0083)
BRACKET_W = (300.0, 600.0, 900.0)
DETAIL_BRACKET_W = (40.0, 80.0, 120.0)
FLAG = {"sizeM": (3.2, 4.2), "distM": 3.0, "albedo": 0.01, "roughness": 1.0, "feather": 0.45}
# Round 6: the 2 x 3 m flag at 2.2 m cut a hard-edged dark cap across the top of the windshield (real_r5_court
# 0030). It is now larger and further (its edge leaves the glass) and FEATHERED: opaque over the inner
# 1 - feather of each half-width, fading smoothly to clear at its edge, so what the glass shows is a gradient.
FLAG_REACH_PAD_M = 1.2        # the flag answers rays shorter than its distance + this (the subject's own)
WINDSHIELD_NZ = (0.45, 0.92)  # a sloped glossy patch: the windshield / hood plane a sky reflection whitens
MIN_SKYWARD = 0.05            # a mirror direction must climb at least this to reach the sky


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _mul(a, k):
    return tuple(x * k for x in a)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _unit(a):
    n = math.sqrt(_dot(a, a)) or 1.0
    return tuple(x / n for x in a)


def scale(profile):
    return profile.radius / REF_RADIUS_M


def toward_camera(pos, point):
    """Horizontal unit vector from a point toward the camera."""
    d = _sub(pos, point)
    return _unit((d[0], d[1], 0.0))


def camera_left(pos, point):
    """Horizontal unit vector to the camera's left, looking from pos at point."""
    d = toward_camera(pos, point)          # forward f = -d; left = (-f.y, f.x) = (d.y, -d.x)
    return (d[1], -d[0], 0.0)


def _swing(pos, point, deg):
    d, left = toward_camera(pos, point), camera_left(pos, point)
    a = math.radians(deg)
    return _add(_mul(d, math.cos(a)), _mul(left, math.sin(a)))


SIDE_NZ = 0.35               # a side panel: |n.z| below this (the door, the flank)
SIDE_MIN_FACING = 0.3        # round 6: a flank seen nearly edge-on (a near-front hero) mirrors the key behind the car,
#                              where no visible panel shows it (night_street az -78: the car went to a silhouette);
#                              below this facing the key stands camera-left instead


def _reflect(v, n):
    return _unit(_sub(v, _mul(n, 2.0 * _dot(v, n))))


def side_panel(profile, pos):
    """(point, normal) of the side panel that faces the camera most (area x facing), or None."""
    best = None
    for t in profile.reflectionTargets or []:
        n = _unit(t["normal"])
        if abs(n[2]) >= SIDE_NZ:
            continue
        facing = _dot(n, _unit(_sub(pos, t["point"])))
        if facing <= SIDE_MIN_FACING:
            continue
        score = t.get("area", 1.0) * facing
        if best is None or score > best[0]:
            best = (score, tuple(t["point"]), n)
    return None if best is None else best[1:]


def hero_key(profile, pos, watts=None):
    """The 4 x 3 m key for a full-frame set-up, where the visible side panel MIRRORS it: on a glossy body the
    door and shoulder separate from the wheels only by what they reflect, so the source goes on the side panel's
    mirror direction (horizontal), 3.5 m out and 2.5 m high, and shows as a soft band along the shoulder. With no
    side panel facing the camera it stands camera-left of the subject (the critique's default placement)."""
    s, c = scale(profile), profile.center
    k = HERO_KEY
    ground = profile.boundsMin[2]
    panel = side_panel(profile, pos)
    if panel is not None:
        pt, n = panel
        r = _reflect(_unit(_sub(pt, pos)), n)
        h = _unit((r[0], r[1], 0.0))
        base = pt
    else:
        h, base = _swing(pos, c, k["sideDeg"]), c
    centre = (base[0] + h[0] * k["distM"] * s, base[1] + h[1] * k["distM"] * s, ground + k["heightM"] * s)
    aim = base if panel is not None else c
    return {"center": centre, "facing": _unit(_sub(aim, centre)), "sizeX": k["sizeM"][0] * s,
            "sizeY": k["sizeM"][1] * s, "watts": (k["watts"] if watts is None else watts) * s * s,
            "mirrors": panel is not None}


WHEEL_KEY = {"sizeM": (2.0, 1.5), "distM": 1.6, "watts": 28.0, "reachK": 1.15}
# Round 8 (owner's r7 grade: "spokes, rotor, tyre and wheel well sit in one dark tonal range"): a close-up on a wheel
# gets its source where the wheel FACE mirrors the camera (the outward axle normal), 2 x 1.5 m at 1.6 m, so one broad
# soft reflection runs across the spokes, rotor and caliper and separates them by finish; the rubber (rough) only
# takes its diffuse share. 28 W: 80 W (the detail key's radiance) and 45 W washed the matte arch liner grey-white.


def wheel_at(profile, target):
    """The profile wheel whose face the detail target is on (within reachK x its radius of its centre), or None."""
    best = None
    for w in getattr(profile, "wheels", None) or []:
        c, r = w.get("center"), w.get("radius")
        if not c or not r:
            continue
        d = math.dist(c, target)
        if d <= WHEEL_KEY["reachK"] * r and (best is None or d < best[0]):
            best = (d, w)
    return None if best is None else best[1]


def wheel_key(profile, pos, wheel, watts=None):
    """The broad source a wheel close-up mirrors in the wheel face (see WHEEL_KEY)."""
    s, k = scale(profile), WHEEL_KEY
    c = tuple(wheel["center"])
    ax = _unit(tuple(wheel.get("axis") or (1.0, 0.0, 0.0)))
    out = _sub(c, profile.center)
    n = ax if _dot(ax, out) >= 0 else _mul(ax, -1.0)          # the face's outward normal
    r = _reflect(_unit(_sub(c, pos)), n)
    if _dot(r, n) <= 0.05:                                     # a grazing view: the mirror runs along the face
        r = _unit(_add(r, _mul(n, 0.3)))
    centre = _add(c, _mul(r, k["distM"] * s))
    return {"center": centre, "facing": _unit(_sub(c, centre)), "sizeX": k["sizeM"][0] * s,
            "sizeY": k["sizeM"][1] * s, "watts": (k["watts"] if watts is None else watts) * s * s}


def detail_key(profile, pos, target, watts=None):
    """The 1.5 x 1 m source for a close detail: camera-left of the detail, a little above it. A wheel close-up
    gets wheel_key instead (round 8)."""
    w = wheel_at(profile, target)
    if w is not None:
        return wheel_key(profile, pos, w, watts=None if watts is None else watts * 2.0)
    s, k = scale(profile), DETAIL_KEY
    v = _swing(pos, target, k["sideDeg"])
    centre = (target[0] + v[0] * k["distM"] * s, target[1] + v[1] * k["distM"] * s, target[2] + k["aboveM"] * s)
    return {"center": centre, "facing": _unit(_sub(target, centre)), "sizeX": k["sizeM"][0] * s,
            "sizeY": k["sizeM"][1] * s, "watts": (k["watts"] if watts is None else watts) * s * s}


def windshield_flag(profile, pos):
    """The 2 x 3 m dark flag where the camera's view of the windshield plane mirrors to the sky, or None
    (no sloped glossy patch faces the camera, or its mirror direction does not reach the sky)."""
    s, best = scale(profile), None
    for t in profile.reflectionTargets or []:
        n = _unit(t["normal"])
        if not WINDSHIELD_NZ[0] <= n[2] <= WINDSHIELD_NZ[1]:
            continue
        facing = _dot(n, _unit(_sub(pos, t["point"])))
        if facing <= 0:
            continue
        score = t.get("area", 1.0) * facing
        if best is None or score > best[0]:
            best = (score, t["point"], n)
    if best is None:
        return None
    _, p, n = best
    v = _unit(_sub(p, pos))
    r = _unit(_sub(v, _mul(n, 2.0 * _dot(v, n))))
    if r[2] < MIN_SKYWARD:
        return None
    dist = FLAG["distM"] * s
    return {"center": _add(p, _mul(r, dist)), "facing": _mul(r, -1.0), "sizeX": FLAG["sizeM"][0] * s,
            "sizeY": FLAG["sizeM"][1] * s, "reachM": dist + FLAG_REACH_PAD_M * s, "aim": tuple(p)}


SHEEN = {"sideM": 3.0, "heightM": 3.0, "lengthK": 3.0, "widthM": 0.3, "wattsPerM2": 50.0, "minFacing": 0.02}
# Round 7 (night street): after dark a black car read as a silhouette. What draws a black car at night is the street
# light its panels mirror: a long, thin line along the shoulder. SHEEN is that street light for every full-frame
# set-up: a strip parallel to the car's long axis on the flank facing the camera, sideM out from the flank and
# heightM up (where a shoulder curving ~20 deg skyward mirrors a low camera), lengthK x the car's length so the whole
# flank finds it, widthM wide, aimed at the flank. Invisible to the camera and linked to the subject alone, it shows
# only as the paint's reflection. Car-scaled (geometry.REF_RADIUS_M); watts scale with the strip's area.


def _long_axis(profile):
    fwd = (getattr(profile, "vehicle", None) or {}).get("forwardAxis")
    if fwd:
        return max((0, 1), key=lambda k: abs(fwd[k]))
    size = profile.sizeM
    return 0 if size[0] >= size[1] else 1


def shoulder_sheen(profile, pos):
    """The street-light strip for a full-frame set-up at camera `pos`: {center, facing, axis (its long side),
    sizeX (along axis), sizeY, watts, side}, or None when neither flank faces the camera (a head-on view)."""
    s, c, k = scale(profile), profile.center, SHEEN
    lo, hi = profile.boundsMin, profile.boundsMax
    ia = _long_axis(profile)
    ib = 1 - ia
    best = None
    for sign in (1.0, -1.0):
        n0 = [0.0, 0.0, 0.0]
        n0[ib] = sign
        mid = list(c)
        mid[ib] = hi[ib] if sign > 0 else lo[ib]
        facing = _dot(n0, _unit(_sub(pos, mid)))
        if facing > k["minFacing"] and (best is None or facing > best[0]):
            best = (facing, sign, tuple(mid))
    if best is None:
        return None
    _, sign, mid = best
    centre = list(mid)
    centre[ib] += sign * k["sideM"] * s
    centre[2] = lo[2] + k["heightM"] * s
    axis = [0.0, 0.0, 0.0]
    axis[ia] = 1.0
    length = k["lengthK"] * (hi[ia] - lo[ia])
    width = k["widthM"] * s
    return {"center": tuple(centre), "facing": _unit(_sub(mid, centre)), "axis": tuple(axis), "sizeX": length,
            "sizeY": width, "watts": k["wattsPerM2"] * length * width, "side": sign}


FRONT = {"alongK": 0.62, "sideK": 0.8, "zFrac": 0.6, "normal": (0.45, 0.30, 0.84), "distM": 3.0,
         "sizeM": (3.0, 2.0), "wattsPerM2": 3.0}
# Round 8 (owner's r7 grade, courtyard: "the front bumper and wheels vanish into black while the windshield and upper
# body carry busy reflections"): one broad soft scrim where the near front fender's crest mirrors the camera, so the
# fender and the hood's edge show one smooth gradient that reveals their shape instead of the trees. The crest point
# sits alongK of the half-length toward the end nearest the camera (a 3/4 hero's front wheel), sideK of the
# half-width out on the camera's side, zFrac up; its normal leans (side, toward that end, up) by `normal`. The key's
# radiance (35 W over 4 x 3 m ~ 3 W/m^2), 3 x 2 m at 3 m, light-linked to the subject, never seen by the camera.


def front_scrim(profile, pos):
    """The fender scrim for a full-frame set-up at `pos`, or None when the crest's mirror direction does not climb
    (a camera above the fender sees the ground mirrored there)."""
    s, c, k = scale(profile), profile.center, FRONT
    lo, hi = profile.boundsMin, profile.boundsMax
    ia = _long_axis(profile)
    ib = 1 - ia
    near = 1.0 if abs(pos[ia] - hi[ia]) < abs(pos[ia] - lo[ia]) else -1.0
    side = 1.0 if pos[ib] >= c[ib] else -1.0
    p = [0.0, 0.0, lo[2] + k["zFrac"] * (hi[2] - lo[2])]
    p[ia] = c[ia] + near * k["alongK"] * 0.5 * (hi[ia] - lo[ia])
    p[ib] = c[ib] + side * k["sideK"] * 0.5 * (hi[ib] - lo[ib])
    n = [0.0, 0.0, k["normal"][2]]
    n[ib], n[ia] = side * k["normal"][0], near * k["normal"][1]
    r = _reflect(_unit(_sub(tuple(p), pos)), _unit(tuple(n)))
    if r[2] < MIN_SKYWARD:
        return None
    centre = _add(tuple(p), _mul(r, k["distM"] * s))
    w, h = k["sizeM"][0] * s, k["sizeM"][1] * s
    return {"center": centre, "facing": _unit(_sub(tuple(p), centre)), "axis": (-r[1], r[0], 0.0), "sizeX": w,
            "sizeY": h, "watts": k["wattsPerM2"] * w * h}


NIGHT_WHEEL_W = 10.0   # (eng, round 8) after dark a full-frame shot's near wheel mirrors a dim street light (the
#                        wheel_key placement at this power): the wheel separates from the lower body, the frame
#                        does not brighten (the day wheel close-up's key is 45 W)


def near_wheel(profile, pos):
    """The profile wheel nearest the camera (its centre), or None."""
    ws = [w for w in (getattr(profile, "wheels", None) or []) if w.get("center") and w.get("radius")]
    return min(ws, key=lambda w: math.dist(w["center"], pos)) if ws else None


def shot_rigs(profile, set_ups, sheen=False, front=False):
    """One rig per shot. set_ups: [{shot, frame, detail, position, target}] (the camera at each shot's middle;
    target = the detail point for a detail shot, else None). Returns [{shot, frame, detail, key, flag, sheen}];
    sheen (after dark): a full-frame set-up also gets its shoulder_sheen strip (None on a detail or head-on), a dim
    glint on its nearest wheel (round 8) and no windshield flag (at night the glass keeps its faint reflections);
    front (by day, round 8): its front_scrim."""
    out = []
    for u in set_ups:
        pos = tuple(u["position"])
        if u["detail"] and u.get("target") is not None:
            # round 6: a close-up keeps the flag too. Without it the hood mirrored the open overcast edge to edge,
            # and on that bright paint every bead read as a dark speck (a real bead on black paint mirrors less
            # than the clear coat around it); under the flag the paint goes dark like the film's and the beads
            # show their highlights and refraction (real_r6 drop test, frame 128)
            key, flag = detail_key(profile, pos, tuple(u["target"])), windshield_flag(profile, pos)
        else:
            key, flag = hero_key(profile, pos), windshield_flag(profile, pos)
        full = not (u["detail"] and u.get("target") is not None)
        if sheen:
            flag = None
        sh = shoulder_sheen(profile, pos) if sheen and full else None
        nw = near_wheel(profile, pos) if sheen and full else None
        glint = None
        if nw is not None:
            glint = {"axis": (0.0, 0.0, 1.0), **wheel_key(profile, pos, nw, watts=NIGHT_WHEEL_W)}
        fr = front_scrim(profile, pos) if front and full else None
        out.append({"shot": u["shot"], "frame": u["frame"], "detail": bool(u["detail"]), "key": key, "flag": flag,
                    "sheen": sh, "front": fr, "glint": glint})
    return out
