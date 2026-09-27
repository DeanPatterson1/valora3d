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


# Round 11 (owner's r10 review: "the courtyard background is blank and washed out"; v04 f_06 carries lamp posts, a
# bench, a bus and a building faint in the fog, and wet leaves everywhere). Anchors placed where the HOOK camera
# looks (not where the court's plan puts them), each checked in frame and clear of the subject's own outline. (eng)
ANCHOR_LAMPS = ((19.0, (5.5, -6.5, 9.0, -9.5, 3.5, -3.5)), (29.0, (-7.0, 8.0, -11.0, 12.0, -4.0, 4.5)),
                (41.0, (9.0, -10.0, 14.0, -15.0, 5.0)))   # (distance past the subject, lateral tries) per lamp
ANCHOR_LAMP_H = 5.8          # lamp post height, metres (a park / car-park column lamp)
_LAT = (0.0, 4.0, -4.0, 8.0, -8.0, 12.0, -12.0, 16.0, -16.0, 20.0, -20.0)
ANCHOR_BLOCKS = (("bus", 56.0, _LAT, (11.5, 2.55, 3.1)),)
# round 12: the far "building" masses are gone (owner-delegated court read: a pale flat slab in front of the fogged
# trees; r12 tried the street's facade kit on it at two fog levels and the fog left the same slab either way)
ANCHOR_BENCH_D = (6.0, 9.0, 3.0, 12.0, 0.0, 15.0)     # bench tries: along the view past the subject's centre ...
ANCHOR_BENCH_O = (-6.0, 6.0, -8.0, 8.0, -4.5, 4.5, -10.0, 10.0, -12.0, 12.0)   # ... and across it, metres
ANCHOR_LEAVES = 90
ANCHOR_LEAF_RANGE = (2.6, 18.0)   # distance from the camera, metres (r11a: 170 from 1.2 m read as a carpet of chips)
ANCHOR_SEED = 0xA7C4


def court_anchors(profile, hero, aspect, seed, exclusion, max_dist=None):
    """{"lamps": [(x, y)], "blocks": [(kind, x, y, (w, d, h), yaw_deg)], "bench": (x, y, yaw_deg) | None,
    "leaves": [leaf dicts as layout()'s litter]}. Pure; empty without a hero pose."""
    from engine.geometry import box_corners, project
    out = {"lamps": [], "blocks": [], "bench": None, "leaves": []}
    if hero is None:
        return out
    rng = random.Random(seed ^ ANCHOR_SEED)
    cx, cy = profile.center[0], profile.center[1]
    fx, fy = cx - hero.position[0], cy - hero.position[1]
    n = math.hypot(fx, fy) or 1.0
    fx, fy = fx / n, fy / n
    rx, ry = fy, -fx
    car = [project(hero, c, aspect) for c in box_corners(profile.boundsMin, profile.boundsMax)]
    car = [c for c in car if c[2] > 0]
    x0 = min(c[0] for c in car) if car else 0.0
    x1 = max(c[0] for c in car) if car else 0.0
    top = project(hero, (cx, cy, profile.boundsMax[2]), aspect)       # the roof over the centre, not a near corner
    ytop = top[1] if top[2] > 0 else 0.0
    far = max_dist if max_dist is not None else 1e9

    def at(d, o):
        return cx + fx * d + rx * o, cy + fy * d + ry * o

    def clear_of_car(x, top_y):          # beside the subject, or its head shows over the roof (a post behind is real)
        return x < x0 - 0.06 or x > x1 + 0.06 or top_y > ytop + 0.04

    for d, tries in ANCHOR_LAMPS:
        for o in tries:
            px, py = at(d, o)
            if math.hypot(px - cx, py - cy) > far:
                continue
            bx, by, bd = project(hero, (px, py, 0.3), aspect)
            tx, ty, td = project(hero, (px, py, ANCHOR_LAMP_H), aspect)
            if bd > 0 and td > 0 and abs(tx) < 0.9 and abs(bx) < 0.9 and clear_of_car(tx, ty):
                out["lamps"].append((px, py))
                break
    for kind, d, tries, size in ANCHOR_BLOCKS:
        for o in tries:
            px, py = at(d, o)
            if math.hypot(px - cx, py - cy) + max(size[:2]) / 2 > far:
                continue
            x, y, dd = project(hero, (px, py, size[2]), aspect)
            if dd > 0 and abs(x) < 0.85 and clear_of_car(x, y) and not any(
                    math.hypot(px - b[1], py - b[2]) < max(size[:2]) for b in out["blocks"]):
                yaw = math.degrees(math.atan2(ry, rx)) + rng.uniform(-12.0, 12.0)
                out["blocks"].append((kind, px, py, size, yaw))
                break
    e = exclusion
    for d in ANCHOR_BENCH_D:                 # the nearest spot beside the subject's outline, in frame, off the court's
        for o in ANCHOR_BENCH_O:             # exclusion (a bench a few metres off, v04 f_06)
            px, py = at(d, o)
            if e and e[0] - 1.0 <= px <= e[2] + 1.0 and e[1] - 1.0 <= py <= e[3] + 1.0:
                continue
            pts = [project(hero, (px + a, py + b, z), aspect) for a in (-1.2, 1.2) for b in (-0.35, 0.35)
                   for z in (0.0, 0.85)]
            if any(q[2] <= 0 for q in pts):
                continue
            inside = [q for q in pts if abs(q[0]) < 0.95 and abs(q[1]) < 0.95 and (q[0] < x0 - 0.02 or q[0] > x1 + 0.02)]
            if len(inside) >= 3:             # part of it at the frame's edge is enough (v04 f_06's bench is cut)
                out["bench"] = (px, py, math.degrees(math.atan2(fy, fx)))
                break
        if out["bench"] is not None:
            break
    tries = 0
    while len(out["leaves"]) < ANCHOR_LEAVES and tries < ANCHOR_LEAVES * 20:
        tries += 1
        d = ANCHOR_LEAF_RANGE[0] + (ANCHOR_LEAF_RANGE[1] - ANCHOR_LEAF_RANGE[0]) * rng.random() ** 1.6
        o = rng.uniform(-0.75, 0.75) * d
        px, py = hero.position[0] + fx * d + rx * o, hero.position[1] + fy * d + ry * o
        if e[0] <= px <= e[2] and e[1] <= py <= e[3]:
            continue
        x, y, dd = project(hero, (px, py, 0.0), aspect)
        if dd <= 0 or abs(x) > 1.05 or abs(y) > 1.05:
            continue
        out["leaves"].append({"xy": (px, py), "yaw": rng.uniform(0, 360.0), "width": rng.uniform(0.016, 0.034),
                              "length": rng.uniform(0.055, 0.105), "tint": rng.randrange(5)})
    return out


# Round 13 (owner's r12 review: "the background is still a blank fog wall ... build depth LAYERS that read through fog
# at graded density: near (kerb, bench, bollards, leaf litter, a tree trunk), mid (tree line, railing, lamp posts, a
# softened building edge or bus), far (faint waterfront / structure silhouettes); near keeps contrast, fog grows with
# distance; not one bold box, darker irregular silhouettes with detail, partly occluded"). Every piece is placed where
# the HOOK camera looks, in the view frame (d along the view past the subject's centre, o across it). Pure. (eng)
LAYER_SEED = 0x1A7E
BOLLARDS = {"d": (4.6, 6.0), "gapM": (1.4, 2.0), "n": (4, 7), "h": (0.78, 0.95), "r": 0.075, "cos": 0.96, "sin": 0.28}
TRUNKS = {"d": (5.5, 9.0), "r": (0.13, 0.22), "h": 7.5, "n": 0}   # round 14 n 2 -> 0: a bare trunk at the frame's
#   edge read as an accidental obstruction (owner's r13 review); the court's own trees carry the near verticals
RAILING = {"d": 21.0, "halfM": 34.0, "postM": 2.1, "h": 1.08, "lean": 1.5}
MID_TREES = {"d": (27.0, 42.0), "halfM": 16.0, "n": 14, "h": (6.0, 11.5), "gap": 0.35}
FAR_BLOCKS = {"d": (50.0, 82.0), "halfM": 26.0, "n": 8, "w": (9.0, 34.0), "dep": (6.0, 14.0),
              "h": ((8.0, 13.0), (13.0, 21.0)), "tall": 0.5}   # round 14 (owner's r13 review: "far buildings barely
#   read - raise their silhouettes above the car's roofline"): nearer (58-92 -> 50-82 m) and taller (6-16 -> 8-21 m),
#   so from a low camera the roofs clear the car and stand against the fog above the mid tree line


def depth_layers(profile, hero, aspect, seed, exclusion, props=(), max_dist=None):
    """{"bollards": [(x, y, h)], "trunks": [(x, y, r, h)], "railing": [(x, y)] post line (or []),
    "midTrees": [(x, y, h, yaw)], "farBlocks": [(x, y, (w, d, h), yaw, tier)]} for the hook frame. Near pieces stand
    beside the subject's outline (never in front of it), clear of the exclusion and the court's props; mid and far
    pieces sit behind it and may pass behind the car (it occludes them, as in v04 f_06). Empty without a hero."""
    from engine.geometry import box_corners, project
    out = {"bollards": [], "trunks": [], "railing": [], "midTrees": [], "farBlocks": []}
    if hero is None:
        return out
    rng = random.Random(seed ^ LAYER_SEED)
    cx, cy = profile.center[0], profile.center[1]
    fx, fy = cx - hero.position[0], cy - hero.position[1]
    n = math.hypot(fx, fy) or 1.0
    fx, fy = fx / n, fy / n
    rx, ry = fy, -fx
    far = max_dist if max_dist is not None else 1e9
    car = [project(hero, c, aspect) for c in box_corners(profile.boundsMin, profile.boundsMax)]
    car = [c for c in car if c[2] > 0]
    x0 = min(c[0] for c in car) if car else 0.0
    x1 = max(c[0] for c in car) if car else 0.0
    e = exclusion
    boxes = [footprint(pr) for pr in props]

    def at(d, o):
        return cx + fx * d + rx * o, cy + fy * d + ry * o

    def free(x, y, pad):
        if e and e[0] - pad <= x <= e[2] + pad and e[1] - pad <= y <= e[3] + pad:
            return False
        return not any(b[0] - pad <= x <= b[2] + pad and b[1] - pad <= y <= b[3] + pad for b in boxes)

    def in_frame(x, y, z, lim=1.0):
        q = project(hero, (x, y, z), aspect)
        return q[2] > 0 and abs(q[0]) < lim and abs(q[1]) < 1.02, q

    # near: a row of bollards receding along the path beside the car, in the strip of frame the car leaves free
    for s_ in sorted((-1.0, 1.0), key=lambda s: -(1.0 - x1) if s > 0 else -(1.0 + x0)):
        lo, hi = (x1 + 0.04, 0.97) if s_ > 0 else (-0.97, x0 - 0.04)
        if hi - lo < 0.04:
            continue
        d0 = BOLLARDS["d"][0]
        o = next((s_ * k * 0.1 for k in range(1, 200)
                  if lo < in_frame(*at(d0, s_ * k * 0.1), 0.5, 2.0)[1][0] < hi), None)
        if o is None:
            continue
        d, row = d0, []
        for _ in range(rng.randint(*BOLLARDS["n"])):
            x, y = at(d, o + rng.gauss(0.0, 0.03))
            ok, q = in_frame(x, y, 0.5)
            if ok and (q[0] < x0 - 0.02 or q[0] > x1 + 0.02) and free(x, y, 0.3):
                row.append((x, y, rng.uniform(*BOLLARDS["h"])))
            g = rng.uniform(*BOLLARDS["gapM"])
            d += g * BOLLARDS["cos"]                     # the path edge runs away at an angle to the view,
            o += s_ * g * BOLLARDS["sin"]                # out toward the frame's edge
        if len(row) >= 2:
            out["bollards"] = row
            break
    # near: a tree trunk or two at the frame's edge (its crown above the frame)
    for _ in range(40):
        if len(out["trunks"]) >= TRUNKS["n"]:
            break
        d = rng.uniform(*TRUNKS["d"])
        o = rng.choice((-1.0, 1.0)) * rng.uniform(3.0, 9.0)
        x, y = at(d, o)
        ok, q = in_frame(x, y, 1.0, 1.05)
        if ok and abs(q[0]) > 0.55 and (q[0] < x0 - 0.05 or q[0] > x1 + 0.05) and free(x, y, 0.6) and \
                all(math.hypot(x - a, y - b) > 3.0 for a, b, *_ in out["trunks"]):
            out["trunks"].append((x, y, rng.uniform(*TRUNKS["r"]), TRUNKS["h"]))
    # mid: a railing straight across the view (the waterfront's edge), a post every postM
    d = RAILING["d"]
    if d < far:
        o = -RAILING["halfM"]
        yaw = rng.uniform(-RAILING["lean"], RAILING["lean"])
        while o <= RAILING["halfM"]:
            x, y = at(d + o * math.tan(math.radians(yaw)), o)
            if math.hypot(x - cx, y - cy) < far:
                out["railing"].append((x, y))
            o += RAILING["postM"]
    # mid: an irregular tree line, clumped, with gaps
    for _ in range(MID_TREES["n"] * 3):
        if len(out["midTrees"]) >= MID_TREES["n"]:
            break
        d = rng.uniform(*MID_TREES["d"])
        o = rng.uniform(-MID_TREES["halfM"], MID_TREES["halfM"])
        if rng.random() < MID_TREES["gap"] and abs(o) < 8.0:
            continue                                     # a gap where the far structures show through
        x, y = at(d, o)
        if math.hypot(x - cx, y - cy) > far:
            continue
        if not in_frame(x, y, 3.0, 1.3)[0]:
            continue
        out["midTrees"].append((x, y, rng.uniform(*MID_TREES["h"]), rng.uniform(0.0, 360.0)))
    # far: structure silhouettes - low sheds / pavilions and a few taller building edges, overlapping in depth
    for _ in range(FAR_BLOCKS["n"] * 4):
        if len(out["farBlocks"]) >= FAR_BLOCKS["n"]:
            break
        d = rng.uniform(*FAR_BLOCKS["d"])
        o = rng.uniform(-FAR_BLOCKS["halfM"], FAR_BLOCKS["halfM"])
        x, y = at(d, o)
        tall = rng.random() < FAR_BLOCKS["tall"]
        w, dep = rng.uniform(*FAR_BLOCKS["w"]), rng.uniform(*FAR_BLOCKS["dep"])
        h = rng.uniform(*FAR_BLOCKS["h"][1 if tall else 0])
        if tall:
            w *= 0.6
        if math.hypot(x - cx, y - cy) + max(w, dep) / 2 > far:
            continue
        if not (in_frame(x, y, h * 0.5, 1.2)[0]):
            continue
        if any(math.hypot(x - b[0], y - b[1]) < 0.5 * (max(w, dep) + max(b[2][:2])) for b in out["farBlocks"]):
            continue
        yaw = math.degrees(math.atan2(ry, rx)) + rng.uniform(-25.0, 25.0)
        out["farBlocks"].append((x, y, (w, dep, h), yaw, "tall" if tall else "low"))
    return out
