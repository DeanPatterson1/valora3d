"""Pure maths for playing an OpenVDB sequence on a Volume object (phase 6 Task 110, lane S).

Measured 5.0.1 facts (engine/bake/formats.py gas_vdb, the T94 probe): a Volume sequence plays file
index = scene_frame - Volume.frame_start + 1 + Volume.frame_offset; sequence_mode CLIP is empty when
scene_frame - frame_start + 1 falls outside 1..frame_duration (the range is tested BEFORE the offset is added);
the velocity grid is 'velocity' in unit FRAME (voxel-space metres per SIM frame), scale 1.0.

Retime. Blender has no playback-rate control for a volume sequence, so a retimed play keys Volume.frame_offset
per render frame (CONSTANT interpolation): render frame f shows file file_for(f), and velocity_scale is the
retime (a sim frame's motion spread over 1/retime render frames). Slowing a sim (retime < 1) holds files for
several frames; that is a stepped play, so retimes below MIN_RETIME are refused (they judder).

Scale guard (GS-01: "a campfire scaled x10 reads wrong"): a sequence keeps its physical size; a placement may
scale it by at most SCALE_MAX either way. The checker refuses a larger factor (registry patch for Chunk 7)."""
import math

SCALE_MAX = 3.0          # GS-01: at most x3 (or 1/3) of the sequence's native size
MIN_RETIME = 0.25        # below this a stepped play judders (each file held 4+ frames); (eng)
MAX_RETIME = 4.0


class VdbScaleError(ValueError):
    pass


def scale_factor(native_m, scale_m):
    """The uniform object scale that makes a sequence of native size native_m measure scale_m; VdbScaleError
    beyond SCALE_MAX either way (a plume keeps its physical width)."""
    if native_m <= 0 or scale_m <= 0:
        raise VdbScaleError(f"sizes must be positive (native {native_m}, asked {scale_m})")
    f = scale_m / native_m
    if f > SCALE_MAX * (1 + 1e-9) or f < 1 / SCALE_MAX * (1 - 1e-9):
        raise VdbScaleError(f"a {native_m:.3g} m sequence scaled to {scale_m:.3g} m is x{f:.2f}, over the x{SCALE_MAX:g} "
                            "guard: pick a sequence baked nearer that size")
    return f


def clamp_retime(retime):
    return min(MAX_RETIME, max(MIN_RETIME, float(retime)))


def file_for(frame, start, retime, n_files, first_file=1):
    """The sequence file index render frame `frame` shows when file `first_file` plays at render frame `start`
    and the sequence advances `retime` files per render frame; None before the start or past the last file."""
    if frame < start:
        return None
    idx = first_file + int(math.floor((frame - start) * retime + 1e-9))
    return idx if idx <= n_files else None


def play_range(start, retime, n_files, first_file=1):
    """(frame_start, frame_duration): the render frames that show a file (CLIP is empty outside them)."""
    span = int(math.ceil((n_files - first_file + 1) / retime - 1e-9))     # frames k with floor(k r) <= n - first
    return start, span


def offset_keys(start, retime, n_files, first_file=1):
    """[(render frame, Volume.frame_offset)] keys for a retimed play: with frame_start = start, render frame f
    reads file (f - start + 1) + offset = file_for(f). Only the frames where the offset changes are keyed
    (CONSTANT interpolation holds it). retime 1 and first_file 1 is the single key (start, 0)."""
    _, span = play_range(start, retime, n_files, first_file)
    keys, last = [], None
    for f in range(start, start + span):
        off = file_for(f, start, retime, n_files, first_file) - (f - start + 1)
        if off != last:
            keys.append((f, off))
            last = off
    return keys


def velocity_scale(retime):
    """Volume.velocity_scale for a play at `retime` sim frames per render frame (unit FRAME)."""
    return float(retime)
