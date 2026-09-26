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
FLAG = {"sizeM": (2.0, 3.0), "distM": 2.2, "albedo": 0.01, "roughness": 1.0}
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
        if facing <= 0.1:
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


def detail_key(profile, pos, target, watts=None):
    """The 1.5 x 1 m source for a close detail: camera-left of the detail, a little above it."""
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


def shot_rigs(profile, set_ups):
    """One rig per shot. set_ups: [{shot, frame, detail, position, target}] (the camera at each shot's middle;
    target = the detail point for a detail shot, else None). Returns [{shot, frame, detail, key, flag}]."""
    out = []
    for u in set_ups:
        pos = tuple(u["position"])
        if u["detail"] and u.get("target") is not None:
            key, flag = detail_key(profile, pos, tuple(u["target"])), None
        else:
            key, flag = hero_key(profile, pos), windshield_flag(profile, pos)
        out.append({"shot": u["shot"], "frame": u["frame"], "detail": bool(u["detail"]), "key": key, "flag": flag})
    return out
