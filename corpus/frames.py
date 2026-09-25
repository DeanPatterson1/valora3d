"""Frames for studying a LOCAL clip (owner refs, owner-downloaded stock, our renders). Link clips are
never downloaded, so this module never sees them. Output goes under research/corpus/local/ (gitignored)."""
import re
import shutil
import subprocess
from pathlib import Path

SCENE_THRESHOLDS = (0.12, 0.3)   # PILOT-NOTES §1: union of both
MERGE_S = 0.2
PAIR_GAP_S = 0.2                 # PILOT-NOTES §1: camera moves need frame pairs ~0.2 s apart
MIN_PAIR_SHOT_S = 0.6
_PTS = re.compile(r"pts_time:([0-9.]+)")


def _ffmpeg():
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg not found on PATH")
    return exe


def probe_duration(clip):
    exe = shutil.which("ffprobe")
    if not exe:
        raise RuntimeError("ffprobe not found on PATH")
    out = subprocess.run([exe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(clip)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def merge_cuts(times, gap=MERGE_S):
    out = []
    for t in sorted(times):
        if not out or t - out[-1] > gap:
            out.append(t)
    return out


def detect_cuts(clip, thresholds=SCENE_THRESHOLDS):
    found = []
    for th in thresholds:
        proc = subprocess.run([_ffmpeg(), "-hide_banner", "-i", str(clip), "-vf",
                               f"select='gt(scene,{th})',showinfo", "-f", "null", "-"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed on {clip}: {proc.stderr.strip()[-300:]}")
        found += [float(x) for x in _PTS.findall(proc.stderr)]
    return [round(t, 3) for t in merge_cuts(found)]


def sample_plan(duration, cuts, pair_gap=PAIR_GAP_S):
    bounds = [0.0] + [c for c in cuts if 0 < c < duration] + [duration]
    plan = []
    for i, (a, b) in enumerate(zip(bounds, bounds[1:])):
        mid = (a + b) / 2
        plan.append({"shot": i, "kind": "mid", "t": round(mid, 3)})
        if b - a >= MIN_PAIR_SHOT_S:
            t = round(min(b - pair_gap - 0.05, mid + 0.15 * (b - a)), 3)  # later in the shot; >= 1 frame before its end
            plan.append({"shot": i, "kind": "pairA", "t": t})
            plan.append({"shot": i, "kind": "pairB", "t": round(t + pair_gap, 3)})
    return plan


def extract(clip, plan, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for p in plan:
        f = out_dir / f"s{p['shot']:02d}_{p['kind']}_{p['t']:.2f}.jpg"
        subprocess.run([_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{p['t']:.3f}",
                        "-i", str(clip), "-frames:v", "1", "-q:v", "3", str(f)], check=True)
        paths.append(f)
    return paths
