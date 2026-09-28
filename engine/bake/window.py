"""Bake windows use frame 1 at t=0; GN has no offset API in Blender 5.0.1.

GN therefore bakes at absolute render frames, including zero/negative pre-roll.
The other portable formats start their bake at 1 and shift frames at playback.
"""
from dataclasses import dataclass
from math import ceil


MODE_FOR_METHOD = {
    "rigid_keys": "shift", "cloth_pc2": "shift", "gas_vdb": "shift",
    "liquid_abc": "shift", "gn_disk": "absolute",
}


@dataclass(frozen=True)
class BakeFrames:
    bake_first: int
    bake_last: int
    clip_first: int
    clip_last: int
    preroll: int
    offset: int
    mode: str
    truncated: bool


def bake_frames(start_s, end_s, fps, preroll_s, max_frames, mode="shift"):
    """Limit the visible clip to the budget while preserving all simulation pre-roll."""
    if end_s <= start_s or fps <= 0 or max_frames < 1 or preroll_s < 0:
        raise ValueError("invalid bake window, fps, pre-roll, or frame budget")
    if mode not in ("shift", "absolute"):
        raise ValueError(f"unknown bake frame mode: {mode!r}")
    clip_first = round(start_s * fps) + 1
    clip_last = ceil(end_s * fps - 1e-9) + 1
    preroll = ceil(preroll_s * fps - 1e-9)
    if preroll + 1 > max_frames:
        raise ValueError("frame budget must fit pre-roll and at least one clip frame")
    truncated = preroll + clip_last - clip_first + 1 > max_frames
    if truncated:
        clip_last = clip_first + max_frames - preroll - 1
    if mode == "absolute":
        first, last, offset = clip_first - preroll, clip_last, 0
    else:
        first = 1
        last = preroll + clip_last - clip_first + 1
        offset = clip_first - preroll - 1
    return BakeFrames(first, last, clip_first, clip_last, preroll, offset, mode, truncated)


def bake_frames_for(method, start_s, end_s, fps, preroll_s, max_frames):
    """Select playback timing from the measured cache format capabilities."""
    try:
        mode = MODE_FOR_METHOD[method]
    except KeyError:
        raise ValueError(f"unknown bake method: {method!r}") from None
    return bake_frames(start_s, end_s, fps, preroll_s, max_frames, mode)


def render_frame(r, bake_frame):
    return bake_frame + r.offset


def bake_frame(r, render_frame):
    return render_frame - r.offset
