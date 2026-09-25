"""night_street layout, pure (phase 5 Task 70).

A straight street in the street frame (u across the road, v along it; v follows the subject's longer
horizontal axis so a drive runs down the road, like the courtyard):
- the road is `width` = max(ROAD_MIN_M, ROAD_K x longest) across and `length` = max(LEN_MIN_M, LEN_K x
  longest) long; kerbs (real size) at u = +-width/2, a pavement PAVE_M wide beyond each kerb;
- facade blocks stand along one or both pavements: seeded widths 3-12 m and heights 4-15 m, a window grid
  per block (real-size windows on 3.2 m floors, each with a seeded `key`: the build lights the windows whose
  key is under the world's windowsLit);
- lamp posts every 12-20 m (seeded) on the pavement edge, alternating sides when both sides are built;
- 0-4 neon bars (seeded) on the facades at shopfront height, never inside the camera clear zone;
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
BOX_MARGIN_K, BOX_MARGIN_M = 0.15, 0.10   # the courtyard's exclusion margin (eng)
SMALL_M = 0.5                        # (eng) below this the street is dressed for a small product
SMALL_PUSH_M = 6.0                   # (eng) extra facade setback for a small subject


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


def segment_hits(a, b, lo, hi):
    """True when the segment a -> b passes through the box [lo, hi] (slab test)."""
    t0, t1 = 0.0, 1.0
    for i in range(3):
        d = b[i] - a[i]
        if abs(d) < 1e-12:
            if not lo[i] <= a[i] <= hi[i]:
                return False
            continue
        u0, u1 = (lo[i] - a[i]) / d, (hi[i] - a[i]) / d
        t0, t1 = max(t0, min(u0, u1)), min(t1, max(u0, u1))
        if t0 > t1:
            return False
    return True


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
                                 side=s, u=s * face_u, v0=v, v1=v + w, height=h, windows=windows))
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
                          hue=rng.uniform(-30.0, 30.0)))

    def clear(it):
        r = (it["min"][0], it["min"][1], it["max"][0], it["max"][1])
        return not _hit(r, excl) and not _hit(r, lane)

    lamps = [it for it in lamps if clear(it)]
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
        lamps, neon, facades = ([it for it in group if not blocks(it)] for group in (lamps, neon, facades))
    return {"road": {"width": width, "length": length, "centre": list(centre), "alongAxis": "y" if ia == 0 else "x",
                     "faceU": face_u, "sides": list(sides)},
            "exclusion": excl, "lane": lane, "kerbs": kerbs, "pavements": pavements, "facades": facades,
            "lamps": lamps, "neon": neon}
