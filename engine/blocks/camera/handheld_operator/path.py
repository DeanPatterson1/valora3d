"""handheld_operator (phase 5 Task 82): a person walking a shot with a lightly stabilised camera.

Port of render-studio film_camera._operate (ModVision tools/render-studio/film_camera.py ~:180-334), made
PURE: the source integrates a body, arm springs and seeded footfalls step by step; here every term is a
closed-form function of (noiseSeed, seconds), so replay and farm splits are exact (no stateful filter).
Ported: _wander's incommensurate-sine drift + tremor (film_camera ~:88, normalised to |w| <= 1), footfall
bob at a seeded step rate, sway, and an aim that lags the body (the aim reads the noise AIM_LAG_S late).
Not ported: the five car-specific shots and their mesh-name anchors, reframing corrections, pauses.

- Base path at distance x radius, height heightFrac x height, eased (easing, settleFrac): walk_arc sweeps
  arcDeg of azimuth, walk_in pushes in pushFrac, stand holds.
- Footfall bob (walking only): (4 + 8 x shake) mm x radius (METHODS R5) at step_hz in 1.6-2.0 Hz.
- Sway: translation <= 0.02 x radius x shake (R5); aim and roll <= 1.5 deg x shake (rotation clamped).
Seconds come from ctx (engine/camera_context: the shot length), else DEFAULT_SHOT_S. noiseSeed is a number
rounded here (review amendment 82: no int param type); layer 1 varies it (Task 89)."""
import math

from engine.camera_context import DEFAULT_SHOT_S
from engine.easing import ease, settle
from engine.geometry import Pose, _basis

MIN_HEIGHT_M = 0.03
BOB_M = (0.004, 0.012)      # (eng) footfall bob at shake 0 / 1, x radius (R5)
STEP_HZ = (1.6, 2.0)        # (eng) walking step rate band
TRANS_M = 0.02              # (eng) sway translation at shake 1, x radius (R5)
ROT_DEG = 1.5               # (eng) aim / roll wander at shake 1 (clamped, not scaled)
AIM_LAG_S = 0.15            # (eng) the aim follows the body this late
ROLL_SHARE = 0.6            # (eng) roll wanders less than the aim


def _seed(params):
    return int(round(params["noiseSeed"]))


def _frac(x):
    return x - math.floor(x)


def wander(seed, t, slow=1.0, fast=0.12):
    """film_camera._wander (smooth drift + faint tremor, sums of incommensurate sines), normalised to [-1, 1]."""
    a = seed * 12.9898
    drift = (math.sin(t * 1.45 + a) + .6 * math.sin(t * 2.61 + a * 1.7) + .35 * math.sin(t * 4.83 + a * 2.3)) / 1.95
    rig = (math.sin(t * 19.5 + a * 3.1) + .7 * math.sin(t * 33.3 + a * .7) + .5 * math.sin(t * 42.1 + a * 1.3)) / 2.2
    return (slow * drift + fast * rig) / (slow + fast)


def step_hz(params):
    """The operator's step rate: a pure function of noiseSeed inside STEP_HZ."""
    return STEP_HZ[0] + (STEP_HZ[1] - STEP_HZ[0]) * _frac(math.sin(_seed(params) * 78.233 + 0.5) * 43758.5453)


def bob_m(params, profile, t):
    """Vertical footfall bob (metres) at t seconds; none when standing."""
    if params["path"] == "stand":
        return 0.0
    amp = (BOB_M[0] + (BOB_M[1] - BOB_M[0]) * params["shake"]) * profile.radius
    phase = 2.0 * math.pi * _frac(_seed(params) * 0.6180339887)
    return amp * math.sin(2.0 * math.pi * step_hz(params) * t + phase)


def base(params, profile, u):
    cx, cy, cz = profile.center
    k = ease(params["easing"], settle(u, params["settleFrac"]))
    walk = params["path"]
    d = profile.radius * params["distance"] * ((1.0 - params["pushFrac"] * k) if walk == "walk_in" else 1.0)
    az = math.radians(params["azimuthDeg"] + (params["arcDeg"] * k if walk == "walk_arc" else 0.0))
    z = max(MIN_HEIGHT_M, params["heightFrac"] * profile.sizeM[2])
    return (cx + d * math.cos(az), cy + d * math.sin(az), z), (cx, cy, cz)


def sample(params, profile, u, target=None, ctx=None):
    seconds = ctx.durationS if ctx is not None else DEFAULT_SHOT_S
    t = min(max(u, 0.0), 1.0) * seconds
    pos, tgt = base(params, profile, u)
    shake, sd = params["shake"], _seed(params)
    pos = (pos[0], pos[1], pos[2] + bob_m(params, profile, t))
    if shake <= 0.0:
        return Pose(position=pos, target=tgt, lens_mm=params["lensMm"])
    tr = TRANS_M * profile.radius * shake / math.sqrt(3.0)          # |sway| <= TRANS_M x radius x shake
    sway = (tr * wander(sd + 0.1, t), tr * wander(sd + 0.2, t), tr * 0.7 * wander(sd + 0.3, t))
    pos = tuple(p + s for p, s in zip(pos, sway))
    rot = math.radians(ROT_DEG * shake) / math.sqrt(2.0)             # |aim| <= ROT_DEG x shake
    ay, ap = rot * wander(sd + 0.4, t - AIM_LAG_S), rot * wander(sd + 0.5, t - AIM_LAG_S)
    _, right, up = _basis(Pose(pos, tgt, params["lensMm"]))
    reach = math.dist(pos, tgt)
    aim = tuple(q + (r * math.tan(ay) + v * math.tan(ap)) * reach for q, r, v in zip(tgt, right, up))
    roll = math.radians(ROT_DEG * shake) * ROLL_SHARE * wander(sd + 0.6, t, fast=0.05)
    return Pose(position=pos, target=aim, lens_mm=params["lensMm"], roll=roll)
