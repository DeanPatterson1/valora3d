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
    wt = (lambda s: s.w) if a > 0 else (lambda s: 1.0)  # all zero-area (degenerate polys): unweighted
    wa = a if a > 0 else float(len(ss))
    c = [sum(s.p[i] * wt(s) for s in ss) / wa for i in range(3)]
    rep = min(ss, key=lambda s: sum((s.p[i] - c[i]) ** 2 for i in range(3)))
    n = _unit([sum(s.n[i] * wt(s) for s in ss) for i in range(3)])
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


_LONG_AXIS = lambda bmin, bmax: (0, 1) if bmax[0] - bmin[0] >= bmax[1] - bmin[1] else (1, 0)


def shoulder_line(samples, bmin, bmax, bins=12, min_bins=9, width_tol=0.15):
    """Per flank, the widest point in each slice along the long axis, between 0.3H and 0.9H.
    That is the shoulder line the side strips should run along (vehicles.md V-L03).
    Both flanks or neither: each needs >= min_bins filled slices, and the two flanks' mean
    |offset| must add up to the body width W within width_tol, or it is not a body side."""
    la, wa = _LONG_AXIS(bmin, bmax)
    H, lo_l, span = bmax[2] - bmin[2], bmin[la], bmax[la] - bmin[la]
    W = bmax[wa] - bmin[wa]
    body = [s for s in samples if 0.3 * H <= s.p[2] <= 0.9 * H]
    out = []
    for sign, name in ((1, "+"), (-1, "-")):
        pts = []
        for b in range(bins):
            a = lo_l + span * (0.05 + 0.9 * b / bins)
            e = lo_l + span * (0.05 + 0.9 * (b + 1) / bins)
            band = [s for s in body if a <= s.p[la] < e and s.p[wa] * sign > 0]
            if band:
                pts.append(_r(max(band, key=lambda s: s.p[wa] * sign).p))
        if len(pts) < min_bins:
            return []
        out.append({"side": f"{name}{'xy'[wa]}", "points": pts})
    width = sum(sum(abs(p[wa]) for p in l["points"]) / len(l["points"]) for l in out)
    if W <= 0 or abs(width - W) > width_tol * W:
        return []
    return out


def _cells(samples, cell):
    g = {}
    for s in samples:
        g.setdefault(tuple(math.floor(v / cell) for v in s.p), []).append(s)
    return [ss for ss in g.values() if len(ss) >= 3]


def _pct(vals, q):
    v = sorted(vals)
    return v[min(len(v) - 1, int(q * len(v)))]


# Base score per kind: lamps first (V-C12 detail inventory), then glossy glints, sharp small
# features, textures. (eng) ordering; the director may override with an explicit target.
_KIND_BASE = {"emissive": 3.0, "glossy_peak": 2.0, "high_curvature": 1.0, "textured": 0.5}


def detail_points(samples, longest, max_n=8, sep_frac=0.15):
    cell = 0.08 * longest
    groups = {
        "emissive": [s for s in samples if s.cls == "emissive"],
        "textured": [s for s in samples if s.textured],
    }
    gl = [s for s in samples if s.gloss and s.curv > 1e-4]
    if gl:
        cut = _pct([s.curv for s in gl], 0.90)
        groups["glossy_peak"] = [s for s in gl if s.curv >= cut]
    other = [s for s in samples if not s.gloss and s.cls != "emissive" and s.curv > 1e-4]
    if other:
        cut = _pct([s.curv for s in other], 0.95)
        groups["high_curvature"] = [s for s in other if s.curv >= cut]
    cands = []
    for kind, ss in groups.items():
        total = sum(s.w for s in ss) or 1.0
        for cl in _cells(ss, cell):
            a, p, n = _representative(cl)
            cands.append({"kind": kind, "point": _r(p), "normal": _r(n),
                          "score": round(_KIND_BASE[kind] + a / total, 4)})
    kept = []
    for c in sorted(cands, key=lambda c: -c["score"]):
        if all(math.dist(c["point"], k["point"]) >= sep_frac * longest for k in kept):
            kept.append(c)
        if len(kept) == max_n:
            break
    return kept


def _components(points, cell):
    """Connected components of 2D points on a grid (8-neighbourhood)."""
    grid = {}
    for p in points:
        grid.setdefault((math.floor(p[0] / cell), math.floor(p[1] / cell)), []).append(p)
    seen, comps = set(), []
    for start in grid:
        if start in seen:
            continue
        stack, comp = [start], []
        seen.add(start)
        while stack:
            c = stack.pop()
            comp += grid[c]
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nb = (c[0] + dx, c[1] + dy)
                    if nb in grid and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        comps.append(comp)
    return comps


def _axle_pattern(ws, la, wa, L, W):
    """True if the wheels form axles: mirrored pairs at one long-axis position with a real
    track, radii agreeing, >= 2 axle positions spanning a real wheelbase. Only a 3-wheeler
    may leave one wheel unpaired, and only on the centreline."""
    free, axles, lone = list(range(len(ws))), [], 0
    while free:
        i = free.pop(0)
        a = ws[i]
        mate = next((j for j in free
                     if abs(ws[j]["center"][la] - a["center"][la]) <= 0.06 * L
                     and abs(ws[j]["center"][wa] + a["center"][wa]) <= 0.06 * W
                     and abs(ws[j]["center"][wa] - a["center"][wa]) >= 0.4 * W
                     and abs(ws[j]["radius"] - a["radius"]) <= 0.1 * max(ws[j]["radius"], a["radius"])),
                    None)
        if mate is not None:
            free.remove(mate)
            axles.append((a["center"][la] + ws[mate]["center"][la]) / 2)
        elif len(ws) == 3 and lone == 0 and abs(a["center"][wa]) <= 0.06 * W:
            lone += 1
            axles.append(a["center"][la])
        else:
            return False
    return len(axles) >= 2 and max(axles) - min(axles) >= 0.3 * L


def wheels(samples, bmin, bmax):
    """Best-effort wheels: ground-contact patches give each (l, w) centre; nearby samples vote a
    radius r = z / (1 + n_z) whose circle centre lands on the patch. The median vote wins.
    Round ground-touching patches are common off vehicles (chair casters, a star base, feet),
    so the set must also look like a wheeled chassis (_axle_pattern) or nothing is reported.
    Any wheel with a wide vote spread makes every wheel 'low' so a vehicle block can refuse it."""
    la, wa = _LONG_AXIS(bmin, bmax)
    H, Wd, L = bmax[2] - bmin[2], bmax[wa] - bmin[wa], bmax[la] - bmin[la]
    contacts = [(s.p[la], s.p[wa]) for s in samples if s.p[2] <= 0.02 * H]
    patches = [c for c in _components(contacts, 0.1 * Wd) if len(c) >= 3]
    if not 3 <= len(patches) <= 8:
        return []
    out = []
    for comp in patches:
        lc = sum(p[0] for p in comp) / len(comp)
        wc = sum(p[1] for p in comp) / len(comp)
        votes = []
        for s in samples:
            if not (0.02 * H < s.p[2] <= 0.6 * H and abs(s.p[wa] - wc) <= 0.15 * Wd
                    and abs(s.n[wa]) < 0.3 and s.n[2] > -0.95):
                continue
            r = s.p[2] / (1.0 + s.n[2])
            if 0 < r < 0.6 * H and abs(s.p[la] - r * s.n[la] - lc) < 0.1 * r:
                votes.append(r)
        if len(votes) < 5:
            continue
        votes.sort()
        r = votes[len(votes) // 2]
        iqr = votes[3 * len(votes) // 4] - votes[len(votes) // 4]
        center, axis = [0.0, 0.0, r], [0.0, 0.0, 0.0]
        center[la], center[wa], axis[wa] = lc, wc, 1.0
        out.append({"center": _r(center), "radius": round(r, 5), "axis": axis,
                    "confidence": "high" if iqr <= 0.15 * r else "low"})
    if len(out) < 3:
        return []
    radii = sorted(w["radius"] for w in out)
    med = radii[len(radii) // 2]
    if not 0.03 * L <= med <= 0.25 * L or any(abs(r - med) > 0.25 * med for r in radii):
        return []
    if not _axle_pattern(out, la, wa, L, Wd):
        return []
    if any(w["confidence"] != "high" for w in out):
        for w in out:
            w["confidence"] = "low"
    return out


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
        shoulderLine=shoulder_line(samples, bmin, bmax),
        detailPoints=detail_points(samples, max(size)),
        wheels=wheels(samples, bmin, bmax),
    )


def _parts(parts, place, max_n=64):
    total = sum(p.get("polys", 0) for p in parts) or 1
    rows = sorted(parts, key=lambda p: -p.get("polys", 0))[:max_n]
    return [{"index": i, "boundsMin": [round(v, 6) for v in place(p["boundsMin"])],
             "boundsMax": [round(v, 6) for v in place(p["boundsMax"])],
             "polyShare": round(p.get("polys", 0) / total, 4)} for i, p in enumerate(rows)]
