"""Overshoot-and-settle after a stop, squash-and-recover after a landing (TAXONOMY SF-05, RB-01, CD-04;
products.md P-M01 "2 f damped landing shake"). A damped oscillator whose 2% settling time is settle_s."""
import math

ZETA = 0.5   # (eng) one visible overshoot, then still


def _w(settle_s, zeta):
    return 4.0 / (zeta * settle_s)


def _peak(zeta):
    """Peak of e^(-zeta w t) sin(w_d t) (independent of w)."""
    s = math.sqrt(1.0 - zeta * zeta)
    phase = math.atan2(s, zeta)
    return math.exp(-zeta * phase / s) * math.sin(phase)


def overshoot(t, amp, settle_s, zeta=ZETA):
    """Displacement past the rest pose after a stop: 0 at t = 0, one overshoot of `amp`, still by settle_s."""
    if t <= 0:
        return 0.0
    w = _w(settle_s, zeta)
    wd = w * math.sqrt(1.0 - zeta * zeta)
    return amp * math.exp(-zeta * w * t) * math.sin(wd * t) / _peak(zeta)


def squash_z(t, squash, settle_s, zeta=ZETA):
    """Scale along the contact normal after a landing: `squash` at impact, one small rebound, then 1."""
    if squash >= 1.0 or t < 0:
        return 1.0
    w = _w(settle_s, zeta)
    wd = w * math.sqrt(1.0 - zeta * zeta)
    return 1.0 - (1.0 - squash) * math.exp(-zeta * w * t) * math.cos(wd * t)


def squash_xy(sz):
    """Sideways scale that keeps the volume: sx * sy * sz = 1."""
    return 1.0 / math.sqrt(sz)
