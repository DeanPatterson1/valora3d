"""What a camera path may know about its shot beyond (params, profile, u, target) (phase 5 Chunk 6).

A camera manifest with `shotContext: true` gets `ctx=ShotContext(...)` as a keyword on every sample call:
the shot's length in seconds (handheld_operator's footfalls and sway run in real time, Task 82) and, for a
moving subject, the subject's track (rolling_track follows it, Task 84). Every call site takes its sampler
from camera_sampler, so the checker, the craft scores, the motion rules and the compiler's keys see the same
programme. A camera without the key is called exactly as before."""
import functools
from dataclasses import dataclass

DEFAULT_SHOT_S = 3.0   # (eng) the shot length a context-free call assumes (no shot at hand)


@dataclass(frozen=True)
class ShotContext:
    durationS: float
    startS: float = 0.0
    track: object = None     # engine.camera_context.Track for a moving subject, else None


def shot_context(shot, track=None):
    return ShotContext(float(shot["endS"]) - float(shot["startS"]), float(shot["startS"]), track)


def camera_sampler(catalog, shot, track=None):
    """The shot camera's sample(params, profile, u, target=None), with ctx bound when the manifest asks."""
    bid = shot["camera"]["id"]
    sample = catalog.load_camera_path(bid)
    if not (catalog.get("camera", bid) or {}).get("shotContext"):
        return sample
    return functools.partial(sample, ctx=shot_context(shot, track))
