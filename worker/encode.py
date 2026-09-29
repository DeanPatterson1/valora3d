"""ffmpeg: frames/frame_%06d.png -> H.264 MP4 (yuv420p, +faststart) and a poster JPG; optional frames.zip."""
import os
import re
import struct
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
# Watermark: a subtle site-URL wordmark bottom-right, sized off the short side so 9:16 and 16:9 get the same visual weight.
WATERMARK_TEXT = "valora3d.com"
WATERMARK_SIZE = 0.042       # font px per px of the frame's short side (540 -> 23 px, 1080 -> 45 px)
WATERMARK_MARGIN = 0.045     # inset from the right and bottom edges, same unit
WATERMARK_ALPHA = 0.6
DEFAULT_WATERMARK_FONT = "/usr/share/fonts/valora/Inter-SemiBold.ttf"   # baked by worker/Dockerfile


def ffmpeg_exe():
    return os.environ.get("FFMPEG_EXE", "ffmpeg")


def watermark_font():
    """The font file for the wordmark, or None when it is absent (a local run without the image's font)."""
    path = os.environ.get("WORKER_WATERMARK_FONT", DEFAULT_WATERMARK_FONT)
    return path if path and Path(path).is_file() else None


def _filter_value(text):
    """Quote a value for a filtergraph option: forward slashes, `:` and `'` escaped, wrapped in single quotes."""
    return "'" + str(text).replace("\\", "/").replace("'", r"'\''").replace(":", r"\:") + "'"


def watermark_filter(width, height, font):
    """drawtext for the wordmark on a width x height frame: white at 60% opacity, a faint shadow for light
    backgrounds, font size and margin proportional to the short side."""
    short = min(int(width), int(height))
    size = max(10, round(short * WATERMARK_SIZE))
    margin = max(4, round(short * WATERMARK_MARGIN))
    shadow = max(1, round(size / 24))
    return (f"drawtext=fontfile={_filter_value(font)}:text={_filter_value(WATERMARK_TEXT)}"
            f":fontsize={size}:fontcolor=white@{WATERMARK_ALPHA}"
            f":shadowcolor=black@0.25:shadowx={shadow}:shadowy={shadow}"
            f":x=w-tw-{margin}:y=h-th-{margin}")


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


def mp4_argv(frames_dir, fps, out, tier="preview", ffmpeg=None, watermark=None):
    """`watermark` is a drawtext filter (watermark_filter) drawn on the RGB frame before the YUV conversion."""
    r = rate(fps)
    pre = f"{watermark}," if watermark else ""
    return [ffmpeg or ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-framerate", r, "-start_number", "1", "-i", str(Path(frames_dir) / FRAME_PATTERN),
            # even dimensions for yuv420p; the engine's tiers are already even, this only guards odd sizes
            # sRGB PNG -> BT.709 limited-range YUV with the matrix named explicitly (swscale defaults to BT.601,
            # which would shift hues against the bt709 tags below)
            "-vf", pre + "scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos+accurate_rnd+full_chroma_int"
                   ":out_color_matrix=bt709:out_range=tv,format=yuv420p",
            "-c:v", "libx264", "-preset", PRESET.get(tier, "medium"), "-crf", str(CRF.get(tier, 20)),
            "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", r,
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            "-movflags", "+faststart", "-an", str(out)]


def poster_index(n):
    """The poster frame (1-based): a third of the way in, past any opening fade, never the last frame."""
    return max(1, min(n, n // 3 + 1))


def poster_argv(frame, out, ffmpeg=None, watermark=None):
    return [ffmpeg or ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(frame),
            *(["-vf", watermark] if watermark else []), "-frames:v", "1", "-q:v", "2", str(out)]


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


def png_size(path):
    """(width, height) from a PNG header, or (None, None)."""
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None, None
    return struct.unpack(">II", head[16:24])


def encode(frames_dir, fps, out_dir, tier="preview", timeout=1800, watermark=False):
    """Returns {'video': path, 'poster': path, 'frames': n, 'watermarked': bool, 'warnings': [...]}.

    With `watermark`, the wordmark is burned into the MP4 and the poster. Without its font file (a local run
    outside the image) the encode goes ahead unmarked, `watermarked` is False and a warning says why."""
    frames = list_frames(frames_dir)
    out_dir = Path(out_dir)
    video, poster = out_dir / "video.mp4", out_dir / "poster.jpg"
    warnings, mark = [], None
    if watermark:
        font = watermark_font()
        width, height = png_size(frames[0])
        if not font:
            warnings.append("watermark skipped: the watermark font file is missing on this worker")
        elif not width:
            warnings.append("watermark skipped: the frame size could not be read")
        else:
            mark = watermark_filter(width, height, font)
    _run(mp4_argv(frames_dir, fps, video, tier, watermark=mark), "mp4 encode", timeout)
    _run(poster_argv(frames[poster_index(len(frames)) - 1], poster, watermark=mark), "poster", 120)
    for p in (video, poster):
        if not p.is_file() or p.stat().st_size == 0:
            raise WorkerError("ENCODE_FAILED", f"{p.name} is empty")
    return {"video": video, "poster": poster, "frames": len(frames), "watermarked": mark is not None,
            "warnings": warnings}


def zip_frames(frames_dir, out):
    """PNGs are already deflated: store them."""
    frames = list_frames(frames_dir)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED) as z:
        for f in frames:
            z.write(f, arcname=f.name)
    return out
