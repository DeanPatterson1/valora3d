"""Local snapshot -> Blender frames -> MP4 pipeline (no network services)."""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time

import watermark

ROOT = Path(__file__).resolve().parent
_dependency_cache = None
_dependency_checked = 0.0
_dependency_lock = threading.Lock()


class RenderCancelled(RuntimeError):
    """The caller cancelled the active Blender or encoder process."""


def _first_binary(env_key, command, patterns):
    candidates = [os.environ.get(env_key + "_PATH"), os.environ.get(env_key), shutil.which(command)]
    for pattern in patterns:
        candidates.extend(sorted(glob.glob(os.path.expanduser(pattern)), reverse=True))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    return None


def _hidden_process_options():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def discover_dependencies():
    """Discover installed binaries, with a short cache for health polling."""
    global _dependency_cache, _dependency_checked
    with _dependency_lock:
        if _dependency_cache and time.monotonic() - _dependency_checked < 30:
            return dict(_dependency_cache)
        program_files = os.environ.get("ProgramFiles", "C:/Program Files")
        local_app = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))
        blender = _first_binary("BLENDER", "blender", [
            f"{program_files}/Blender Foundation/Blender */blender.exe",
            "/Applications/Blender.app/Contents/MacOS/Blender", "/usr/bin/blender",
        ])
        ffmpeg = _first_binary("FFMPEG", "ffmpeg", [
            "~/.local/ffmpeg/*/bin/ffmpeg.exe", "~/.local/bin/ffmpeg*",
            f"{local_app}/Microsoft/WinGet/Packages/*FFmpeg*/*/bin/ffmpeg.exe",
            f"{local_app}/Microsoft/WinGet/Packages/*FFmpeg*/bin/ffmpeg.exe",
            f"{local_app}/Microsoft/WinGet/Links/ffmpeg.exe",
            "C:/ffmpeg/bin/ffmpeg.exe", f"{program_files}/ffmpeg/bin/ffmpeg.exe",
            "~/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg*.exe",
            "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg",
        ])
        if not ffmpeg:
            try:
                import imageio_ffmpeg
                candidate = imageio_ffmpeg.get_ffmpeg_exe()
                if Path(candidate).is_file():
                    ffmpeg = str(Path(candidate).resolve())
            except (ImportError, RuntimeError, OSError):
                pass
        gpu = "unknown"
        smi = shutil.which("nvidia-smi")
        if not smi and os.name == "nt":
            candidate = Path(os.environ.get("WINDIR", "C:/Windows")) / "System32/nvidia-smi.exe"
            if candidate.is_file():
                smi = str(candidate)
        if smi:
            try:
                result = subprocess.run(
                    [smi, "--query-gpu=name", "--format=csv,noheader"],
                    capture_output=True, text=True, timeout=3, **_hidden_process_options(),
                )
                if result.returncode == 0 and result.stdout.strip():
                    gpu = result.stdout.strip().splitlines()[0]
            except (OSError, subprocess.TimeoutExpired):
                pass
        _dependency_cache = {"blender": blender, "ffmpeg": ffmpeg, "gpu": gpu}
        _dependency_checked = time.monotonic()
        return dict(_dependency_cache)


def _stop_process(process):
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=1.5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def _run_process(command, job_dir, cancelled, on_line=None):
    """Drain output on a reader thread so cancellation never waits for a line."""
    if cancelled.is_set():
        raise RenderCancelled("Render cancelled")
    messages = queue.Queue()
    with (job_dir / "log.txt").open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            command, cwd=job_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            **_hidden_process_options(),
        )

        def read_output():
            try:
                for line in process.stdout:
                    messages.put(line)
            finally:
                messages.put(None)

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        tail = []
        drained = False
        try:
            while not drained or process.poll() is None:
                if cancelled.is_set():
                    raise RenderCancelled("Render cancelled")
                try:
                    line = messages.get(timeout=0.1)
                except queue.Empty:
                    continue
                if line is None:
                    drained = True
                    continue
                log.write(line)
                log.flush()
                tail = (tail + [line.rstrip()])[-12:]
                if on_line:
                    on_line(line.rstrip())
            if cancelled.is_set():
                raise RenderCancelled("Render cancelled")
            if process.returncode:
                detail = next((line for line in reversed(tail) if line.startswith("ERROR ")), None)
                raise RuntimeError(detail or f"{Path(command[0]).name} exited with code {process.returncode}. " + "\n".join(tail[-4:]))
        finally:
            _stop_process(process)
            reader.join(timeout=2)
            if process.stdout:
                process.stdout.close()


# Sensor-style grain after AgX at delivery resolution: a noisy copy is merged
# through an inverted-luma mask, so shadows carry most of it and highlights stay
# clean, as on a real sensor. It also dithers fog gradients.
GRAIN_FILTER = "vignette=angle=PI/14,split=3[a][b][c];[b]noise=alls=13:allf=t+u:all_seed=20260916[n];[c]lutyuv=y='clip(250-val*1.35,45,250)':u=110:v=110[m];[a][n][m]maskedmerge"


def finish_filter(job):
    """The delivery filtergraph ending in [wm], or None. Grain: the spec's flag
    on any scene; without a spec it stays rain-scoped (today's film). A
    watermarked preset composites the overlay (ffmpeg input 1) AFTER the grain
    so the mark is never noised away; the caller adds that input whenever the
    graph names [1:v]."""
    stages = []
    if job.get('grain', job.get('scene') == 'rainy_courtyard'):
        stages.append(GRAIN_FILTER)
    if watermark.wants_watermark(job):
        stages.append("[1:v]overlay=0:0")
    if not stages:
        return None
    graph, label = "", "[0:v]"
    for index, stage in enumerate(stages):
        out = "[wm]" if index == len(stages) - 1 else f"[s{index}]"
        graph += f"{label}{stage}{out};"
        label = out
    return graph.rstrip(";")


def encoding_settings(job, resolution):
    """Resolution-aware delivery quality plus the finishing filtergraph."""
    pixels = int(resolution[0]) * int(resolution[1])
    bitrate = 60000000 if pixels >= 3840 * 2160 else 20000000 if pixels >= 1920 * 1080 else None
    flags = ['-preset', 'slow', '-b:v', str(bitrate), '-maxrate', str(round(bitrate*1.25)),
             '-bufsize', str(bitrate*2)] if bitrate else ['-preset', 'fast', '-crf', '18']
    graph = finish_filter(job)
    if graph:
        flags += ['-filter_complex', graph, '-map', '[wm]']
    return flags, bitrate


def poster_frame(job, first, total):
    """Which frame becomes poster.jpg / the finished latest.jpg. The walk-in film
    opens behind a tree trunk, so its first frame is a brown blur on every car;
    the poster is taken two frames before the first cut instead, where the
    opening shot has framed the car. Orbit programmes keep frame one."""
    programme = (job.get('spec') or {}).get('camera', {}).get('programme') if isinstance(job.get('spec'), dict) else None
    walk_in = programme == 'walk-in-5-shot' or (programme is None and job.get('scene') == 'rainy_courtyard')
    if not walk_in or total < 4:
        return first
    import math
    return first + max(0, math.ceil(0.42 * total) - 2)


def run_pipeline(job, job_dir, on_progress, cancelled):
    """Render an already-validated job and return its measured statistics.

    Inputs: job_dir/snapshot.glb plus canonical job fields. The queue owns
    job.json; this function writes pipeline-job.json and its own output files.
    """
    job_dir = Path(job_dir).resolve()
    snapshot = job_dir / "snapshot.glb"
    if not snapshot.is_file():
        raise ValueError("The saved build snapshot is missing")
    if cancelled.is_set():
        raise RenderCancelled("Render cancelled")
    dependencies = discover_dependencies()
    if not dependencies["blender"] or not dependencies["ffmpeg"]:
        missing = [name for name in ("blender", "ffmpeg") if not dependencies[name]]
        raise RuntimeError("Install or configure " + " and ".join(missing) + " before rendering")
    started = time.monotonic()
    spec_path = job_dir / "pipeline-job.json"
    spec_path.write_text(json.dumps(job, indent=2), encoding="utf-8")
    on_progress({"status": "preparing", "progress": 0, "frame": 0})

    marked = watermark.wants_watermark(job)
    overlay = job_dir / "watermark.png"
    if marked:
        overlay = watermark.build_overlay(overlay, *job["resolution"])

    def blender_line(line):
        if line.startswith("PROGRESS "):
            try:
                event = json.loads(line[len("PROGRESS "):])
            except (ValueError, TypeError):
                return
            if isinstance(event, dict):
                # Blender writes the progress still to latest-raw.jpg on a
                # watermarked job; only the stamped copy is ever named latest.jpg.
                raw = job_dir / "latest-raw.jpg"
                if marked and raw.is_file():
                    try:
                        watermark.stamp_still(raw, overlay, job_dir / "latest.jpg")
                    except OSError:
                        pass                    # half-written by Blender; the next progress line retries
                on_progress(event)

    _run_process([
        dependencies["blender"], "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1",
        "--python", str(ROOT / "render_snapshot.py"), "--", str(spec_path),
    ], job_dir, cancelled, blender_line)
    render_stats = json.loads((job_dir / "render-stats.json").read_text(encoding="utf-8"))
    total = int(render_stats["totalFrames"])
    fps = int(render_stats["fps"])
    first = int(render_stats.get("frameStart", 1))
    frames = job_dir / "frames"
    if any(not (frames / f"frame_{frame:06d}.png").is_file() for frame in range(first, first + total)):
        raise RuntimeError("Blender did not produce every requested frame")
    on_progress({"status": "encoding", "frame": total, "totalFrames": total, "progress": 0.94})
    encoded_at = time.monotonic()
    quality, target_bitrate = encoding_settings(job, render_stats['resolution'])
    encode = [
        dependencies["ffmpeg"], "-y", "-hide_banner", "-loglevel", "warning",
        "-framerate", str(fps), "-start_number", str(first), "-i", str(frames / "frame_%06d.png"),
        *(["-i", str(overlay)] if marked else []),
        "-frames:v", str(total), "-an", "-c:v", "libx264", *quality, "-pix_fmt", "yuv420p",
    ]
    if target_bitrate:
        pass_log = str(job_dir / 'encode-pass')
        _run_process([*encode, '-pass', '1', '-passlogfile', pass_log, '-f', 'null', os.devnull], job_dir, cancelled)
        encode += ['-pass', '2', '-passlogfile', pass_log]
    _run_process([*encode, '-movflags', '+faststart', str(job_dir / 'video.mp4')], job_dir, cancelled)
    _run_process([
        dependencies["ffmpeg"], "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(frames / f"frame_{poster_frame(job, first, total):06d}.png"),
        *(["-i", str(overlay), "-filter_complex", "[0:v][1:v]overlay=0:0[wm]", "-map", "[wm]"] if marked else []),
        "-frames:v", "1", "-q:v", "2",
        str(job_dir / "poster.jpg"),
    ], job_dir, cancelled)
    for output in ("video.mp4", "poster.jpg"):
        if not (job_dir / output).is_file() or (job_dir / output).stat().st_size == 0:
            raise RuntimeError(f"Encoder did not produce {output}")
    if marked or not (job_dir / "latest.jpg").is_file():
        # A finished marked job leaves only stamped stills behind.
        shutil.copyfile(job_dir / "poster.jpg", job_dir / "latest.jpg")
        (job_dir / "latest-raw.jpg").unlink(missing_ok=True)
    stats = {
        **render_stats,
        "duration": total / fps,
        "duration_s": total / fps,
        "elapsedSeconds": round(time.monotonic() - started, 3),
        "encodingSeconds": round(time.monotonic() - encoded_at, 3),
        "secondsPerFrame": round(float(render_stats["renderSeconds"]) / total, 4),
        "gpu": dependencies["gpu"],
        "videoBytes": (job_dir / "video.mp4").stat().st_size,
        "targetBitrate": target_bitrate,
        "encodingPasses": 2 if target_bitrate else 1,
    }
    (job_dir / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats
