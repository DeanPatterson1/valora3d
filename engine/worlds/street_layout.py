"""night_street layout, pure (phase 5 Task 70).

A straight street in the street frame (u across the road, v along it; v follows the subject's longer
horizontal axis so a drive runs down the road, like the courtyard):
- the road is `width` = max(ROAD_MIN_M, ROAD_K x longest) across and `length` = max(LEN_MIN_M, LEN_K x
  longest) long; kerbs (real size) at u = +-width/2, a pavement PAVE_M wide beyond each kerb;
- facade blocks stand along one or both pavements: seeded widths 3-12 m and heights 4-15 m, a window grid
  per block (real-size windows on 3.2 m floors, each with a seeded `key`: the build lights the windows whose
  key is under the world's windowsLit);
- lamp posts every 12-20 m (seeded) on the pavement edge, alternating sides when both sides are built;
- 0-4 neon bars (seeded) on the facades at shopfront height, never inside the camera clear zone; a bar keeps
  its facade's `fid` and goes when its facade goes (review chunk 4 #7: no floating signage);
- kerbs and pavements are solid 15 cm slabs: a camera key within SLAB_CLEAR_M of one, or a sight line from a
  camera to the subject through one, cuts a dropped-kerb gap (+-CAM_CLEAR_M along the road) instead of
  dropping the street (review chunk 4 #5: a low hero camera stood inside the pavement);
- nothing is placed inside the subject's bounds + margin (`exclusion`) or, when the world has a drive lane,
  inside the lane down the road (`lane`);
- a small subject (< SMALL_M) gets the facades pushed back SMALL_PUSH_M, and with the hero pose given,
  every lamp post after the first one the hero camera sees is moved behind the camera plane, so a sneaker
  sees at most one lamp, not a row of 5 m giants;
- every draw comes from random.Random(seed): a layout is a pure function of its arguments.
Numbers marked (eng) are in the calibration register."""
import math
import random

ROAD_MIN_M, ROAD_K = 7.0, 1.6        # (eng) two lanes; a larger subject gets a wider road
LEN_MIN_M, LEN_K = 30.0, 8.0         # plan: length = max(30 m, 8 x longest)
PAVE_M = 3.0                         # (eng) pavement width
KERB = (0.15, 0.15)                  # (eng) kerb width, height (real size)
FACADE_W = (3.0, 12.0)               # plan: seeded block widths
FACADE_H = (4.0, 15.0)               # plan: seeded block heights
FACADE_DEPTH_M = 6.0                 # (eng) a block's depth (only its front face is seen)
BOTH_SIDES_P = 0.7                   # (eng) share of layouts with facades on both sides
FLOOR_M, WINDOW = 3.2, (1.2, 1.5)    # (eng) floor height; window width x height (real size)
WINDOW_PITCH_M = 2.6                 # (eng) window spacing along a facade
LAMP_GAP = (12.0, 20.0)              # plan: lamp posts every 12-20 m
LAMP_H, LAMP_INSET = 5.0, 0.4        # (eng) post height; distance in from the kerb onto the pavement
LAMP_BOX = (0.3, 0.3)                # (eng) the post + head footprint, metres
NEON_MAX = 4                         # plan: 0-4 neon bars
NEON = (2.4, 0.12, 0.12)             # (eng) bar length, height, depth (real size)
NEON_Z = (3.0, 5.0)                  # (eng) shopfront height band
CAM_CLEAR_M = 1.5                    # (eng) no neon bar within this of the hero camera
SLAB_CLEAR_M = 0.3                   # (eng) a camera key within this of a kerb/pavement slab gets a dropped-kerb gap
BOX_MARGIN_K, BOX_MARGIN_M = 0.15, 0.10   # the courtyard's exclusion margin (eng)
SMALL_M = 0.5                        # (eng) below this the street is dressed for a small product
SMALL_PUSH_M = 6.0                   # (eng) extra facade setback for a small subject
# art pass round 2 (2026-09-25): street furniture from its own seeded stream (never moves anything above).
# type -> (across, along, height) real metres, and where it stands: "kerb" (on the pavement by the kerb),
# "wall" (on the pavement against the facade line) or "road" (parked / set in the road)
FURNITURE = {"bin": ((0.62, 0.56, 0.91), "kerb"), "hydrant": ((0.3, 0.3, 0.8), "kerb"),
             "utility_box": ((0.45, 0.55, 1.12), "wall"), "trashbag": ((0.5, 0.55, 0.57), "wall"),
             "chalkboard": ((0.76, 0.92, 1.51), "wall"), "planter": ((0.47, 1.25, 0.45), "wall"),
             "parked_car": ((1.8, 4.4, 1.41), "road"), "manhole": ((0.7, 0.7, 0.04), "road")}
FURN_GAP = (2.5, 6.0)                # (eng) spacing of furniture along each pavement
FURN_WEIGHTS = {"bin": 3, "hydrant": 1, "utility_box": 1, "trashbag": 2, "chalkboard": 1, "planter": 2}
PARKED_P, MANHOLES = 0.35, (1, 3)    # (eng) chance of a parked car per side; manhole covers in the road
FURN_KERB_IN, FURN_WALL_IN = 0.45, 0.35   # (eng) how far in from the kerb / out from the facade line
FURN_SEED = 0xF0E1
FURN_FRAME_PAD_M = 0.6               # (eng) furniture sight-line margin


def _frame(profile):
    cx, cy = profile.center[0], profile.center[1]
    hx, hy = profile.half[0], profile.half[1]
    return ((cx, cy), 0, hx, hy) if hy >= hx else ((cx, cy), 1, hy, hx)


def _to_placed(centre, ia, u, v):
    return (centre[0] + u, centre[1] + v) if ia == 0 else (centre[0] + v, centre[1] + u)


def _rect(centre, ia, u0, v0, u1, v1):
    (x0, y0), (x1, y1) = _to_placed(centre, ia, u0, v0), _to_placed(centre, ia, u1, v1)
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def box(item):
    """(boundsMin, boundsMax) of a layout item: placed metres."""
    return tuple(item["min"]), tuple(item["max"])


def _item(kind, centre, ia, ua, va, ub, vb, z0, z1, **extra):
    r = _rect(centre, ia, ua, va, ub, vb)
    return {"kind": kind, "min": (r[0], r[1], z0), "max": (r[2], r[3], z1), **extra}


def seen(hero, item, aspect):
    """True when any corner of the item is in front of the hero camera and inside its frame."""
    from engine.geometry import box_corners, project
    for c in box_corners(*box(item)):
        x, y, d = project(hero, c, aspect)
        if d > 0 and abs(x) <= 1.02 and abs(y) <= 1.02:
            return True
    return False


def _behind(hero, item, aspect):
    """The item shifted straight back along the hero camera's horizontal forward, 5 cm past its plane."""
    from engine.geometry import box_corners, project
    depths = [project(hero, c, aspect)[2] for c in box_corners(*box(item))]
    F = [t - q for t, q in zip(hero.target, hero.position)]
    n = math.sqrt(sum(v * v for v in F))
    fh = math.hypot(F[0], F[1]) / n
    fx, fy = F[0] / (n * fh), F[1] / (n * fh)
    t = max(depths) / fh + 0.05
    lo, hi = item["min"], item["max"]
    return {**item, "min": (lo[0] - fx * t, lo[1] - fy * t, lo[2]), "max": (hi[0] - fx * t, hi[1] - fy * t, hi[2])}


def _near(it, point, pad):
    return all(it["min"][i] - pad <= point[i] <= it["max"][i] + pad for i in range(3))


def segment_span(a, b, lo, hi):
    """(t0, t1) of the segment a -> b inside the box [lo, hi] (slab test), or None when it misses."""
    t0, t1 = 0.0, 1.0
    for i in range(3):
        d = b[i] - a[i]
        if abs(d) < 1e-12:
            if not lo[i] <= a[i] <= hi[i]:
                return None
            continue
        u0, u1 = (lo[i] - a[i]) / d, (hi[i] - a[i]) / d
        t0, t1 = max(t0, min(u0, u1)), min(t1, max(u0, u1))
        if t0 > t1:
            return None
    return t0, t1


def segment_hits(a, b, lo, hi):
    """True when the segment a -> b passes through the box [lo, hi] (slab test)."""
    return segment_span(a, b, lo, hi) is not None


def _carve(slabs, centre, ia, cameras, pts):
    """Kerb/pavement slabs with a dropped-kerb gap wherever a camera key stands in one (within SLAB_CLEAR_M) or
    looks at the subject through one. Gaps run +-CAM_CLEAR_M along the road; the slab's other extents stay."""
    va = 1 if ia == 0 else 0                     # the placed axis v runs along
    out = []
    for it in slabs:
        gaps = []
        for c in cameras:
            if _near(it, c, SLAB_CLEAR_M):
                gaps.append((c[va] - CAM_CLEAR_M, c[va] + CAM_CLEAR_M))
            for q in pts:
                span = segment_span(c, q, it["min"], it["max"])
                if span is not None:
                    a, b = (c[va] + t * (q[va] - c[va]) for t in span)
                    gaps.append((min(a, b) - CAM_CLEAR_M, max(a, b) + CAM_CLEAR_M))
        if not gaps:
            out.append(it)
            continue
        pieces, lo = [], it["min"][va]
        for g0, g1 in sorted(gaps):
            if g0 > lo:
                pieces.append((lo, min(g0, it["max"][va])))
            lo = max(lo, g1)
        if lo < it["max"][va]:
            pieces.append((lo, it["max"][va]))
        for p0, p1 in pieces:
            if p1 - p0 > 1e-6:
                mn, mx = list(it["min"]), list(it["max"])
                mn[va], mx[va] = p0, p1
                out.append({**it, "min": tuple(mn), "max": tuple(mx)})
    return out


def _sight(profile):
    """The points a camera must see: the subject's bounds corners and centre."""
    from engine.geometry import box_corners
    return box_corners(profile.boundsMin, profile.boundsMax) + [tuple(profile.center)]


def layout(profile, seed, lane_m=30.0, hero=None, aspect="9:16", cameras=()):
    """cameras: every camera key position. A lamp, neon bar or facade within CAM_CLEAR_M of one is dropped
    (the camera clear zone: no set piece sits on a camera path), and so is one standing between a camera and
    the subject (a facade block in front of a wide orbit leaves an alley instead of a wall)."""
    rng = random.Random(seed)
    centre, ia, h_across, h_along = _frame(profile)
    width = max(ROAD_MIN_M, ROAD_K * profile.longest)
    length = max(LEN_MIN_M, LEN_K * profile.longest)
    small = profile.longest < SMALL_M
    margin = BOX_MARGIN_K * profile.longest + BOX_MARGIN_M
    excl = _rect(centre, ia, -(h_across + margin), -(h_along + margin), h_across + margin, h_along + margin)
    lane = (_rect(centre, ia, -(h_across + margin), -length / 2, h_across + margin, length / 2)
            if lane_m > 0 else excl)
    half = width / 2
    face_u = half + KERB[0] + PAVE_M + (SMALL_PUSH_M if small else 0.0)
    sides = (-1, 1) if rng.random() < BOTH_SIDES_P else (rng.choice((-1, 1)),)

    kerbs = [_item("kerb", centre, ia, s * half - KERB[0] / 2, -length / 2, s * half + KERB[0] / 2, length / 2,
                   0.0, KERB[1], side=s) for s in (-1, 1)]
    pavements = [_item("pavement", centre, ia, s * (half + KERB[0] / 2), -length / 2,
                       s * (face_u), length / 2, 0.0, KERB[1], side=s) for s in (-1, 1)]

    facades = []
    for s in sides:
        v = -length / 2
        while v < length / 2:
            w = min(rng.uniform(*FACADE_W), length / 2 - v)
            h = rng.uniform(*FACADE_H)
            windows = []
            floors = int((h - 1.0) // FLOOR_M)
            cols = int(w // WINDOW_PITCH_M)
            for f in range(floors):
                for c in range(cols):
                    windows.append({"v": v + (c + 0.5) * w / cols, "z": 1.2 + f * FLOOR_M, "key": rng.random()})
            facades.append(_item("facade", centre, ia, s * face_u, v, s * (face_u + FACADE_DEPTH_M), v + w, 0.0, h,
                                 side=s, u=s * face_u, v0=v, v1=v + w, height=h, windows=windows,
                                 fid=len(facades)))
            v += w

    lamps, v, k = [], -length / 2 + rng.uniform(0.0, LAMP_GAP[0]), 0
    while v < length / 2:
        s = sides[k % len(sides)] if len(sides) == 2 else sides[0]
        u = s * (half + KERB[0] + LAMP_INSET)
        lamps.append(_item("lamp", centre, ia, u - LAMP_BOX[0] / 2, v - LAMP_BOX[1] / 2, u + LAMP_BOX[0] / 2,
                           v + LAMP_BOX[1] / 2, 0.0, LAMP_H, side=s, head=(*_to_placed(centre, ia, u - s * 0.6, v), LAMP_H)))
        v += rng.uniform(*LAMP_GAP)
        k += 1

    neon = []
    for _ in range(rng.randint(0, NEON_MAX)):
        fa = facades[rng.randrange(len(facades))]
        if fa["v1"] - fa["v0"] < NEON[0] + 0.4:
            continue
        v0 = rng.uniform(fa["v0"] + 0.2, fa["v1"] - NEON[0] - 0.2)
        z = rng.uniform(*NEON_Z)
        u = fa["u"] - math.copysign(NEON[2], fa["u"])
        neon.append(_item("neon", centre, ia, min(u, fa["u"]), v0, max(u, fa["u"]), v0 + NEON[0], z, z + NEON[1],
                          hue=rng.uniform(-30.0, 30.0), fid=fa["fid"]))

    def clear(it):
        r = (it["min"][0], it["min"][1], it["max"][0], it["max"][1])
        return not _hit(r, excl) and not _hit(r, lane)

    furniture = [it for it in _furniture(seed, centre, ia, width, length, face_u, lamps) if clear(it)]
    lamps = [it for it in lamps if clear(it)]
    lamp_lights = []
    facades = [it for it in facades if clear(it)]
    neon = [it for it in neon if clear(it)]
    if hero is not None:
        cam = hero.position
        neon = [it for it in neon if math.dist(cam, tuple((a + b) / 2 for a, b in zip(it["min"], it["max"])))
                > CAM_CLEAR_M]
        if small:
            kept, shown = [], 0
            for it in sorted(lamps, key=lambda it: math.dist(cam, it["head"])):
                if seen(hero, it, aspect):
                    shown += 1
                    if shown > 1:
                        moved = _behind(hero, it, aspect)
                        shift = [moved["min"][i] - it["min"][i] for i in range(2)]
                        it = {**moved, "head": (it["head"][0] + shift[0], it["head"][1] + shift[1], it["head"][2])}
                kept.append(it)
            lamps = kept
    if cameras:
        pts = _sight(profile)

        def blocks(it):
            return any(_near(it, c, CAM_CLEAR_M) or any(segment_hits(c, q, it["min"], it["max"]) for q in pts)
                       for c in cameras)
        # round 3: a lamp dropped for a camera leaves its light behind (no post): the near pavement is lit
        lamp_lights = [{**it, "kind": "lamp_light"} for it in lamps if blocks(it)]
        lamps, neon, facades = ([it for it in group if not blocks(it)] for group in (lamps, neon, facades))

        def frames_over(it):                  # furniture: a margin round the box, so a bin or hydrant never
            m = FURN_FRAME_PAD_M              # stands half over the subject in a low long-lens frame
            lo = tuple(v - m for v in it["min"][:2]) + (it["min"][2],)
            hi = tuple(v + m for v in it["max"][:2]) + (it["max"][2] + m,)
            return blocks(it) or any(segment_hits(c, q, lo, hi) for c in cameras for q in pts)
        furniture = [it for it in furniture if not frames_over(it)]
    if hero is not None:
        furniture = [it for it in furniture if not _near(it, tuple(hero.position), CAM_CLEAR_M)]
    slab_cams = list(cameras) + ([tuple(hero.position)] if hero is not None else [])
    if slab_cams:
        pts = _sight(profile)
        kerbs = _carve(kerbs, centre, ia, slab_cams, pts)
        pavements = _carve(pavements, centre, ia, slab_cams, pts)
    standing = {fa["fid"] for fa in facades}
    neon = [it for it in neon if it["fid"] in standing]          # a bar goes with its facade
    return {"road": {"width": width, "length": length, "centre": list(centre), "alongAxis": "y" if ia == 0 else "x",
                     "faceU": face_u, "sides": list(sides)},
            "exclusion": excl, "lane": lane, "kerbs": kerbs, "pavements": pavements, "facades": facades,
            "lamps": lamps, "neon": neon, "furniture": furniture, "lampLights": lamp_lights}


def _furniture(seed, centre, ia, width, length, face_u, lamps):
    """Bins, hydrants, utility boxes, bags, cafe boards and planters along both pavements, a parked (covered)
    car per side now and then, and manhole covers in the road; the same clearance and sight-line rules as
    the lamps drop them. Its own random stream: every other layout item is unchanged."""
    rng = random.Random(seed ^ FURN_SEED)
    half = width / 2
    va = 1 if ia == 0 else 0
    lamp_v = [((it["min"][va] + it["max"][va]) / 2) for it in lamps]
    kinds = [k for k, w in FURN_WEIGHTS.items() for _ in range(w)]
    out = []

    def add(t, u, v, s, yaw=0.0):
        (a, b, h), _ = FURNITURE[t]
        z0 = KERB[1] if FURNITURE[t][1] != "road" else 0.0
        out.append(_item("furniture", centre, ia, u - a / 2, v - b / 2, u + a / 2, v + b / 2, z0, z0 + h,
                         type=t, side=s, yaw=yaw, u=u, v=v))
    for s in (-1, 1):
        v = -length / 2 + rng.uniform(0.5, FURN_GAP[1])
        while v < length / 2 - 0.5:
            t = rng.choice(kinds)
            (a, b, h), where = FURNITURE[t]
            if not any(abs(v - lv) < 0.8 for lv in lamp_v):
                u = s * (half + KERB[0] + FURN_KERB_IN) if where == "kerb" else s * (face_u - FURN_WALL_IN - a / 2)
                add(t, u, v, s, rng.uniform(-15.0, 15.0))
                if t == "bin" and rng.random() < 0.5:                  # a bag or two left by the bin
                    add("trashbag", s * (face_u - FURN_WALL_IN - 0.25), v + rng.uniform(-0.8, 0.8), s,
                        rng.uniform(0.0, 360.0))
            v += rng.uniform(*FURN_GAP)
        if rng.random() < PARKED_P:
            add("parked_car", s * (half - 1.0), rng.uniform(-length / 2 + 3.0, length / 2 - 3.0), s,
                rng.uniform(-2.0, 2.0))
    for _ in range(rng.randint(*MANHOLES)):
        add("manhole", rng.uniform(-half + 1.0, half - 1.0), rng.uniform(-length / 2 + 1.0, length / 2 - 1.0), 0,
            rng.uniform(0.0, 360.0))
    return out


# Round 11 (owner's r10 review: "the street props were invisible; the night feels like a set"): the seeded furniture
# lands wherever the street's plan puts it, mostly out of the hook's frame. hero_dressing adds a few pieces WHERE the
# hook camera looks: a covered car parked down the street near a lamp, and bins with a bag on the kerb the camera
# sees, each in frame, clear of the subject's outline and of every camera-to-subject sight line. (eng)
HERO_BINS = 2
HERO_PARK_V_M = (5.0, 22.0)          # parked car: this far along the street past the subject's end
HERO_KERB_V_M = (-6.0, 14.0)         # kerb pieces: along the street round the subject
HERO_SEED = 0x8E5D


def _hull(pts):
    """Convex hull (counter-clockwise) of 2D points (monotone chain)."""
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def _inside(poly, q, pad=0.0):
    """q inside the convex CCW polygon (grown by about `pad`)."""
    if len(poly) < 3:
        return False
    for a, b in zip(poly, poly[1:] + poly[:1]):
        ex, ey = b[0] - a[0], b[1] - a[1]
        n = math.hypot(ex, ey) or 1.0
        if (ex * (q[1] - a[1]) - ey * (q[0] - a[0])) / n < -pad:
            return False
    return True


def outline(profile, hero, aspect):
    """The subject's projected outline in the hero frame: the convex hull of its surface samples (the bounds box's
    corners overstate a car's outline by ~0.3 of the frame), else of its box corners."""
    from engine.geometry import box_corners, project
    pts = getattr(profile, "surfaceSamples", None) or box_corners(profile.boundsMin, profile.boundsMax)
    q = [project(hero, tuple(p), aspect) for p in pts]
    return _hull([(x, y) for x, y, d in q if d > 0])


def hero_dressing(profile, lay, hero, aspect, seed, cameras=()):
    """Extra furniture items (layout()'s format) for the hook's frame; [] without a hero pose."""
    from engine.geometry import box_corners, project
    if hero is None:
        return []
    rng = random.Random(seed ^ HERO_SEED)
    centre, ia, _, h_along = _frame(profile)
    width = lay["road"]["width"]
    half = width / 2
    hull = outline(profile, hero, aspect)
    pts = _sight(profile)
    cams = list(cameras) + [tuple(hero.position)]
    excl, lane = lay["exclusion"], lay["lane"]
    taken = [it for it in lay["furniture"]]

    def ok(it, pad=0.1):
        r = (it["min"][0], it["min"][1], it["max"][0], it["max"][1])
        if _hit(r, excl) or not seen(hero, it, aspect):
            return False
        if it.get("type") != "parked_car" and _hit(r, lane):
            return False
        pr = [project(hero, c, aspect) for c in box_corners(*box(it))]
        pr = [q for q in pr if q[2] > 0]
        if len(pr) < 8:
            return False
        # some of it shows: corners outside the subject's projected outline, inside the frame
        shows = [q for q in pr if abs(q[0]) < 0.97 and abs(q[1]) < 0.97 and not _inside(hull, q[:2], 0.02)]
        if len(shows) < 2:
            return False
        lo = tuple(v - pad for v in it["min"][:2]) + (it["min"][2],)
        hi = tuple(v + pad for v in it["max"][:2]) + (it["max"][2],)
        if any(segment_hits(c, q, lo, hi) for c in cams for q in pts) or any(_near(it, c, CAM_CLEAR_M) for c in cams):
            return False
        return not any(_hit(r, (t["min"][0], t["min"][1], t["max"][0], t["max"][1])) for t in taken)

    def make(t, u, v, s, yaw):
        (a, b, h), where = FURNITURE[t]
        z0 = KERB[1] if where != "road" else 0.0
        return _item("furniture", centre, ia, u - a / 2, v - b / 2, u + a / 2, v + b / 2, z0, z0 + h,
                     type=t, side=s, yaw=yaw, u=u, v=v, hero=True)
    out = []
    va = 1 if ia == 0 else 0
    lamp_v = [((it["min"][va] + it["max"][va]) / 2, it.get("side", 1)) for it in lay["lamps"]]
    cands = []
    for s in (-1, 1):
        for end in (-1, 1):
            v = h_along + HERO_PARK_V_M[0]
            while v <= h_along + HERO_PARK_V_M[1]:
                near_lamp = min((abs(end * v - lv) for lv, ls in lamp_v if ls == s), default=99.0)
                cands.append((near_lamp + rng.uniform(0.0, 2.0), s, end * v))
                v += 1.5
    for _, s, v in sorted(cands):
        it = make("parked_car", s * (half - 1.0), v, s, rng.uniform(-2.0, 2.0))
        if ok(it, pad=0.3):
            out.append(it)
            taken.append(it)
            break
    kerb_u = half + KERB[0] + FURN_KERB_IN
    placed = 0
    vs = [HERO_KERB_V_M[0] + (HERO_KERB_V_M[1] - HERO_KERB_V_M[0]) * k / 40.0 for k in range(41)]
    rng.shuffle(vs)
    for s in (-1, 1):
        for v in vs:
            if placed >= HERO_BINS:
                break
            it = make("bin", s * kerb_u, v, s, rng.uniform(-15.0, 15.0))
            if ok(it):
                out.append(it)
                taken.append(it)
                placed += 1
                bag = make("trashbag", s * (kerb_u + 0.55), v + rng.choice((-0.7, 0.7)), s, rng.uniform(0.0, 360.0))
                if ok(bag, pad=0.02):
                    out.append(bag)
                    taken.append(bag)
    return out


# Round 12 (owner's r11 review: "a showpiece render, a curated key"): a car photographed at night is parked under a
# street lamp. hero_lamp puts that lamp's light near the subject: on a pavement, over the kerb, a few metres along the
# street, JUST outside the hook frame (the post is out of shot, its pool is not), on the camera's side of the car so
# the flank, bonnet and the cabin through the windscreen take its light. (eng)
HERO_LAMP_ALONG = (1.5, 2.5, 0.5, 3.5, -1.5, -2.5)   # along-street offsets (+ toward the camera), tried in order
HERO_LAMP_Z = 5.0 * 0.87                                     # a lantern head (LANTERN_Z of a LAMP_H post)


def hero_lamp(profile, lay, hero, aspect):
    """(x, y, z) of the light of a lamp standing just out of the hook frame near the subject, or None (no hero pose,
    or every spot is in frame). Pure."""
    from engine.geometry import project
    if hero is None:
        return None
    centre = lay["road"]["centre"]
    ia = 0 if lay["road"]["alongAxis"] == "y" else 1
    half = lay["road"]["width"] / 2
    cu = (hero.position[0] - centre[0]) if ia == 0 else (hero.position[1] - centre[1])
    near = 1.0 if cu >= 0 else -1.0                           # the pavement on the camera's side first
    cv = (hero.position[1] - centre[1]) if ia == 0 else (hero.position[0] - centre[0])
    toward = 1.0 if cv >= 0 else -1.0                         # along-street offsets toward the camera first
    for s in (near, -near):
        u = s * (half + KERB[0] + LAMP_INSET)
        for dv in HERO_LAMP_ALONG:
            x, y = _to_placed(centre, ia, u, toward * dv)
            tx, ty, d = project(hero, (x, y, HERO_LAMP_Z), aspect)
            if d <= 0 or abs(tx) > 1.08 or abs(ty) > 1.08:
                return (x, y, HERO_LAMP_Z)
    return None
