"""Pure maths for the drive couplings tyre_spray and dust_kick (phase 6 Task 106). Particles leave the rolling
tyres of a driving subject: the contact points (profile.wheels[].contact) are carried through the drive's own
pose function (engine/motion_path.pose_fn), so a particle is born exactly where that tyre is at its birth time,
with the car's velocity measured from the same pose function (a central difference).

A tyre's tread leaves the road at rest and lifts round the back of the wheel: a particle released at an angle phi
past the contact has, in the world, v_car (1 - cos phi) along the car and |v_car| sin phi up (the rooster tail);
the side sheet leaves the contact sideways. Rates scale with speed above SPEED_MIN_MS (the checker's >= 15 km/h
coupling threshold, applied here as a smooth ramp so a car pulling away starts spraying gradually).

Three populations per block: `grain` (real-size droplets 1-4 mm / grit 0.2-1 mm, rendered as points), `fine`
(the mist itself: many sub-millimetre droplets / dust motes, rendered as real-size points so the camera's shutter
smears them into streaks and haze the way it smears real spray) and `puff` (the soft billow, a few cm, rendered as
a noise-broken volume by Points to Volume). Each particle carries its own drag `k` (1/s) and gravity share `fall`:
a fine droplet is carried by the air it is thrown into, a grain flies ballistic, a puff barely falls.
Hero pass (2026-09-28): the lane clips showed the mist as round blobs (a few large puffs, each a uniform sphere)
and the grains at a 540p size floor; the fine population carries the mist now, the puffs are smaller, softer
and noise-broken. All numbers (eng) until G6 (v04)."""
import math

from engine.motion_path import apply, pose_fn

G = 9.81
SPEED_MIN_MS = 15 / 3.6        # 15 km/h: the coupling threshold (plan T106)
SPEED_FULL_MS = 30 / 3.6       # full rate from 30 km/h
FD_S = 1.0 / 240               # central-difference step of the car velocity

# rates are per wheel per m/s of speed; drag k in 1/s toward the air; fall = the share of g a particle feels
# (a 0.3 mm droplet's terminal speed is ~1 m/s: it hangs in the wake; a puff is air)
SPRAY = {"grainRate": 110.0, "fineRate": 400.0, "puffRate": 20.0,
         "grainSizeM": (0.001, 0.004), "fineSizeM": (0.0002, 0.0007), "puffSizeM": (0.03, 0.08),
         "grainLifeS": (0.5, 1.1), "fineLifeS": (0.6, 1.5), "puffLifeS": (0.8, 1.8),
         "phiDeg": (6.0, 30.0), "lift": (0.4, 0.8), "fineLift": (0.25, 0.6), "fineSpread": 0.12,
         "front": 0.35, "side": 0.1, "drag": 1.4, "fineDrag": 6.0, "puffDrag": 3.5,
         "fall": 1.0, "fineFall": 0.35, "puffFall": 0.15}
DUST = {"grainRate": 80.0, "fineRate": 700.0, "puffRate": 40.0,
        "grainSizeM": (0.0002, 0.001), "fineSizeM": (0.00008, 0.0003), "puffSizeM": (0.08, 0.2),
        "grainLifeS": (0.4, 0.9), "fineLifeS": (1.2, 2.8), "puffLifeS": (1.6, 3.2),
        "phiDeg": (10.0, 40.0), "lift": (0.3, 0.6), "fineLift": (0.25, 0.7), "fineSpread": 0.3,
        "front": 0.5, "side": 0.15, "drag": 2.0, "fineDrag": 3.0, "puffDrag": 2.5,
        "fall": 1.0, "fineFall": 0.08, "puffFall": 0.15}
POPS = ("grain", "fine", "puff")
# The wheel arch catches what the tread throws steeply: only droplets released low behind the contact escape
# (hero pass 2026-09-28: phi up to 55 deg and full lift sent spray up through the rear wing, 3 m high at 45 km/h).
FINE_PHI_DEG = 40.0
MAX_PER_BLOCK = 600_000


def speed_ramp(speed):
    """0 below SPEED_MIN_MS, 1 from SPEED_FULL_MS, smoothstep between."""
    x = min(1.0, max(0.0, (speed - SPEED_MIN_MS) / (SPEED_FULL_MS - SPEED_MIN_MS)))
    return x * x * (3 - 2 * x)


def _sub(a, b):
    return tuple(p - q for p, q in zip(a, b))


def _unit(v):
    m = math.sqrt(sum(c * c for c in v))
    return tuple(c / m for c in v) if m > 1e-9 else (0.0, 0.0, 0.0)


def wheel_state(pose_at, profile, wheel, t):
    """(world contact point, car velocity at that contact) at script time t."""
    c = wheel["contact"]
    p = apply(c, pose_at(t), profile)
    a, b = apply(c, pose_at(t + FD_S), profile), apply(c, pose_at(t - FD_S), profile)
    return p, tuple((x - y) / (2 * FD_S) for x, y in zip(a, b))


def particles(kind, params, script, profile, catalog, first, last, fps, rng, cap=MAX_PER_BLOCK):
    """Seeded particles of tyre_spray (kind "spray") or dust_kick ("dust") for render frames [first, last]:
    per frame and wheel, round(rate x ramp(speed) x density / fps) grains and puffs, where rate is per m/s of
    speed. A wheel trailing the car's motion is a rear wheel (full rate); leading wheels emit `front` x."""
    k = SPRAY if kind == "spray" else DUST
    dens = float(params.get("density", 1.0))
    pose_at = pose_fn(script, profile, catalog)
    wheels = [w for w in (profile.wheels or []) if w.get("contact")]
    out, carry = [], {}
    for f in range(int(first), int(last) + 1):
        t = (f - 1) / fps
        states = [wheel_state(pose_at, profile, w, t) for w in wheels]
        if not states:
            break
        vcar = tuple(sum(s[1][i] for s in states) / len(states) for i in range(3))
        speed = math.sqrt(sum(c * c for c in vcar))
        ramp = speed_ramp(speed)
        if ramp <= 0:
            continue
        fwd = _unit(vcar)
        side_ax = _unit((fwd[1], -fwd[0], 0.0))
        mid = sum(sum(a * b for a, b in zip(s[0], fwd)) for s in states) / len(states)
        for wi, (w, (p, _)) in enumerate(zip(wheels, states)):
            rear = sum(a * b for a, b in zip(p, fwd)) < mid
            share = 1.0 if rear else k["front"]
            r, width = float(w.get("radius", 0.3)), float(w.get("width", 0.2))
            lat = 1.0 if sum(a * b for a, b in zip(_sub(p, (profile.center[0], profile.center[1], 0)), side_ax)) > 0 else -1.0
            for pop in POPS:
                n_f = k[f"{pop}Rate"] * speed * ramp * dens * share / fps + carry.get((wi, pop), 0.0)
                n = int(n_f)
                carry[(wi, pop)] = n_f - n
                for _ in range(n):
                    if len(out) >= cap:
                        return out
                    out.append(_one(k, pop, p, fwd, side_ax, lat, speed, vcar, r, width, f, rng))
    return out


def _one(k, pop, p, fwd, side_ax, lat, speed, vcar, r, width, f, rng):
    birth = f - 1 + rng.random()
    if pop == "fine":
        return _fine(k, p, fwd, side_ax, lat, speed, vcar, r, width, birth, rng)
    across = (rng.random() - 0.5) * width
    if rng.random() < k["side"]:                      # the side sheet: out of the contact, sideways
        pos = tuple(p[i] + side_ax[i] * lat * (0.5 * width) + fwd[i] * (rng.random() - 0.5) * r for i in range(2)) + (0.02,)
        out_s, up_s = speed * (0.15 + 0.2 * rng.random()), speed * (0.05 + 0.15 * rng.random())
        vel = tuple(vcar[i] * 0.5 + side_ax[i] * lat * out_s for i in range(2)) + (up_s,)
    else:                                              # the rooster tail: round the back of the tyre
        phi = math.radians(k["phiDeg"][0] + (k["phiDeg"][1] - k["phiDeg"][0]) * rng.random())
        pos = tuple(p[i] - fwd[i] * r * math.sin(phi) + side_ax[i] * across for i in range(2)) + (r * (1 - math.cos(phi)),)
        lift = k["lift"][0] + (k["lift"][1] - k["lift"][0]) * rng.random()
        spread = 0.08 * speed * (rng.random() - 0.5)
        vel = tuple(vcar[i] * (1 - math.cos(phi)) + side_ax[i] * spread for i in range(2)) + (speed * math.sin(phi) * lift,)
    return _pack(k, pop, birth, pos, vel, rng)


def _pack(k, pop, birth, pos, vel, rng):
    lo, hi = k[f"{pop}SizeM"]
    llo, lhi = k[f"{pop}LifeS"]
    pre = "" if pop == "grain" else pop
    return {"birth": birth, "pos": pos, "vel": vel, "size": lo + (hi - lo) * rng.random(),
            "life": llo + (lhi - llo) * rng.random(), "puff": 1.0 if pop == "puff" else 0.0,
            "fine": 1.0 if pop == "fine" else 0.0,
            "k": k[f"{pre}Drag" if pre else "drag"], "fall": k[f"{pre}Fall" if pre else "fall"]}


def _fine(k, p, fwd, side_ax, lat, speed, vcar, r, width, birth, rng):
    """A mist droplet / dust mote: torn off the back of the tyre below the wheel arch (phi 0-FINE_PHI_DEG) and the
    tread's width, thrown slower and wider than a grain (it is the spray's cloud, not its jet)."""
    phi = math.radians(FINE_PHI_DEG * rng.random())
    across = (rng.random() - 0.5) * width * 1.4
    pos = tuple(p[i] - fwd[i] * r * math.sin(phi) + side_ax[i] * across for i in range(2)) + (r * (1 - math.cos(phi)),)
    lift = k["fineLift"][0] + (k["fineLift"][1] - k["fineLift"][0]) * rng.random()
    spread = k["fineSpread"] * speed * (rng.random() - 0.5)
    out = 0.03 * speed * rng.random() * lat                  # the tyre's side wall flings a little outward
    vel = tuple(vcar[i] * (1 - math.cos(phi)) * (0.6 + 0.4 * rng.random()) + side_ax[i] * (spread + out)
                for i in range(2)) + (speed * max(math.sin(phi), 0.15) * lift,)
    return _pack(k, "fine", birth, pos, vel, rng)
