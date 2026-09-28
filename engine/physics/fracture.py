"""shatter's pure fracture (phase 6 Task 102; METHODS M-FRAC, DS-01): seeded Voronoi sites, dense near the impact
point, and each site's convex cell of a box by half-space intersection (the box clipped by the bisector plane of
every nearer site). The Cell Fracture extension is not bundled with Blender 5.0.1, so the cells are computed here
and bake.py builds each shard from its vertices and faces.

Box coordinates: the prop pane is centred on the origin, width on X, thickness on Y, height on Z; sites lie on the
pane's mid-plane (y = 0), so every cell spans the full thickness (a real pane breaks through). A cell is
{"site", "verts": [[x, y, z]], "faces": [[vertex index, ...] counter-clockwise seen from outside]}."""
import math
import random

NEAR_SHARE = 0.75          # (eng) share of sites drawn with the radial falloff around the impact
FALLOFF = 1.8              # (eng) r = R x u^FALLOFF: > 1 packs sites (small shards) near the impact
MIN_GAP = 0.25             # (eng) x sqrt(area / n): no two sites closer (no sliver cells)
EPS = 1e-12


def sites(box, n, impact, seed):
    """n seeded sites [(x, 0, z)] inside the pane; `impact` is (x, z) on the pane."""
    w, _, h = box
    rng = random.Random(seed)
    gap = MIN_GAP * math.sqrt(w * h / n)
    big = math.hypot(w, h) / 2
    out = []
    while len(out) < n:
        if rng.random() < NEAR_SHARE:
            r, a = big * rng.random() ** FALLOFF, rng.uniform(0, 2 * math.pi)
            x, z = impact[0] + r * math.cos(a), impact[1] + r * math.sin(a)
        else:
            x, z = rng.uniform(-w / 2, w / 2), rng.uniform(-h / 2, h / 2)
        if abs(x) >= w / 2 * 0.999 or abs(z) >= h / 2 * 0.999:
            continue
        if any(math.hypot(x - p[0], z - p[2]) < gap for p in out):
            continue
        out.append((x, 0.0, z))
    return out


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def face_normal(pts):
    """Newell's normal of a planar polygon, unit length."""
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    k = math.sqrt(_dot(n, n)) or 1.0
    return (n[0] / k, n[1] / k, n[2] / k)


def _box_faces(box):
    hx, hy, hz = (v / 2 for v in box)
    c = [(sx * hx, sy * hy, sz * hz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return [[c[i] for i in q] for q in quads]


def _clip(faces, n, d):
    """Keep n.p <= d; returns the clipped faces plus the cap polygon on the plane."""
    out, cut = [], []
    for poly in faces:
        res = []
        for i, a in enumerate(poly):
            b = poly[(i + 1) % len(poly)]
            da, db = _dot(n, a) - d, _dot(n, b) - d
            if da <= EPS:
                res.append(a)
            if (da < -EPS and db > EPS) or (da > EPS and db < -EPS):
                t = da / (da - db)
                p = tuple(a[k] + t * (b[k] - a[k]) for k in range(3))
                res.append(p)
                cut.append(p)
            elif abs(da) <= EPS:
                cut.append(a)
        if len(res) >= 3:
            out.append(res)
    if len(cut) >= 3:
        uniq = []
        for p in cut:
            if all(math.dist(p, q) > 1e-10 for q in uniq):
                uniq.append(p)
        if len(uniq) >= 3:
            c = tuple(sum(p[k] for p in uniq) / len(uniq) for k in range(3))
            u = _sub(uniq[0], c)
            u = tuple(v / math.sqrt(_dot(u, u)) for v in u)
            v = _cross(n, u)
            uniq.sort(key=lambda p: math.atan2(_dot(_sub(p, c), v), _dot(_sub(p, c), u)))
            out.append(uniq)
    return out


def _index(faces):
    verts, idx = [], []
    for poly in faces:
        f = []
        for p in poly:
            j = next((k for k, q in enumerate(verts) if math.dist(p, q) < 1e-10), None)
            if j is None:
                j = len(verts)
                verts.append(list(p))
            if not f or f[-1] != j:
                f.append(j)
        if len(f) >= 3 and f[0] == f[-1]:
            f.pop()
        if len(set(f)) >= 3:
            idx.append(f)
    return verts, idx


def cells(box, pts):
    """The Voronoi cell of every site inside the box, in site order."""
    out = []
    for i, s in enumerate(pts):
        faces = _box_faces(box)
        others = sorted((math.dist(s, q), j) for j, q in enumerate(pts) if j != i)
        for dist, j in others:
            reach = max(math.dist(s, p) for poly in faces for p in poly)
            if dist / 2 > reach:
                break
            q = pts[j]
            n = _sub(q, s)
            k = math.sqrt(_dot(n, n))
            n = (n[0] / k, n[1] / k, n[2] / k)
            mid = tuple((s[t] + q[t]) / 2 for t in range(3))
            faces = _clip(faces, n, _dot(n, mid))
        verts, idx = _index(faces)
        out.append({"site": list(s), "verts": verts, "faces": idx})
    return out


def volume(cell):
    v = 0.0
    P = cell["verts"]
    for f in cell["faces"]:
        a = P[f[0]]
        for j in range(1, len(f) - 1):
            v += _dot(a, _cross(P[f[j]], P[f[j + 1]]))
    return v / 6.0


def centroid(cell):
    P = cell["verts"]
    return tuple(sum(p[k] for p in P) / len(P) for k in range(3))
