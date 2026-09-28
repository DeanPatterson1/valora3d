"""ffmpeg: frames/frame_%06d.png -> H.264 MP4 (yuv420p, +faststart) and a poster JPG; optional frames.zip."""
import os
import re
import subprocess
import zipfile
from fractions import Fraction
from pathlib import Path

from worker.contract import WorkerError

FRAME_PATTERN = "frame_%06d.png"
_FRAME = re.compile(r"^frame_(\d{6})\.png$")
# CRF per tier: preview is a composition check (smaller file), final is the paid clip (visually lossless-ish).
CRF = {"preview": 23, "final": 17}
PRESET = {"preview": "veryfast", "final": "slow"}


def ffmpeg_exe():
    return os.environ.get("FFMPEG_EXE", "ffmpeg")


def rate(fps):
    """30 -> '30', 29.97 -> '2997/100', 15.0 -> '15'; a string ffmpeg reads exactly."""
    f = Fraction(str(fps)).limit_denominator(1001)
    if f <= 0:
        raise WorkerError("ENCODE_FAILED", f"bad fps {fps}")
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


def list_frames(frames_dir):
    """Sorted frame files; raises FRAMES_MISSING unless they are frame_000001.. contiguous."""
    frames_dir = Path(frames_dir)
    try:
        names = sorted(n for n in os.listdir(frames_dir) if _FRAME.match(n))
    except OSError as e:
        raise WorkerError("FRAMES_MISSING", str(e)) from None
    if not names:
        raise WorkerError("FRAMES_MISSING", "no frames")
    for i, n in enumerate(names, 1):
        if int(_FRAME.match(n).group(1)) != i:
            raise WorkerError("FRAMES_MISSING", f"frame {i} is missing")
    return [frames_dir / n for n in names]


def mp4_argv(frames_dir, fps, out, tier="preview", ffmpeg=None):
    r = rate(fps)
    return [ffmpeg or ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-framerate", r, "-start_number", "1", "-i", str(Path(frames_dir) / FRAME_PATTERN),
            # even dimensions for yuv420p; the engine's tiers are already even, this only guards odd sizes
            # sRGB PNG -> BT.709 limited-range YUV with the matrix named explicitly (swscale defaults to BT.601,
            # which would shift hues against the bt709 tags below)
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos+accurate_rnd+full_chroma_int"
                   ":out_color_matrix=bt709:out_range=tv,format=yuv420p",
            "-c:v", "libx264", "-preset", PRESET.get(tier, "medium"), "-crf", str(CRF.get(tier, 20)),
            "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", r,
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            "-movflags", "+faststart", "-an", str(out)]


def poster_index(n):
    """The poster frame (1-based): a third of the way in, past any opening fade, never the last frame."""
    return max(1, min(n, n // 3 + 1))


def poster_argv(frame, out, ffmpeg=None):
    return [ffmpeg or ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(frame),
            "-frames:v", "1", "-q:v", "2", str(out)]


def _run(argv, what, timeout):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        raise WorkerError("WORKER_MISCONFIGURED", "ffmpeg is not installed") from None
    except subprocess.TimeoutExpired:
        raise WorkerError("ENCODE_FAILED", f"{what} timed out") from None
    if p.returncode != 0:
        last = (p.stderr.strip().splitlines() or ["?"])[-1]
        raise WorkerError("ENCODE_FAILED", f"{what}: {last[:300]}")


def encode(frames_dir, fps, out_dir, tier="preview", timeout=1800):
    """Returns {'video': path, 'poster': path, 'frames': n}."""
    frames = list_frames(frames_dir)
    out_dir = Path(out_dir)
    video, poster = out_dir / "video.mp4", out_dir / "poster.jpg"
    _run(mp4_argv(frames_dir, fps, video, tier), "mp4 encode", timeout)
    _run(poster_argv(frames[poster_index(len(frames)) - 1], poster), "poster", 120)
    for p in (video, poster):
        if not p.is_file() or p.stat().st_size == 0:
            raise WorkerError("ENCODE_FAILED", f"{p.name} is empty")
    return {"video": video, "poster": poster, "frames": len(frames)}


def zip_frames(frames_dir, out):
    """PNGs are already deflated: store them."""
    frames = list_frames(frames_dir)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED) as z:
        for f in frames:
            z.write(f, arcname=f.name)
    return out
