"""A stand-in for `py -m engine.site_job` with the same CLI, SITEJOB lines, output layout and exit codes, but no
Blender: it writes small synthetic PNG frames. Used by worker/tests and `worker/local_test.py --stub`.

FAKE_SITEJOB_MODE: ok (default) | reject (exit 5 in direct) | ingest_reject (exit 1 in ingest) |
                   error (exit 1 in render) | hang (sleeps forever in render) | noframes (done, frames missing)
FAKE_SITEJOB_SIZE: WxH of the frames (default 108x192, a fifth of the 9:16 preview)
FAKE_SITEJOB_FRAME_S: seconds to sleep per frame (default 0)
FAKE_SITEJOB_MARKERS=1: list --markers in `run --help` (tests the feature gate)"""
import argparse
import json
import os
import struct
import sys
import time
import zlib
from pathlib import Path


def emit(stage, **f):
    print("SITEJOB " + json.dumps({"stage": stage, **f}), flush=True)


def png(path, w, h, frame):
    """A tiny RGB gradient PNG that shifts per frame (stdlib only)."""
    rows = []
    for y in range(h):
        row = bytearray([0])
        for x in range(w):
            row += bytes(((x * 255 // max(1, w - 1) + frame * 3) % 256, y * 255 // max(1, h - 1), (frame * 7) % 256))
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 6)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                           + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fake_site_job")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    for flag in ("--model", "--out"):
        r.add_argument(flag, required=True)
    for flag in ("--prompt", "--world", "--aspect", "--seed", "--duration", "--paint", "--finish", "--provider",
                 "--timeout", "--profile"):
        r.add_argument(flag)
    r.add_argument("--tier", default="preview")
    r.add_argument("--frame-step", default="1")
    if os.environ.get("FAKE_SITEJOB_MARKERS") == "1":
        r.add_argument("--markers")
    a = ap.parse_args(argv)
    mode = os.environ.get("FAKE_SITEJOB_MODE", "ok")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    print("Blender 5.0.1 (fake) chatter that is not a SITEJOB line", flush=True)

    emit("ingest")
    if not Path(a.model).is_file():
        emit("error", error="model not found")
        return 1
    if mode == "ingest_reject":
        emit("error", error="The model has more than 5,000,000 vertices.")
        return 1
    emit("direct")
    if mode == "reject":
        emit("error", error="input rejected: world 'moon' is not offered on the site")
        return 5
    fps = 24
    n = int(round(float(a.duration or 3) * fps))
    beauty = out / "render" / "beauty"
    beauty.mkdir(parents=True, exist_ok=True)
    summary = {"source": "fake", "direction": "fake", "world": a.world or "studio",
               "format": {"aspect": a.aspect or "9:16", "durationS": n / fps, "fps": fps}, "unsupported": [],
               "rerolls": 0, "providerError": None}
    emit("render", frames=n, fps=fps, beauty=str(beauty), tier=a.tier, direct=summary)
    w, h = (int(v) for v in os.environ.get("FAKE_SITEJOB_SIZE", "108x192").split("x"))
    if a.aspect == "16:9":
        w, h = h, w
    step_s = float(os.environ.get("FAKE_SITEJOB_FRAME_S", "0"))
    for f in range(1, n + 1):
        if mode == "hang":
            time.sleep(3600)
        if mode == "error" and f == 2:
            emit("error", error="Blender compile failed (exit 11)")
            return 1
        png(beauty / f"{f:04d}.png", w, h, f)
        if step_s:
            time.sleep(step_s)
    frames = out / "frames"
    frames.mkdir(exist_ok=True)
    for f in range(1, n + 1):
        if mode == "noframes" and f == n // 2:
            continue
        (frames / f"frame_{f:06d}.png").write_bytes((beauty / f"{f:04d}.png").read_bytes())
    result = {"frames": n, "fps": float(fps), "framesDir": str(frames), "tier": a.tier,
              "timing": {"ingestS": 0.1, "directS": 0.1, "renderS": 0.5, "totalS": 0.7}, "direct": summary}
    (out / "site_job.json").write_text(json.dumps(result), encoding="utf-8")
    emit("done", **result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
