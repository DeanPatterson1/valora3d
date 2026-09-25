"""Loaded tyre: a flat contact patch and a sidewall bulge (TAXONOMY CD-02; METHODS §2.1 M-GND).

The whole vehicle drops by the tyre deflection d; tyre-band points below the ground are clamped onto
it (the flat patch), and points low on the sidewall move out along the axle. Chord geometry: a
circle of radius r cut d below its lowest point leaves a flat chord L = 2 sqrt(2 r d - d^2), so
d = L^2 / (8 r) for small d. Car tyres: L 0.12-0.18 m, d 2-3.5% of r (METHODS)."""
import math

BULGE_FALLOFF = 0.3   # the bulge fades to zero 0.3 r above the patch (eng; METHODS CD-02)


def deflection(radius, patch_len_frac):
    if radius <= 0:
        return 0.0
    length = patch_len_frac * radius
    return length * length / (8.0 * radius)


PREFLAT_FRAC = 0.6   # a modelled flat bottom >= 60% of the target patch is already a loaded tyre (eng)
PREFLAT_TOL_M = 0.0005   # its bottom: vertices within 0.5 mm of the lowest point (= realism_probe FLAT_TOL_M)


def preflattened(flat_len, radius, patch_len_frac):
    """The model's own tyre already has a contact patch (a scan or a sculpted loaded tyre)."""
    return flat_len >= PREFLAT_FRAC * patch_len_frac * radius


MAX_WHEEL_DROP_FRAC = 0.1   # a tyre modelled up to 0.1 r above the ground is a modelling offset (eng)


def wheel_drop(bottom_z, radius):
    """How far one wheel's unsprung pieces move down so its tyre meets z = 0 before the patch forms.
    Source models can leave a wheel a few mm up (sports_car's rears: 15 mm); a wheel higher than
    MAX_WHEEL_DROP_FRAC r is lifted on purpose and left alone."""
    return bottom_z if DROP_EPS_M < bottom_z <= MAX_WHEEL_DROP_FRAC * radius else 0.0


DROP_EPS_M = 1e-4   # 0.1 mm: below this a wheel touches (float noise of the placement, e.g. 3e-8 m)


MAX_SINGLE_DROP_M = 0.02      # a lone wheel moves down at most 20 mm ...
MAX_SINGLE_DROP_FRAC = 0.05   # ... and at most 0.05 r (review fix 4; eng)
AXLE_GAP_FRAC = 0.5           # wheels closer than 0.5 r along the car share an axle (eng)


def _axles(wheels, fwd):
    """Wheel indices grouped into axles along the forward axis, front-to-back order irrelevant."""
    r = sorted(w["radius"] for w in wheels)[len(wheels) // 2]
    at = sorted(range(len(wheels)), key=lambda i: sum(a * b for a, b in zip(wheels[i]["center"], fwd)))
    groups, last = [], None
    for i in at:
        f = sum(a * b for a, b in zip(wheels[i]["center"], fwd))
        if last is None or f - last > AXLE_GAP_FRAC * r:
            groups.append([])
        groups[-1].append(i)
        last = f
    return groups


def axle_plan(wheels, bottoms, fwd):
    """How a vehicle whose source model leaves wheels off the ground comes down onto it (placed space).
    A whole floating axle (every wheel on it up by wheel_drop) turns the car rigidly about the grounded
    axle's contact line (tilt: pivot, axis, angle; the body goes with it, the wheels stay in their arches).
    Only what is left per wheel after that moves a single wheel down, capped at
    min(MAX_SINGLE_DROP_M, MAX_SINGLE_DROP_FRAC r). Two-axle vehicles tilt; others drop per wheel."""
    drops = [wheel_drop(b, w["radius"]) for b, w in zip(bottoms, wheels)]
    tilt = None
    axles = _axles(wheels, fwd) if wheels else []
    if len(axles) == 2:
        lift = [min(drops[i] for i in a) for a in axles]
        if (lift[0] > 0.0) != (lift[1] > 0.0):
            g, fl = (0, 1) if lift[0] == 0.0 else (1, 0)
            mean = lambda a, k: sum(wheels[i]["center"][k] for i in axles[a]) / len(axles[a])
            pivot = (mean(g, 0), mean(g, 1), 0.0)
            ux, uy = mean(fl, 0) - pivot[0], mean(fl, 1) - pivot[1]
            span = math.hypot(ux, uy)
            if span > 0.0:
                ux, uy = ux / span, uy / span
                tilt = {"pivot": pivot, "axis": (-uy, ux, 0.0), "angle": math.asin(min(1.0, lift[fl] / span))}
                for i in axles[fl]:
                    drops[i] -= lift[fl]
    cap = [min(MAX_SINGLE_DROP_M, MAX_SINGLE_DROP_FRAC * w["radius"]) for w in wheels]
    return {"tilt": tilt, "drops": [min(d, c) if d > DROP_EPS_M else 0.0 for d, c in zip(drops, cap)]}


def tilt_point(p, tilt):
    """p turned about tilt["axis"] (unit, horizontal) through tilt["pivot"] by tilt["angle"] (Rodrigues)."""
    k, th, c0 = tilt["axis"], tilt["angle"], tilt["pivot"]
    v = [a - b for a, b in zip(p, c0)]
    kv = (k[1] * v[2] - k[2] * v[1], k[2] * v[0] - k[0] * v[2], k[0] * v[1] - k[1] * v[0])
    kdv = sum(a * b for a, b in zip(k, v))
    c, s = math.cos(th), math.sin(th)
    return tuple(o + vi * c + kvi * s + ki * kdv * (1 - c) for o, vi, kvi, ki in zip(c0, v, kv, k))


def patch_length(radius, d):
    return 2.0 * math.sqrt(max(0.0, 2.0 * radius * d - d * d))


def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def deform(z, axial, ground, d, radius, half_width, bulge_frac):
    """(z', axial') of one tyre-band point in placed space. axial = signed offset from the tyre's
    mid-plane along the axle. The Blender deformer (tyre_contact/build.py) is this function in nodes."""
    z2 = max(z, ground)
    k = bulge_frac * d * (1.0 - smoothstep(0.0, BULGE_FALLOFF * radius, z2 - ground))
    side = min(1.0, abs(axial) / half_width) if half_width > 0 else 0.0
    return z2, (axial + math.copysign(k * side, axial)) if axial else axial
