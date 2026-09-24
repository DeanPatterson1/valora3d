"""Pure half of ingest: raw Blender facts -> SubjectProfile. Trusts no names (spec §4.1)."""
from engine.profile import SubjectProfile

PLAUSIBLE_M = (0.02, 30.0)
_LARGE_FACTORS = (("mm", 0.001), ("cm", 0.01))
_SIZE_CLASSES = ((0.1, "macro"), (0.5, "hand"), (2.5, "furniture"), (8.0, "vehicle"))


def infer_units(longest_raw):
    lo, hi = PLAUSIBLE_M
    if lo <= longest_raw <= hi:
        return "m", 1.0, "high"
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


def build_profile(raw):
    lo, hi = raw["boundsMin"], raw["boundsMax"]
    size_raw = [b - a for a, b in zip(lo, hi)]
    unit, f, conf = infer_units(max(size_raw))
    size = [v * f for v in size_raw]
    center = [(a + b) / 2 for a, b in zip(lo, hi)]

    def place(v):  # the SubjectProfile placement formula
        return [(v[0] - center[0]) * f, (v[1] - center[1]) * f, (v[2] - lo[2]) * f]

    bmin, bmax = place(lo), place(hi)
    return SubjectProfile(
        sizeM=size, boundsMin=bmin, boundsMax=bmax, unitGuess=unit, scaleConfidence=conf,
        upAxis="Z", sizeClass=size_class(max(size)), categoryHint=category_hint(size),
        materials=_material_shares(raw.get("materials", [])), polyCount=raw.get("polyCount", 0),
        rigged=raw.get("rigged", False), animated=raw.get("animated", False),
        sourceCenter=center, sourceMinZ=lo[2], scaleFactor=f,
    )
