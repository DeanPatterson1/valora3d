"""Pure sim facts (phase 6 Task 95): where a pour goes in, where the liquid stops, where smoke and sparks come
from, which way a car faces, where scattered pieces pile up.

No SubjectProfile field is added: profile_key hashes profile.to_dict(), and variety memory and the floor cache
key on it, so every fact here is computed from the profile's existing measurements plus the job's markers.
Markers win over measurements (PHASING §2: "markers first"); a measured fact carries confidence "low" or
"medium", and a sim that needs one at high confidence asks for a marker (sim_needs_profile). Markers are the
checked script's markers: anchor points are placed metres (engine/markers.check_anchors converts gltf ones).
"""
import math
import re

from engine.physics import shape

OPENING_TEXT = re.compile(r"\b(opening|rim|top|mouth|lip|neck)\b", re.I)
FILL_TEXT = re.compile(r"\b(fill|level|line)\b", re.I)
EMITTER_TEXT = re.compile(r"\b(emit\w*|exhaust|smoke|steam|spark\w*|source|vent|nozzle|spout|chimney|flame)\b", re.I)
FRONT_TEXT = re.compile(r"\b(front|nose|bonnet|hood|headlights?|grille)\b", re.I)
EMITTER_KINDS = ("emissive", "exhaust")

TOP_BAND = 0.04          # (eng) share of height counted as the top ring
BODY_BAND = (0.3, 0.7)   # (eng) share of height whose radius is the body radius
OPEN_RATIO = 0.6         # the top ring's radius >= 0.6 x the body radius reads as an opening (PHASING §2)
ROUND_ASPECT = 1.5       # (eng) the top ring's XY extents within 1.5:1, i.e. an upright round top
RING_PCT = 0.95          # the ring radius is the 95th-percentile radial distance (robust to a stray sample)
FULL_FILL = 0.85         # the default fill line: "full" at 0.85 x height (eng)
PILE_INNER, PILE_OUTER = 1.05, 1.6   # the pile annulus, x the footprint radius (eng)
MIN_RING = 8
INNER_DEPTH, INNER_BAND, INNER_PCT = 0.15, 0.1, 0.1   # (eng) the inner-wall band below a marked rim (lane P T105)


def _text_hits(markers, pattern):
    return [m for m in (markers or []) if isinstance(m, dict) and pattern.search(str(m.get("text", "")))]


def _point(m):
    return [float(v) for v in m["anchor"]["point"]]


def _pct(vals, q):
    vals = sorted(vals)
    return vals[min(len(vals) - 1, int(q * (len(vals) - 1) + 0.5))] if vals else 0.0


def _radial(pts, c):
    return [math.hypot(p[0] - c[0], p[1] - c[1]) for p in pts]


def _body_radius(pts, c, lo_z, h):
    body = [p for p in pts if lo_z + BODY_BAND[0] * h <= p[2] <= lo_z + BODY_BAND[1] * h]
    return _pct(_radial(body, c), RING_PCT) if body else 0.0


def _ring_axis(band):
    xs, ys = [q[0] for q in band], [q[1] for q in band]
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)


def _inner_radius(pts, ax, rim_z, h, r_rim):
    """The container's inner wall below the rim, about its axis: the INNER_PCT percentile of the samples' axis
    distance in a band INNER_DEPTH x height below the rim (+- INNER_BAND x height), clear of the rim's lip and
    top annulus. A thick glass wall's outer samples sit above it; never more than the rim radius."""
    zc = rim_z - INNER_DEPTH * h
    band = [q for q in pts if abs(q[2] - zc) <= INNER_BAND * h]
    return min(_pct(_radial(band, ax), INNER_PCT), r_rim) if band else r_rim


def container(profile, markers):
    """{"opening": [x, y, z], "radiusM", "confidence"} or None. A marker naming an opening/rim/top/mouth is
    high confidence: the opening is the ring's axis at the marker's height, its radius measured about that axis
    from the samples at that height, "innerRadiusM" its inner wall just below the rim (what a drink or a pour
    fills; the same as radiusM on a single-sided glass), and the marker point kept as "marker"; else an upright
    round top ring
    whose radius is >= OPEN_RATIO x the body radius is a low-confidence guess (a bottle or a can standing
    up); anything else (a can on its side, a shoe) has no container."""
    pts = [tuple(p) for p in (getattr(profile, "surfaceSamples", None) or [])]
    c, lo_z = profile.center, profile.boundsMin[2]
    h = profile.boundsMax[2] - lo_z
    hits = _text_hits(markers, OPENING_TEXT)
    if hits:
        p = _point(hits[0])
        band = [q for q in pts if abs(q[2] - p[2]) <= TOP_BAND * h]
        # The ring is measured about ITS axis (the band's XY extents' centre), never about the marker: a marker
        # usually sits ON the rim, and measuring about it gave up to the full diameter (lane P, T95 bug).
        ax = _ring_axis(band) if band else (c[0], c[1])
        r = _pct(_radial(band, ax), RING_PCT) if band else 0.0
        return {"opening": [round(ax[0], 6), round(ax[1], 6), p[2]], "radiusM": round(r, 6),
                "innerRadiusM": round(_inner_radius(pts, ax, p[2], h, r), 6), "confidence": "high", "marker": p}
    if len(pts) < 16 or h <= 0:
        return None
    ups = {tuple(s["p"]) for s in shape.up_facing(shape.samples(profile))}
    top = [q for q in pts if q[2] >= profile.boundsMax[2] - TOP_BAND * h and q in ups]
    if len(top) < MIN_RING:
        return None
    xs, ys = [q[0] for q in top], [q[1] for q in top]
    ex, ey = max(xs) - min(xs), max(ys) - min(ys)
    if min(ex, ey) <= 0 or max(ex, ey) / min(ex, ey) > ROUND_ASPECT:
        return None
    r_top, r_body = _pct(_radial(top, c), RING_PCT), _body_radius(pts, c, lo_z, h)
    if r_body <= 0 or r_top < OPEN_RATIO * r_body:
        return None
    return {"opening": [round(c[0], 6), round(c[1], 6), round(profile.boundsMax[2], 6)],
            "radiusM": round(r_top, 6), "confidence": "low"}


def fill_line(profile, markers):
    """{"z", "confidence", "source", "level"}: a fill/level/line marker's height, else "full" at 0.85 x height."""
    hits = _text_hits(markers, FILL_TEXT)
    if hits:
        return {"z": _point(hits[0])[2], "confidence": "high", "source": "marker", "level": "marker"}
    lo_z = profile.boundsMin[2]
    return {"z": lo_z + FULL_FILL * (profile.boundsMax[2] - lo_z), "confidence": "low", "source": "default",
            "level": "full"}


def emitters(profile, markers):
    """[{"point", "normal", "source", "confidence"}]: emitter markers (high) first, then emissive / exhaust
    detail points (medium), in the profile's ranked order."""
    out = []
    for m in _text_hits(markers, EMITTER_TEXT):
        p = _point(m)
        n = m["anchor"].get("normal") or [a - b for a, b in zip(p, profile.center)]
        out.append({"point": p, "normal": list(n), "source": f"marker:{m.get('id')}", "confidence": "high"})
    for i, d in enumerate(getattr(profile, "detailPoints", None) or []):
        if d.get("kind") in EMITTER_KINDS:
            out.append({"point": list(d["point"]), "normal": list(d.get("normal") or [0.0, 0.0, 1.0]),
                        "source": f"detail:{i}", "confidence": "medium"})
    return out


def nose_sign(profile, markers):
    """(+1 | -1, confidence) along vehicle.forwardAxis (else the longest horizontal axis). A marker labelled
    front/nose decides it at high confidence (the phase-5 register's noseSign ingest fact); otherwise
    engine/physics/shape.nose_sign's measured guess."""
    hits = _text_hits(markers, FRONT_TEXT)
    if not hits:
        return shape.nose_sign(profile)
    ax = (getattr(profile, "vehicle", None) or {}).get("forwardAxis")
    if ax is None:
        i, sign = (0 if profile.sizeM[0] >= profile.sizeM[1] else 1), 1
    else:
        i, sign = shape._axis_index(ax)
    off = (_point(hits[0])[i] - profile.center[i]) * sign
    return (sign if off >= 0 else -sign), "high"


def pile_zone(profile):
    """The ground annulus between 1.05 x and 1.6 x the footprint radius (the footprint box's half-diagonal),
    where rigid_scatter zone=around lands its pieces."""
    r = math.hypot(profile.half[0], profile.half[1])
    c = profile.center
    return {"center": [c[0], c[1], 0.0], "innerM": PILE_INNER * r, "outerM": PILE_OUTER * r}
