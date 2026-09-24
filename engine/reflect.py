"""Reflection-shaped lighting (vehicles.md §1 V-L01..L11; products.md P-L01..L07). Pure maths:
the compiler turns LightSpecs into Blender area lights and black cards (Task 22).
Every size/height/ratio default is (eng): calibrate through harness items T3-06..T3-09."""
import math
from dataclasses import dataclass

from engine.geometry import _dot, _norm, _sub, point_in_box

LIGHT_BOX_MARGIN = 0.10   # same margin the checker keeps cameras out of
MIN_Z_FRAC = 0.05         # lights stay above the floor by this fraction of the subject radius
MAX_STRIPS = 2            # V-L04: overhead + 2 strips = at most 3 big planes


@dataclass(frozen=True)
class LightSpec:
    name: str
    role: str       # overhead | strip | accent | rim | negfill | key | fill
    center: tuple
    facing: tuple   # unit vector the emitting face points along
    sizeX: float
    sizeY: float
    power: float    # relative radiance; build.py multiplies by area and a calibrated constant
    # V-L01: every rig object (area lights, and black cards / negative fill) must be invisible to
    # camera rays but visible in glossy reflections. The compiler (Task 22) MUST set the Blender
    # object's camera visibility from this (off), never leave Blender's default (on).
    cameraVisible: bool = False


@dataclass(frozen=True)
class RigLayout:
    lights: tuple
    ambient: float  # world fill relative to the overhead radiance (= 1 / keyFill, V-L11 / P-L05)
    notes: tuple = ()  # targets skipped and why (e.g. an ingest normal of zero length)


def _has_normal(t):
    n = t.get("normal") or (0.0, 0.0, 0.0)
    return math.sqrt(_dot(n, n)) > 1e-12


def mirror_dir(point, normal, camera):
    if not _has_normal({"normal": normal}):
        raise ValueError("mirror_dir: zero-length surface normal")
    d = _norm(_sub(point, camera))
    n = _norm(normal)
    k = 2.0 * _dot(d, n)
    return _norm((d[0] - k * n[0], d[1] - k * n[1], d[2] - k * n[2]))


def _along(p, v, t):
    return (p[0] + v[0] * t, p[1] + v[1] * t, p[2] + v[2] * t)


def _place(p, direction, dist, profile):
    """Centre at p + direction*dist, lifted above the floor and pushed out of the subject box;
    facing points back at p."""
    c = _along(p, direction, dist)
    zmin = MIN_Z_FRAC * profile.radius
    if c[2] < zmin:
        c = (c[0], c[1], zmin)
    cx, cy, _ = profile.center
    for _ in range(40):
        if not point_in_box(c, profile.boundsMin, profile.boundsMax, LIGHT_BOX_MARGIN):
            break
        h = (c[0] - cx, c[1] - cy, 0.0)
        h = _norm(h) if (h[0] or h[1]) else (1.0, 0.0, 0.0)
        c = (c[0] + h[0] * 0.1 * profile.radius, c[1] + h[1] * 0.1 * profile.radius, c[2])
    return c, _norm(_sub(p, c))


def _targets(profile, notes):
    """Top + flank targets from ingest; each missing or unusable one synthesized from bounds."""
    lo, hi = profile.boundsMin, profile.boundsMax
    cx, cy, _ = profile.center
    by = {}
    for t in profile.reflectionTargets:
        if _has_normal(t):
            by[t["kind"]] = t
        else:
            notes.append(f"reflection target {t['kind']} has a zero-length normal; synthesized from bounds")
    top = by.get("top") or {"kind": "top", "point": [cx, cy, hi[2]], "normal": [0, 0, 1]}
    z = lo[2] + 0.6 * (hi[2] - lo[2])
    synth = {"+x": {"kind": "+x", "point": [hi[0], cy, z], "normal": [1, 0, 0]},
             "-x": {"kind": "-x", "point": [lo[0], cy, z], "normal": [-1, 0, 0]},
             "+y": {"kind": "+y", "point": [cx, hi[1], z], "normal": [0, 1, 0]},
             "-y": {"kind": "-y", "point": [cx, lo[1], z], "normal": [0, -1, 0]}}
    return top, [by.get(k) or synth[k] for k in ("+x", "-x", "+y", "-y")]


def rig_layout(profile, camera, params):
    r = profile.radius
    L, W = max(profile.sizeM[:2]), min(profile.sizeM[:2])
    H = profile.sizeM[2]
    notes = []
    top, sides = _targets(profile, notes)
    lights = []

    # Overhead plane (V-L02, P-L01): solved so the roof/top reflects it, else straight above.
    P = tuple(top["point"])
    R = mirror_dir(P, top["normal"], camera)
    height = profile.boundsMax[2] + params["overheadHeightR"] * r
    if R[2] > 0.2:
        c, facing = _place(P, R, (height - P[2]) / R[2], profile)
    else:
        c, facing = (profile.center[0], profile.center[1], height), (0.0, 0.0, -1.0)
    over = LightSpec("valora_overhead", "overhead", c, facing,
                     L * params["overheadScale"], W * params["overheadWidth"], 1.0)
    lights.append(over)

    # Side strips on the flanks the camera sees (V-L03, V-L08), most face-on first.
    seen = []
    for s in sides:
        v = _norm(_sub(camera, s["point"]))
        facing_cam = _dot(_norm(s["normal"]), v)
        if facing_cam > 0.05:
            seen.append((facing_cam, s))
    seen.sort(key=lambda t: -t[0])
    length = L * params["stripLength"]
    width = length / params["stripAspect"]
    for _, s in seen[:MAX_STRIPS]:
        p = tuple(s["point"])
        c, facing = _place(p, mirror_dir(p, s["normal"], camera), params["stripDistR"] * r, profile)
        lights.append(LightSpec(f"valora_strip_{s['kind']}", "strip", c, facing, length, width, 0.8))
        # Negative fill (V-L10): a black card where the lower flank's reflection lands.
        low = (p[0], p[1], profile.boundsMin[2] + 0.3 * H)
        c2, f2 = _place(low, mirror_dir(low, s["normal"], camera), params["stripDistR"] * r, profile)
        lights.append(LightSpec(f"valora_negfill_{s['kind']}", "negfill", c2, f2,
                                length, width * (1.0 + 4.0 * params["darkShare"]), 0.0))

    # Accents on detail glints (V-L05): small, close, placed by reflection.
    # Only a surface facing the camera can show a glint: filter before spending the count.
    pts = []
    for j, d in enumerate(profile.detailPoints):
        if d["kind"] not in ("glossy_peak", "high_curvature"):
            continue
        if not _has_normal(d):
            notes.append(f"detail point {j} has a zero-length normal; no accent placed")
        elif _dot(_norm(d["normal"]), _norm(_sub(camera, d["point"]))) > 0.05:
            pts.append(d)
    # (eng) V-L05: an accent is accentScale x the key's short side; accentScale spans 0.2-0.7.
    side = params["accentScale"] * min(over.sizeX, over.sizeY)
    for i, d in enumerate(pts[: int(params["accentCount"])]):
        p = tuple(d["point"])
        c, facing = _place(p, mirror_dir(p, d["normal"], camera), 0.6 * r, profile)
        lights.append(LightSpec(f"valora_accent_{i}", "accent", c, facing, side, side, 0.6))

    # Rim from behind and above (V-L11, P-L06).
    cx, cy, cz = profile.center
    az = math.atan2(camera[1] - cy, camera[0] - cx) + math.pi
    el = math.radians(params["rimElevationDeg"])
    c = (cx + 2 * r * math.cos(el) * math.cos(az), cy + 2 * r * math.cos(el) * math.sin(az), cz + 2 * r * math.sin(el))
    lights.append(LightSpec("valora_rim", "rim", c, _norm(_sub(profile.center, c)), 0.6 * r, 0.3 * r,
                            params["rimStrength"]))
    return RigLayout(tuple(lights), 1.0 / params["keyFill"], tuple(notes))
