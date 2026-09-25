"""Body on springs (TAXONOMY VD-01; METHODS §2.2): a static sag, and after a stop or a landing one or
two damped bounces at the ride frequency. Ride frequency by class: 1.2-1.6 Hz passenger, 1.8-2.0 Hz
sporty, < 0.8 Hz luxury (METHODS VD-01)."""
import math

RIDE_HZ = {"sport": 1.9, "comfort": 1.3, "offroad": 1.1, "toy": 1.3}   # (eng) mid-band per class
PITCH_DEG_PER_G = 1.0   # (eng) METHODS VD-01: 0.5-1.5 deg of pitch per g of braking
G = 9.81


def ride_hz(vehicle_class):
    return RIDE_HZ.get(vehicle_class, RIDE_HZ["comfort"])


def static_sag(radius, sag_frac_r):
    return sag_frac_r * radius


def _wd(hz, zeta):
    w = 2.0 * math.pi * hz
    return w, w * math.sqrt(1.0 - zeta * zeta)


def pitch_after_stop(t, decel_ms2, hz, zeta):
    """Body pitch (radians, nose down positive) from the moment the car stops: the braking dive is
    released into damped bounces."""
    if t < 0:
        return 0.0
    w, wd = _wd(hz, zeta)
    return math.radians(PITCH_DEG_PER_G * decel_ms2 / G) * math.exp(-zeta * w * t) * math.cos(wd * t)


def heave_after_landing(t, impact_ms, hz, zeta, max_m):
    """Body heave (metres, down negative) after the wheels touch down, capped at max_m travel."""
    if t <= 0:
        return 0.0
    w, wd = _wd(hz, zeta)
    return -min(max_m, impact_ms / w) * math.exp(-zeta * w * t) * math.sin(wd * t)
