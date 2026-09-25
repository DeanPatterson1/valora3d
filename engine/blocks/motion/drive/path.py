"""drive (hand-off H5): a wheeled subject drives along a path with a speed profile, inside the window
[startS, startS + driveS] (it waits before and holds after: 40 km/h x 4 s = 44 m, review amendment 79).

- Heading comes from the path TANGENT, never from the sign of ingest forwardAxis (H5): the long axis follows
  the tangent. Which end leads is nose_sign(profile) (engine/physics/shape), unless facing overrides it.
- path: straight | arc_left | arc_right | s_curve (heading 0 -> back to 0, curvature k_max sin) | stop (a
  straight that brakes to a stop). Curvature k = 1 / R, R = max(ARC_WB_K x wheelbase, v^2 / (A_LAT_G g)), so
  a fast arc is a wide one.
- accel: cruise (constant) | launch (0 -> v at LAUNCH_G) | brake_to_stop (v -> 0 at BRAKE_G, stopping at the
  window end). A pass-by (cruise, launch) is centred: mid-window the subject is on its mark; a stop ends on it.
- The pose turns about the trailing axle (pivot()): the unsteered wheels roll clean, the leading ones scrub
  (reported as wheel_scrub) until front-wheel steering exists.
- Pitch and roll come from the suspension realism block, never from this path."""
import math

from engine.motion_path import SubjectPose
from engine.physics.shape import _axis_index, nose_sign

G = 9.81
ARC_WB_K = 3.0         # (eng) arc radius >= 3 x wheelbase
A_LAT_G = 0.4          # (eng) arcs are wide enough to stay under 0.4 g lateral
LAUNCH_G, BRAKE_G = 0.3, 0.6   # (eng) launch and braking accelerations
S_STEPS = 400          # numeric integration steps along an s_curve


def _v(params):
    return params["speedKmh"] / 3.6


def forward(params, profile):
    """Placed-space unit vector the subject travels along at its mark."""
    veh = getattr(profile, "vehicle", None) or {}
    ax = veh.get("forwardAxis", [0.0, 1.0, 0.0])
    i, sign = _axis_index(ax)
    facing = params.get("facing", "auto")
    lead = nose_sign(profile)[0] if facing == "auto" else (sign if facing == "forward" else -sign)
    f = [0.0, 0.0, 0.0]
    f[i] = float(lead)
    return f[0], f[1]


def wheelbase(profile):
    veh = getattr(profile, "vehicle", None) or {}
    if veh.get("wheelbaseM"):
        return float(veh["wheelbaseM"])
    ws = [w["center"] for w in (profile.wheels or []) if w.get("center")]
    i, _ = _axis_index(veh.get("forwardAxis", [0.0, 1.0, 0.0]))
    if len(ws) >= 2:
        span = max(c[i] for c in ws) - min(c[i] for c in ws)
        if span > 0:
            return span
    return 0.6 * profile.longest


def radius(params, profile):
    return max(ARC_WB_K * wheelbase(profile), _v(params) ** 2 / (A_LAT_G * G))


def _accel(params):
    return "brake_to_stop" if params.get("path") == "stop" else params.get("accel", "cruise")


def _phases(params):
    """(v0, brake start u, launch end u) in window time u = t - startS."""
    v, T, acc = _v(params), params["driveS"], _accel(params)
    if acc == "brake_to_stop":
        v0 = min(v, BRAKE_G * G * T)
        return v0, T - v0 / (BRAKE_G * G), None
    if acc == "launch":
        return v, None, v / (LAUNCH_G * G)
    return v, None, None


def travelled(params, u):
    """Metres along the path after window time u (clamped to the window)."""
    T = params["driveS"]
    u = min(max(u, 0.0), T)
    v0, brake, launch = _phases(params)
    if brake is not None:
        a = BRAKE_G * G
        if u <= brake:
            return v0 * u
        w = u - brake
        return v0 * brake + v0 * w - 0.5 * a * w * w
    if launch is not None:
        a = LAUNCH_G * G
        if u <= launch:
            return 0.5 * a * u * u
        return 0.5 * a * launch * launch + v0 * (u - launch)
    return v0 * u


def speed(params, u):
    T = params["driveS"]
    if u < 0 or u > T:
        return 0.0
    v0, brake, launch = _phases(params)
    if brake is not None:
        return v0 if u <= brake else max(0.0, v0 - BRAKE_G * G * (u - brake))
    if launch is not None:
        return min(v0, LAUNCH_G * G * u)
    return v0


def lane_distance(params, profile):
    """Metres driven in the window (vehicle_speed_cap compares it with the world's driveLaneM)."""
    return travelled(params, params["driveS"])


def curvature(params, profile, s):
    path, k = params.get("path", "straight"), 1.0 / radius(params, profile)
    if path == "arc_left":
        return k
    if path == "arc_right":
        return -k
    if path == "s_curve":
        L = max(lane_distance(params, profile), 1e-6)
        return k * math.sin(2.0 * math.pi * s / L)
    return 0.0


def heading(params, profile, s):
    """Turn of the tangent (rad) after s metres (0 at the start of the path)."""
    path, k = params.get("path", "straight"), 1.0 / radius(params, profile)
    if path == "arc_left":
        return k * s
    if path == "arc_right":
        return -k * s
    if path == "s_curve":
        L = max(lane_distance(params, profile), 1e-6)
        return k * L / (2.0 * math.pi) * (1.0 - math.cos(2.0 * math.pi * s / L))
    return 0.0


def _xy(params, profile, s):
    """Path point after s metres, start at the origin, initial tangent +x (before turning onto the mark)."""
    path, k = params.get("path", "straight"), 1.0 / radius(params, profile)
    if path in ("arc_left", "arc_right"):
        sg = 1.0 if path == "arc_left" else -1.0
        return math.sin(k * s) / k, sg * (1.0 - math.cos(k * s)) / k
    if path == "s_curve":
        n = max(8, int(S_STEPS * s / max(lane_distance(params, profile), 1e-6)))
        h = s / n
        x = y = 0.0
        for j in range(n):                            # midpoint rule on the heading
            a = heading(params, profile, (j + 0.5) * h)
            x, y = x + h * math.cos(a), y + h * math.sin(a)
        return x, y
    return s, 0.0


def pivot(params, profile):
    """The trailing axle midpoint (placed, z = 0): the bicycle model turns the car about its unsteered axle, so
    those wheels roll without scrub; the leading ones scrub until front-wheel steering exists (phase 6). None
    (the ground-centre pivot) without wheels."""
    ws = [w["center"] for w in (profile.wheels or []) if w.get("center")]
    if not ws:
        return None
    fx, fy = forward(params, profile)
    along = [c[0] * fx + c[1] * fy for c in ws]
    lo = min(along)
    rear = [c for c, a in zip(ws, along) if a <= lo + 0.25 * wheelbase(profile)]
    return (sum(c[0] for c in rear) / len(rear), sum(c[1] for c in rear) / len(rear), 0.0)


def mark_s(params, profile):
    """Metres along the path where the subject is on its mark (its placed pose)."""
    if _accel(params) == "brake_to_stop":
        return lane_distance(params, profile)
    return travelled(params, params["driveS"] / 2.0)


def rest_s(params, profile, duration):
    return params["startS"] + params["driveS"]


def sample(params, profile, t, duration):
    s = travelled(params, t - params["startS"])
    s0 = mark_s(params, profile)
    fx, fy = forward(params, profile)
    base = math.atan2(fy, fx) - heading(params, profile, s0)   # rotate the path so the mark faces forward
    x, y = _xy(params, profile, s)
    x0, y0 = _xy(params, profile, s0)
    dx, dy = x - x0, y - y0
    c, sn = math.cos(base), math.sin(base)
    return SubjectPose(offset=(c * dx - sn * dy, sn * dx + c * dy, 0.0),
                       yaw=heading(params, profile, s) - heading(params, profile, s0), pivot=pivot(params, profile))


def still(params):
    return False


def flags(params):
    return {"translates": True, "stops": _accel(params) == "brake_to_stop"}
