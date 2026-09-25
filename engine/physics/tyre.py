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
    return bottom_z if 0.0 < bottom_z <= MAX_WHEEL_DROP_FRAC * radius else 0.0


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
