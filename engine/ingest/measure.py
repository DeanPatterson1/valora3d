"""Pure half of ingest: raw Blender facts -> SubjectProfile. Trusts no names (spec §4.1)."""
import math
from collections import namedtuple

from engine.profile import SubjectProfile

Sample = namedtuple("Sample", "p n w cls gloss textured curv")  # placed coords, unit normal, area m^2

GLOSS_METALLIC, GLOSS_ROUGHNESS = 0.5, 0.3  # TIERS §2 "gloss" mask definition
_DIRS = {"top": (0, 0, 1), "+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0),
         "top+x": (0.7071, 0, 0.7071), "top-x": (-0.7071, 0, 0.7071),
         "top+y": (0, 0.7071, 0.7071), "top-y": (0, -0.7071, 0.7071)}

PLAUSIBLE_M = (0.02, 30.0)
CM_PLAUSIBLE_M = (2.0, 10.0)   # a raw size that x100 lands here may be a cm-authored object
CONFIDENT_MAX_M = 10.0         # plausible in metres above this, but unusual enough to flag
_LARGE_FACTORS = (("mm", 0.001), ("cm", 0.01))
_SIZE_CLASSES = ((0.1, "macro"), (0.5, "hand"), (2.5, "furniture"), (8.0, "vehicle"))


def infer_units(longest_raw):
    lo, hi = PLAUSIBLE_M
    if lo <= longest_raw <= hi:
        as_cm = CM_PLAUSIBLE_M[0] <= longest_raw * 100 <= CM_PLAUSIBLE_M[1]
        return "m", 1.0, "low" if as_cm or longest_raw > CONFIDENT_MAX_M else "high"
    if longest_raw > hi:
        for name, f in _LARGE_FACTORS:
            if lo <= longest_raw * f <= hi:
                return name, f, "low"
    return "unknown", 1.0, "low"


def size_class(longest_m):
    for limit, name in _SIZE_CLASSES:
        if longest_m < limit:
            return name
    return "architectural"


def category_hint(size):
    x, y, z = size
    longest, width = max(x, y), min(x, y)
    if 2.5 <= longest <= 7.0 and z < 0.6 * longest and longest >= 2 * width:
        return "vehicle-like"
    return "small-object" if max(size) < 0.5 else "large-object"


def material_class(m):
    g = lambda k, d=0.0: m.get(k, d)
    if g("emission") > 0.5:
        return "emissive"
    if g("transmission") > 0.5:
        return "glass"
    if g("subsurface") > 0.2:
        return "skin"
    if g("metallic") > 0.5:
        return "metal"
    if g("roughness", 0.5) < 0.25:
        return "glossy"
    if g("roughness", 0.5) > 0.7:
        return "fabric"
    return "matte"


def _material_shares(mats):
    total = sum(m.get("area", 0.0) for m in mats)
    if total <= 0:
        return []
    shares = {}
    for m in mats:
        c = material_class(m)
        shares[c] = shares.get(c, 0.0) + m.get("area", 0.0) / total
    return [{"class": c, "share": round(v, 4)} for c, v in sorted(shares.items(), key=lambda kv: -kv[1])]


def is_gloss(m):
    return m.get("metallic", 0.0) >= GLOSS_METALLIC or m.get("roughness", 0.5) <= GLOSS_ROUGHNESS


def gloss_share(mats):
    total = sum(m.get("area", 0.0) for m in mats)
    if total <= 0:
        return 0.0
    return round(sum(m.get("area", 0.0) for m in mats if is_gloss(m)) / total, 4)


def _r(v, nd=5):
    return [round(float(x), nd) for x in v]


def _unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n > 0 else [0.0, 0.0, 1.0]


def _representative(ss):
    """(area, surface point nearest the area-weighted centroid, mean unit normal)."""
    a = sum(s.w for s in ss)
    c = [sum(s.p[i] * s.w for s in ss) / a for i in range(3)]
    rep = min(ss, key=lambda s: sum((s.p[i] - c[i]) ** 2 for i in range(3)))
    n = _unit([sum(s.n[i] * s.w for s in ss) for i in range(3)])
    return a, rep.p, n


def reflection_targets(samples, max_n=6, min_share=0.05):
    """Largest glossy patches grouped by facing: where the reflection solver aims the key planes
    (vehicles.md V-L02/L03, products.md P-L01). Down-facing surfaces are never lit this way."""
    gl = [s for s in samples if s.gloss and s.n[2] > -0.5]
    total = sum(s.w for s in gl)
    if total <= 0:
        return []
    bins = {}
    for s in gl:
        k = max(_DIRS, key=lambda d: sum(a * b for a, b in zip(_DIRS[d], s.n)))
        bins.setdefault(k, []).append(s)
    out = []
    for k, ss in bins.items():
        a, p, n = _representative(ss)
        if a >= min_share * total:
            out.append({"kind": k, "point": _r(p), "normal": _r(n), "area": round(a, 6)})
    return sorted(out, key=lambda t: -t["area"])[:max_n]


def shoulder_line(samples, bmin, bmax):
    return []  # Task 8


def detail_points(samples, longest):
    return []  # Task 8


def wheels(samples, bmin, bmax):
    return []  # Task 9


def _samples(raw, place, f):
    mats = raw.get("materials", [])
    out = []
    for x, y, z, nx, ny, nz, w, mi, curv in raw.get("samples", []):
        m = mats[int(mi)] if 0 <= int(mi) < len(mats) else {}
        out.append(Sample(tuple(place([x, y, z])), tuple(_unit([nx, ny, nz])), w * f * f,
                          material_class(m), is_gloss(m), bool(m.get("textured")), curv))
    return out


def build_profile(raw):
    lo, hi = raw["boundsMin"], raw["boundsMax"]
    size_raw = [b - a for a, b in zip(lo, hi)]
    unit, f, conf = infer_units(max(size_raw))
    size = [v * f for v in size_raw]
    center = [(a + b) / 2 for a, b in zip(lo, hi)]

    def place(v):  # the SubjectProfile placement formula
        return [(v[0] - center[0]) * f, (v[1] - center[1]) * f, (v[2] - lo[2]) * f]

    bmin, bmax = place(lo), place(hi)
    samples = _samples(raw, place, f)
    return SubjectProfile(
        sizeM=size, boundsMin=bmin, boundsMax=bmax, unitGuess=unit, scaleConfidence=conf,
        upAxis="Z", sizeClass=size_class(max(size)), categoryHint=category_hint(size),
        materials=_material_shares(raw.get("materials", [])), polyCount=raw.get("polyCount", 0),
        rigged=raw.get("rigged", False), animated=raw.get("animated", False),
        sourceCenter=center, sourceMinZ=lo[2], scaleFactor=f,
        boundsPosed=bool(raw.get("boundsPosed", False)),
        parts=_parts(raw.get("parts", []), place),
        glossShare=gloss_share(raw.get("materials", [])),
        reflectionTargets=reflection_targets(samples),
    )


def _parts(parts, place, max_n=64):
    total = sum(p.get("polys", 0) for p in parts) or 1
    rows = sorted(parts, key=lambda p: -p.get("polys", 0))[:max_n]
    return [{"index": i, "boundsMin": [round(v, 6) for v in place(p["boundsMin"])],
             "boundsMax": [round(v, 6) for v in place(p["boundsMax"])],
             "polyShare": round(p.get("polys", 0) / total, 4)} for i, p in enumerate(rows)]
