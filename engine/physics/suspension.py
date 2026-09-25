"""Body on springs (TAXONOMY VD-01; METHODS §2.2): a static sag, and after a stop or a landing one or
two damped bounces at the ride frequency. Ride frequency by class: 1.2-1.6 Hz passenger, 1.8-2.0 Hz
sporty, < 0.8 Hz luxury (METHODS VD-01)."""
import math

RIDE_HZ = {"sport": 1.9, "comfort": 1.3, "offroad": 1.1, "toy": 1.3}   # (eng) mid-band per class
ROLL_DEG_PER_G = {"sport": 2.0, "comfort": 5.0, "offroad": 6.0, "toy": 0.0}   # (eng) METHODS VD-04/05 body roll
ROLL_LAG_S = 0.15       # (eng) first-order lag of the body roll behind the lateral acceleration
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


def roll_deg_per_g(vehicle_class):
    return ROLL_DEG_PER_G.get(vehicle_class, ROLL_DEG_PER_G["comfort"])


def lateral_g(pos, yaws, fps, forward, shots=None):
    """Signed lateral acceleration per frame in g, from the motion track: a = v x yaw rate, positive when the
    car turns to ITS left (so the body leans right). forward: the placed forward axis; a car that reverses
    through a turn leans the other way. shots (motion_path.frame_shots): each take on its own, never
    differentiated across a cut."""
    if shots is not None:
        from engine.physics.events import takes
        return [a for i0, i1 in takes(shots, len(pos)) for a in lateral_g(pos[i0:i1], yaws[i0:i1], fps, forward)]
    out = [0.0] * len(pos)
    for i in range(1, len(pos) - 1):
        vx, vy = (pos[i + 1][0] - pos[i - 1][0]) * fps / 2, (pos[i + 1][1] - pos[i - 1][1]) * fps / 2
        rate = (yaws[i + 1] - yaws[i - 1]) * fps / 2
        c, s = math.cos(yaws[i]), math.sin(yaws[i])
        fx, fy = c * forward[0] - s * forward[1], s * forward[0] + c * forward[1]
        ahead = 1.0 if vx * fx + vy * fy >= 0 else -1.0
        out[i] = ahead * math.hypot(vx, vy) * rate / G
    if len(out) > 1:
        out[0], out[-1] = out[1], out[-2]
    return out


def body_roll(a_lat_g, deg_per_g, fps, lag_s=ROLL_LAG_S, shots=None):
    """Body roll per frame (radians, positive = the car's right side down: it leans OUT of a left turn),
    rollDegPerG x a_lat, lagged first-order by lag_s. shots: the lag restarts from level with every take."""
    if shots is not None:
        from engine.physics.events import takes
        return [r for i0, i1 in takes(shots, len(a_lat_g)) for r in body_roll(a_lat_g[i0:i1], deg_per_g, fps, lag_s)]
    k = 1.0 - math.exp(-1.0 / (fps * lag_s)) if lag_s > 0 else 1.0
    out, r = [], 0.0
    for a in a_lat_g:
        r += k * (math.radians(deg_per_g * a) - r)
        out.append(r)
    return out
