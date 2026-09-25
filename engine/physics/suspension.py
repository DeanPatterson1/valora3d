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


MAX_DECEL_G = 1.2       # (eng) road-tyre braking limit; a motion track can report far more (a teleport)
DIVE_RAMP_S = 0.25      # (eng) the braking dive builds over the last 0.25 s before the stop (= events.DECEL_WINDOW_S)
MAX_ZETA = 0.95         # (eng) keeps the damped form defined; >= 1 would be critically / over damped


def _wd(hz, zeta):
    z = min(zeta, MAX_ZETA)
    w = 2.0 * math.pi * hz
    return w, w * math.sqrt(1.0 - z * z), z


SETTLE_DECAY = 1000.0   # keys run until the bounce envelope e^(-z w t) is 1/1000 of its start


def settle_window_s(hz, zeta):
    """How long after an event the damped response needs keys: ln(1000) / (z w). A fixed window cut a soft,
    lightly damped car mid-bounce (review fix 5); the response past this is below 0.1% of its start."""
    w, _, z = _wd(hz, zeta)
    return math.log(SETTLE_DECAY) / (z * w) if z > 0 else float("inf")


def pitch_after_stop(t, decel_ms2, hz, zeta):
    """Body pitch (radians, nose down positive) around a stop at t = 0: the braking dive builds over
    DIVE_RAMP_S before it (smoothstep), then is released as the free response of a damped spring from
    rest at the dive angle, e^(-z w t) (cos w_d t + z / sqrt(1 - z^2) sin w_d t): no step, no kink."""
    p0 = math.radians(PITCH_DEG_PER_G * min(decel_ms2, MAX_DECEL_G * G) / G)
    if t < 0:
        x = max(0.0, 1.0 + t / DIVE_RAMP_S)
        return p0 * x * x * (3.0 - 2.0 * x)
    w, wd, z = _wd(hz, zeta)
    return p0 * math.exp(-z * w * t) * (math.cos(wd * t) + z / math.sqrt(1.0 - z * z) * math.sin(wd * t))


def heave_after_landing(t, impact_ms, hz, zeta, max_m):
    """Body heave (metres, down negative) after the wheels touch down, capped at max_m travel."""
    if t <= 0:
        return 0.0
    w, wd, z = _wd(hz, zeta)
    return -min(max_m, impact_ms / w) * math.exp(-z * w * t) * math.sin(wd * t)
