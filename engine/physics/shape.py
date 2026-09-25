"""Shape facts from SubjectProfile.surfaceSamples (METHODS §3), pure and stdlib-only, so no re-ingest.

At HEAD a sample is a bare [x, y, z] point, so estimate_normals() adds a normal per point (PCA of its k
nearest neighbours, oriented away from the centroid) and samples(profile) returns [{"p", "n"}], cached by
the sample CONTENT (never id(profile), which is reused after garbage collection).
principal_axes: PCA of the sample points (long -> short). roll_axis: the flat-lying principal axis whose
samples sit at a near-constant distance from it (cylinder fit) with its radius and a confidence.
support_polygon: convex hull (XY) of samples within SUPPORT_Z of the ground. up_facing / low_edges:
normal filters. nose_sign: which way along vehicle.forwardAxis the nose points (always low confidence in
phase 5: parts carry no material class, so there is no windscreen to find; an ingest `noseSign` fact is a
phase-6 item)."""
import math

ROUND_CV = 0.08        # (eng) coefficient of variation of the radial distance for a 'round' section
SUPPORT_Z = 0.01       # (eng) share of height counted as touching the ground
UP_DOT, DOWN_DOT = 0.7, -0.3   # METHODS PT-04 (n.up > 0.7), FL-20 (n.up < -0.3)
NORMAL_K = 12          # neighbours per normal estimate
NORMAL_TOL = 0.1       # (eng) plane-vote inlier distance, share of the median neighbour distance
NOSE_OFFSET = 0.03     # (eng) glass offset share of length for a confident nose sign
_CACHE_MAX = 64


def _pts(samples):
    return [tuple(s["p"]) for s in samples]


def _jacobi(a, sweeps=50):
    a = [row[:] for row in a]
    v = [[1.0 if i == j else 0.0 for j in range(3)] for i in range(3)]
    for _ in range(sweeps):
        off = max(abs(a[0][1]), abs(a[0][2]), abs(a[1][2]))
        if off < 1e-15:
            break
        for p, q in ((0, 1), (0, 2), (1, 2)):
            if abs(a[p][q]) < 1e-18:
                continue
            th = 0.5 * math.atan2(2 * a[p][q], a[q][q] - a[p][p])
            c, s = math.cos(th), math.sin(th)
            for k in range(3):
                akp, akq = a[k][p], a[k][q]
                a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
            for k in range(3):
                apk, aqk = a[p][k], a[q][k]
                a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
            for k in range(3):
                vkp, vkq = v[k][p], v[k][q]
                v[k][p], v[k][q] = c * vkp - s * vkq, s * vkp + c * vkq
    vals = [a[i][i] for i in range(3)]
    vecs = [[v[k][i] for k in range(3)] for i in range(3)]
    order = sorted(range(3), key=lambda i: -vals[i])
    return [vals[i] for i in order], [vecs[i] for i in order]


def _centroid(pts):
    n = len(pts)
    return tuple(sum(p[i] for p in pts) / n for i in range(3))


def _cov(pts, c):
    n = len(pts)
    return [[sum((p[i] - c[i]) * (p[j] - c[j]) for p in pts) / n for j in range(3)] for i in range(3)]


def principal_axes(samples):
    pts = _pts(samples)
    if len(pts) < 4:
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    return _jacobi(_cov(pts, _centroid(pts)))[1]


def _neighbours(pts, k):
    """k nearest neighbours (self included) per point via a uniform grid; brute force distance inside
    the searched rings. The ring grows until it holds k points and covers the k-th distance."""
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    ext = max(hi[i] - lo[i] for i in range(3)) or 1.0
    cell = ext / max(1.0, len(pts) ** 0.5)
    grid = {}
    key = lambda p: tuple(int((p[i] - lo[i]) // cell) for i in range(3))  # noqa: E731
    for j, p in enumerate(pts):
        grid.setdefault(key(p), []).append(j)
    out = []
    for p in pts:
        cx, cy, cz = key(p)
        ring = 1
        while True:
            cand = [j for dx in range(-ring, ring + 1) for dy in range(-ring, ring + 1)
                    for dz in range(-ring, ring + 1) for j in grid.get((cx + dx, cy + dy, cz + dz), ())]
            if len(cand) >= min(k, len(pts)):
                d = sorted((sum((pts[j][i] - p[i]) ** 2 for i in range(3)), j) for j in cand)[:k]
                if len(cand) == len(pts) or math.sqrt(d[-1][0]) <= ring * cell:
                    out.append([j for _, j in d])
                    break
            ring += 1
    return out


def estimate_normals(points, k=NORMAL_K):
    """Per point: the smallest-eigenvalue vector of its k-neighbourhood covariance, oriented away from
    the cloud centroid. Bare points in, unit normals out (same order). Near an edge the neighbourhood
    straddles two faces and plain PCA returns the diagonal, so each point then adopts, from its own and
    its neighbours' PCA normals, the one whose plane through the point holds the most neighbours within
    NORMAL_TOL x the median neighbour distance (a deterministic normal vote)."""
    pts = [tuple(float(x) for x in p) for p in points]
    if len(pts) < 4:
        return [[0.0, 0.0, 1.0] for _ in pts]
    c = _centroid(pts)
    nbs = _neighbours(pts, k)
    raw = []
    for nb in nbs:
        q = [pts[j] for j in nb]
        raw.append(_jacobi(_cov(q, _centroid(q)))[1][2])
    out = []
    for i, (p, nb) in enumerate(zip(pts, nbs)):
        others = [j for j in nb if j != i]
        ds = sorted(math.dist(p, pts[j]) for j in others) or [0.0]
        tol = NORMAL_TOL * ds[len(ds) // 2]
        best = None
        for j in [i] + others:
            n = raw[j]
            support = sum(1 for m in nb if abs(sum((pts[m][a] - p[a]) * n[a] for a in range(3))) < tol)
            if best is None or support > best[0]:
                best = (support, n)
        n = best[1]
        if sum((p[a] - c[a]) * n[a] for a in range(3)) < 0:
            n = [-x for x in n]
        norm = math.sqrt(sum(x * x for x in n)) or 1.0
        out.append([x / norm for x in n])
    return out


_SAMPLES = {}


def _content_key(points):
    return (len(points), hash(tuple(tuple(float(x) for x in p) for p in points)))


def samples(profile):
    """[{"p", "n"}] for the profile's surface samples; normals estimated once per sample content."""
    pts = list(getattr(profile, "surfaceSamples", None) or [])
    key = _content_key(pts)
    hit = _SAMPLES.get(key)
    if hit is None:
        if len(_SAMPLES) >= _CACHE_MAX:
            _SAMPLES.clear()
        hit = _SAMPLES[key] = [{"p": list(p), "n": n} for p, n in zip(pts, estimate_normals(pts))]
    return hit


def _radial(pts, c, axis):
    out = []
    for p in pts:
        d = [p[i] - c[i] for i in range(3)]
        t = sum(d[i] * axis[i] for i in range(3))
        out.append(math.sqrt(max(0.0, sum(x * x for x in d) - t * t)))
    return out


def roll_axis(samples):
    """{'axis', 'radius', 'confidence'}: a horizontal principal axis with a round cross-section."""
    pts = _pts(samples)
    if len(pts) < 16:
        return {"axis": [1.0, 0.0, 0.0], "radius": 0.0, "confidence": "low"}
    c = _centroid(pts)
    best = None
    for ax in principal_axes(samples):
        if abs(ax[2]) > 0.3:             # must lie roughly flat to roll on the ground
            continue
        r = _radial(pts, c, ax)
        mean = sum(r) / len(r)
        cv = math.sqrt(sum((x - mean) ** 2 for x in r) / len(r)) / mean if mean else 1.0
        if best is None or cv < best[0]:
            best = (cv, ax, mean)
    if best is None:
        return {"axis": [1.0, 0.0, 0.0], "radius": 0.0, "confidence": "low"}
    cv, ax, mean = best
    return {"axis": [round(x, 6) for x in ax], "radius": round(mean, 6),
            "confidence": "high" if cv <= ROUND_CV else "low"}


def _hull(points):
    pts = sorted(set(points))
    if len(pts) < 3:
        return [list(p) for p in pts]
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])  # noqa: E731
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return [list(p) for p in lo[:-1] + hi[:-1]]


def support_polygon(samples):
    pts = _pts(samples)
    if not pts:
        return []
    h = max(p[2] for p in pts) or 1.0
    return _hull([(round(p[0], 5), round(p[1], 5)) for p in pts if p[2] <= SUPPORT_Z * h + 1e-9])


def up_facing(samples):
    return [s for s in samples if s["n"][2] > UP_DOT]


def low_edges(samples):
    return [s for s in samples if s["n"][2] < DOWN_DOT and s["p"][2] > 0.0]


def _axis_index(ax):
    """vehicle.forwardAxis is a vector at HEAD ([0, 1, 0]); older text forms ('+y') still parse."""
    if isinstance(ax, (list, tuple)) and len(ax) >= 2:
        i = max(range(len(ax)), key=lambda j: abs(ax[j]))
        return i, (1 if ax[i] >= 0 else -1)
    s = str(ax).strip().lower()
    return {"x": 0, "y": 1, "z": 2}.get(s.lstrip("+-"), 0), (-1 if s.startswith("-") else 1)


def nose_sign(profile):
    """(+1 | -1, confidence) along vehicle.forwardAxis: glass (windscreen) sits forward of the body centre
    on most cars. Parts carry no material class at HEAD, so this is (sign of the forward axis, "low") for
    every profile in phase 5 (hand-off H5 falls back to a side pass-by on low confidence)."""
    veh = getattr(profile, "vehicle", None) or {}
    ax = veh.get("forwardAxis")
    if ax is None:
        return 1, "low"
    i, sign = _axis_index(ax)
    glass = [p for p in (profile.parts or []) if p.get("class") == "glass"]
    if not glass:
        return sign, "low"
    mid = sum((p["boundsMin"][i] + p["boundsMax"][i]) / 2 for p in glass) / len(glass)
    off = (mid - profile.center[i]) * sign
    return (sign if off >= 0 else -sign), ("high" if abs(off) >= NOSE_OFFSET * profile.longest else "low")


_FACTS = {}


def shape_facts(profile):
    """{fact: (high, low)} for the computed shape facts (catalog.PROFILE_FACTS / REQUIRES_PROFILE)."""
    key = _content_key(list(getattr(profile, "surfaceSamples", None) or []))
    hit = _FACTS.get(key)
    if hit is None:
        ss = samples(profile)
        if len(_FACTS) >= _CACHE_MAX:
            _FACTS.clear()
        hit = _FACTS[key] = {
            "rollAxis": (roll_axis(ss)["confidence"] == "high", False),
            "supportPolygon": (len(support_polygon(ss)) >= 3, False),
            "upFacing": (len(up_facing(ss)) >= 8, False),
        }
    return hit


SHAPE_FACTS = ("rollAxis", "supportPolygon", "upFacing")
