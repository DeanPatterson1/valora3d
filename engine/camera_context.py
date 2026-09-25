"""What a camera path may know about its shot beyond (params, profile, u, target) (phase 5 Chunk 6).

A camera manifest with `shotContext: true` gets `ctx=ShotContext(...)` as a keyword on every sample call:
the shot's length in seconds (handheld_operator's footfalls and sway run in real time, Task 82) and, for a
moving subject, its Track (rolling_track follows it, Task 84). Every call site takes its sampler from
camera_sampler, so the checker, the craft scores, the motion rules and the compiler's keys see the same
programme. A camera without the key is called exactly as before."""
import functools
import math
from dataclasses import dataclass

DEFAULT_SHOT_S = 3.0        # (eng) the shot length a context-free call assumes (no shot at hand)
HEADING_DT = 1.0 / 120.0    # s: the central difference that measures the travel direction
HEADING_SCAN = (0.1, 200)   # a stopped subject takes the sign of its nearest travel: step (s) x steps


def rest_forward(profile):
    """The subject's long axis in placed xy (the vehicle's forwardAxis when ingest measured one)."""
    ax = (profile.vehicle or {}).get("forwardAxis")
    if ax:
        n = math.hypot(ax[0], ax[1]) or 1.0
        return (ax[0] / n, ax[1] / n)
    return (1.0, 0.0) if profile.sizeM[0] >= profile.sizeM[1] else (0.0, 1.0)


@dataclass(frozen=True, eq=False)
class Track:
    """A moving subject as a tracking camera sees it: the rest profile, the shared pose function
    (engine/motion_path) and the shot it is framed in."""
    pose_at: object
    profile: object
    shot: dict
    fps: float = None

    def t(self, u):
        from engine.motion_path import shot_t
        return shot_t(self.shot, u, self.fps)

    def at(self, t):
        from engine.motion_path import posed_profile
        return posed_profile(self.profile, self.pose_at(t))

    def _velocity(self, t):
        a, b = self.pose_at(t - HEADING_DT).offset, self.pose_at(t + HEADING_DT).offset
        return (b[0] - a[0], b[1] - a[1])

    def heading(self, t):
        """Unit xy travel direction at t; a stopped subject keeps its long axis (turned by the pose), signed by
        the nearest moment it travels."""
        v = self._velocity(t)
        n = math.hypot(*v)
        if n > 1e-9:
            return (v[0] / n, v[1] / n)
        from engine.motion_path import rotate
        f = rest_forward(self.profile)
        ax = rotate((f[0], f[1], 0.0), self.pose_at(t))
        m = math.hypot(ax[0], ax[1]) or 1.0
        ax = (ax[0] / m, ax[1] / m)
        step, steps = HEADING_SCAN
        for k in range(1, steps + 1):
            for tt in (t - k * step, t + k * step):
                w = self._velocity(tt)
                if math.hypot(*w) > 1e-9:
                    return ax if w[0] * ax[0] + w[1] * ax[1] >= 0 else (-ax[0], -ax[1])
        return ax


@dataclass(frozen=True, eq=False)
class ShotContext:
    durationS: float
    startS: float = 0.0
    track: object = None     # Track for a moving subject, else None

    def __eq__(self, other):
        return (isinstance(other, ShotContext) and (self.durationS, self.startS) == (other.durationS, other.startS)
                and self.track is other.track)

    __hash__ = object.__hash__


def shot_context(shot, track=None):
    return ShotContext(float(shot["endS"]) - float(shot["startS"]), float(shot["startS"]), track)


def camera_sampler(catalog, shot, profile=None, motion=None):
    """The shot camera's sample(params, profile, u, target=None), with ctx bound when the manifest asks.
    profile = the REST profile and motion = (pose_at, fps) for a moving subject: the context then carries the
    subject's Track."""
    bid = shot["camera"]["id"]
    sample = catalog.load_camera_path(bid)
    if not (catalog.get("camera", bid) or {}).get("shotContext"):
        return sample
    track = Track(motion[0], profile, shot, motion[1]) if motion is not None and profile is not None else None
    return functools.partial(sample, ctx=shot_context(shot, track))
