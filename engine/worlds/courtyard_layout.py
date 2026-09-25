"""rain_courtyard layout, pure (phase 5 Task 63; port of render-studio rain_scene.build, generalised).

render-studio built a 14 x 32 m asphalt court for one car: curbs at x = +-4.8 m, tree beds with trees,
two benches, two drainage grates, 620 fallen leaves plus 90 loose ones, a grass verge, and a leaf exclusion
box around THAT car. Here, in the court frame (u across, v along the court; v follows the subject's longer
horizontal axis so a drive runs down the court):
- the court is `width` = max(COURT_MIN_M, COURT_K x longest) across and width x 32/14 long; render-studio
  positions scale with s = width / 14, while every prop keeps its REAL size (a bench stays a bench);
- nothing is placed inside the subject's bounds + margin (`exclusion`) or, when the world has a drive lane,
  inside the lane down the court (`lane`);
- a small subject (< SMALL_M) keeps the court but its set dressing is moved out of the hero camera's view
  (mirrored behind the camera plane), so the camera sees asphalt, puddles and the soft background dome;
- every draw comes from random.Random(seed), so a layout is a pure function of (profile, seed, dressing).
Numbers marked (eng) are in the calibration register."""
import math
import random

COURT_MIN_M = 14.0          # render-studio's court width
COURT_K = 6.0               # (eng) court width, x the subject's longest side
COURT_ASPECT = 32.0 / 14.0  # render-studio's court length / width
BOX_MARGIN_K, BOX_MARGIN_M = 0.15, 0.10   # (eng) exclusion = bounds + 0.15 x longest + 0.1 m
SMALL_M = 0.5               # (eng) below this the set dressing leaves the hero view
LITTER, LOOSE = 620, 90     # render-studio's fallen and loose leaves
GRASS_TUFTS = 300           # (eng) render-studio planted 1800 instances; one joined mesh here
SPARSE_KEEP = 1.0 / 3.0     # (eng) sparse dressing keeps a third of the litter and grass

# Real-size prop boxes (metres): (across, along, height). Trees: the crown's footprint.
# The bench is the pinned modular_street_seating_1k backed bench (measured 2026-09-25: 2.45 x 0.67 x 0.87 m;
# render-studio's box bench was 0.5 x 1.8); the manhole is water_manhole_cover_1k's frame.
SIZES = {"curb": (0.28, 0.982, 0.13), "tree_bed": (1.8, 2.5, 0.14), "bench": (0.67, 2.45, 0.87),
         "grate": (0.30, 0.88, 0.012), "manhole": (0.69, 0.69, 0.04), "tree": (3.6, 3.6, 5.0)}


def _frame(profile):
    """(centre xy, across-axis index, along-axis index, half across, half along) of the subject."""
    cx, cy = profile.center[0], profile.center[1]
    hx, hy = profile.half[0], profile.half[1]
    return ((cx, cy), 0, 1, hx, hy) if hy >= hx else ((cx, cy), 1, 0, hy, hx)


def _to_placed(centre, ia, u, v):
    """Court frame (u across, v along) -> placed xy."""
    return (centre[0] + u, centre[1] + v) if ia == 0 else (centre[0] + v, centre[1] + u)


def _rect(centre, ia, u0, v0, u1, v1):
    (x0, y0), (x1, y1) = _to_placed(centre, ia, u0, v0), _to_placed(centre, ia, u1, v1)
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def footprint(prop):
    """Placed xy rect (x0, y0, x1, y1) of a prop's box."""
    (x, y), (sx, sy, _) = prop["xy"], prop["size"]
    if prop["yaw"] % 180:
        sx, sy = sy, sx
    return (x - sx / 2, y - sy / 2, x + sx / 2, y + sy / 2)


def box(prop):
    """(boundsMin, boundsMax) of a prop, placed metres, ground at z = 0."""
    x0, y0, x1, y1 = footprint(prop)
    return (x0, y0, 0.0), (x1, y1, prop["size"][2])


def _hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _props(rng, s, length, dressing):
    """render-studio's dressing in the court frame, positions x s, sizes real. Yields (kind, u, v, extra)."""
    cu = 4.8 * s
    for side in (-1, 1):
        n = int(length)                                       # one 0.98 m stone per metre
        for j in range(n):
            yield "curb", side * cu, -length / 2 + 0.5 + j, {}
    for side in (-1, 1):
        for y in (-7, -1, 6, 12):
            if dressing == "sparse" and y > 0:
                continue
            near = y < 0
            u, v = side * (cu + (0.9 if near else 2.7) * max(1.0, s ** 0.5)), y * s
            yield "tree_bed", u, v, {}
            yield "tree", u, v, {"height": rng.uniform(4.4, 5.7) * (1.6 if near else 1.0)}
    if dressing == "full":
        for u, v in ((-5.8, 2.3), (5.8, -4.0)):
            yield "bench", u * s, v * s, {}
    for v in (-5.0, 5.0):
        yield "grate", 4.1 * s, v * s, {}
    yield "manhole", -2.6 * s, 8.5 * s, {}                    # (eng) one service cover: a scale cue up the court


def _behind(hero, b, aspect):
    """The xy shift that moves a prop box wholly behind the hero camera (straight back along the camera's
    horizontal forward, 5 cm past the plane). None when it is already behind."""
    from engine.geometry import box_corners, project
    depths = [project(hero, c, aspect)[2] for c in box_corners(*b)]
    if max(depths) <= 0:
        return None
    F = [t - q for t, q in zip(hero.target, hero.position)]
    n = math.sqrt(sum(v * v for v in F))
    fh = math.hypot(F[0], F[1]) / n                             # |horizontal part| of the unit forward
    fx, fy = F[0] / (n * fh), F[1] / (n * fh)
    t = max(depths) / fh + 0.05
    return -fx * t, -fy * t


def layout(profile, seed, dressing="full", drive_lane_m=24.0, hero=None, aspect="9:16"):
    rng = random.Random(seed)
    centre, ia, _, h_across, h_along = _frame(profile)
    width = max(COURT_MIN_M, COURT_K * profile.longest)
    length = width * COURT_ASPECT
    s = width / COURT_MIN_M
    margin = BOX_MARGIN_K * profile.longest + BOX_MARGIN_M
    excl = _rect(centre, ia, -(h_across + margin), -(h_along + margin), h_across + margin, h_along + margin)
    lane = (_rect(centre, ia, -(h_across + margin), -length / 2, h_across + margin, length / 2)
            if drive_lane_m > 0 else excl)
    small = hero is not None and profile.longest < SMALL_M
    props = []
    for kind, u, v, extra in _props(rng, s, length, dressing):
        yaw = 0 if ia == 0 else 90
        size = SIZES[kind] if kind != "tree" else (*SIZES["tree"][:2], extra["height"])
        pr = {"kind": kind, "xy": _to_placed(centre, ia, u, v), "yaw": yaw, "size": size}
        if kind == "tree":
            pr["height"] = extra["height"]
        if small:
            move = _behind(hero, box(pr), aspect)
            if move is not None:
                pr["xy"] = (pr["xy"][0] + move[0], pr["xy"][1] + move[1])
        r = footprint(pr)
        if _hit(r, excl) or _hit(r, lane):
            continue
        props.append(pr)
    keep = SPARSE_KEEP if dressing == "sparse" else 1.0
    litter = []
    for i in range(LITTER + LOOSE):
        if rng.random() < 0.62:
            u = math.copysign(4.55 - abs(rng.gauss(0, 0.55)), rng.uniform(-1, 1)) * s
        else:
            u = rng.uniform(-4.5, 4.5) * s
        v = rng.uniform(-13, 13) * s
        leaf = {"xy": _to_placed(centre, ia, u, v), "yaw": rng.uniform(0, 360.0),
                "width": rng.uniform(0.016, 0.034), "length": rng.uniform(0.055, 0.105), "tint": rng.randrange(5)}
        x, y = leaf["xy"]
        if rng.random() > keep or (excl[0] <= x <= excl[2] and excl[1] <= y <= excl[3]):
            continue
        litter.append(leaf)
    grass = []
    for _ in range(GRASS_TUFTS):
        u = rng.choice((-1, 1)) * (5.1 + rng.random() ** 1.8 * 22) * s
        v = rng.uniform(-length, length)
        tuft = {"xy": _to_placed(centre, ia, u, v), "yaw": rng.uniform(0, 360.0), "height": rng.uniform(0.16, 0.30),
                "pick": rng.random()}
        if rng.random() <= keep:
            grass.append(tuft)
    return {"court": {"width": width, "length": length, "scale": s, "centre": list(centre),
                      "alongAxis": "y" if ia == 0 else "x"},
            "exclusion": excl, "lane": lane, "props": props, "litter": litter, "grass": grass}
