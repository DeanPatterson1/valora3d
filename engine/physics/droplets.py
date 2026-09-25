"""Droplets and drips on the subject (plan Task 66; render-studio rain_atmosphere.drips generalised). Pure.

Beads (FL-03): real-size flattened hemispheres (sizeMm across) scattered on the subject's surface where it
faces up (zone up_facing: estimated normal n.up > shape.UP_DOT) or anywhere (zone all), covering COVER x
density of that surface (eng). Drips (FL-20): emitters on the subject's low edges (shape.low_edges); each
swells for HANG_FRAC of its seeded period, lets go and falls under gravity until the ground (z = 0), where it
is gone until the next cycle. The lifecycle is a function of time alone (METHODS R1)."""
import math
import random

from engine.physics import shape

G = 9.81
HANG_FRAC = 0.4        # render-studio: a drop hangs for 40% of its period
SWELL_EXP = 0.6        # render-studio: fills fast, then hangs
COVER = 0.25           # (eng) share of the selected surface the beads cover at density 1
MAX_BEADS = 30000      # (eng) instance cap, by cost
MAX_DRIPS = 40         # (eng) drip emitters at density 1
PERIOD_S = (1.2, 3.4)  # (eng) render-studio period range at car scale (hang + fall + ring always fit)


def fall_time(h):
    return math.sqrt(2.0 * max(h, 0.0) / G)


def drip_state(t, period, phase, h):
    """(state, size 0..1, drop metres below the emitter): swell -> fall -> gone, one cycle per period."""
    since = ((t / period + phase) % 1.0) * period
    hang = HANG_FRAC * period
    if since < hang:
        return "swell", (since / hang) ** SWELL_EXP, 0.0
    fall = since - hang
    drop = 0.5 * G * fall * fall
    if drop < h:
        return "fall", 1.0, drop
    return "gone", 0.0, h


def zone_samples(profile, zone):
    ss = shape.samples(profile)
    return shape.up_facing(ss) if zone == "up_facing" else list(ss)


def bead_density(size_mm, density):
    """Beads per m2 of selected surface: COVER x density of it, each a disc of diameter sizeMm."""
    r = size_mm / 2000.0
    return COVER * density / (math.pi * r * r)


def drip_emitters(profile, density, seed):
    """[(placed point, period, phase)] on the low edges, seeded; at most MAX_DRIPS x density, highest first."""
    edges = sorted(shape.low_edges(shape.samples(profile)), key=lambda s: -s["p"][2])
    n = min(len(edges), int(round(MAX_DRIPS * density)))
    rng = random.Random(seed)
    pick = sorted(rng.sample(range(len(edges)), n)) if n else []
    lo, hi = PERIOD_S
    return [(list(edges[i]["p"]), rng.uniform(lo, hi) + fall_time(edges[i]["p"][2]), rng.random()) for i in pick]
