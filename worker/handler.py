"""RunPod serverless entry: `python -m worker.handler` (the image's CMD).

One job: validate -> download the GLB (200 MB cap, glTF header check) -> `engine.site_job run` (SITEJOB lines and
beauty-frame counts become progress updates) -> ffmpeg MP4 + poster (+ optional frames.zip) -> PUT to the job's
presigned URLs -> a result dict. The contract (input, progress, output, error codes) is in worker/README.md."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from worker import encode, sitejob, transfer
from worker.contract import OUTPUT_TYPES, WorkerError, error_for_exit, parse_job

WORKER_VERSION = "1"
# site_job stage -> the site's RenderJob.status (apps/web lib/schema/project.ts)
STATUS = {"downloading": "PREPARING", "ingest": "PREPARING", "direct": "PREPARING", "render": "RENDERING",
          "encoding": "ENCODING", "uploading": "UPLOADING", "done": "COMPLETE", "error": "FAILED"}


def _env(name, default):
    return os.environ.get(name, default)


def _flag(name, default="0"):
    return _env(name, default).strip().lower() in ("1", "true", "yes")


def timeout_for(tier):
    return float(_env("WORKER_TIMEOUT_FINAL_S" if tier == "final" else "WORKER_TIMEOUT_PREVIEW_S",
                      "14400" if tier == "final" else "3600"))


def make_non_dumpable():
    """Linux: PR_SET_DUMPABLE=0 so a compromised child (same uid) cannot read this process's /proc/<pid>/environ
    or ptrace it -- that environ holds RunPod's job-reporting key. Children regain dumpability on exec, which is
    fine: they never receive that key (sitejob.child_env)."""
    if not sys.platform.startswith("linux"):
        return False
    try:
        import ctypes
        return ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0) == 0
    except (OSError, AttributeError):
        return False


# ---------------------------------------------------------------- cold-start facts (cached per container)

_PIN = None


def _gpu_name():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True,
                             text=True, timeout=20).stdout.strip().splitlines()
        return out[0].strip() if out else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def asset_status(engine_root=None, library=None):
    """(manifest sha256, missing asset ids). A missing asset makes its block build a procedural fallback --
    a different look than the owner graded -- so production refuses to render without the full library."""
    engine_root = Path(engine_root or sitejob.engine_dir())
    manifest = engine_root / "engine" / "assets" / "manifest.json"
    if not manifest.is_file():
        return None, ["<manifest>"]
    raw = manifest.read_bytes()
    lib = Path(library or _env("VALORA_ASSET_LIBRARY", "") or engine_root / "assets-in" / "library")
    missing = [aid for aid, a in json.loads(raw)["assets"].items() if not (lib / a["path"]).is_file()]
    return hashlib.sha256(raw).hexdigest(), missing


def pin():
    """Build identity for every result (render-core spec: blender_build, engine_sha, assets_hash, gpu_model)."""
    global _PIN
    if _PIN is None:
        assets_hash, missing = asset_status()
        _PIN = {"worker": WORKER_VERSION, "blender": _env("VALORA_BLENDER_VERSION", "5.0.1"),
                "engineSha": _env("VALORA_ENGINE_SHA", "unknown"), "assetsHash": assets_hash,
                "assetsMissing": len(missing), "gpu": _gpu_name()}
        _PIN["_missing"] = missing
    return _PIN


def ensure_ready():
    """Raise WORKER_MISCONFIGURED when this container cannot deliver the graded look."""
    if _flag("WORKER_SKIP_READY_CHECKS"):
        return
    p = pin()
    blender = _env("BLENDER_EXE", "")
    if not blender or not Path(blender).is_file():
        raise WorkerError("WORKER_MISCONFIGURED", f"BLENDER_EXE {blender!r} not found")
    if p["_missing"] and _flag("WORKER_REQUIRE_ASSETS", "1"):
        raise WorkerError("WORKER_MISCONFIGURED",
                          f"{len(p['_missing'])} pinned assets missing (first: {p['_missing'][0]}); "
                          "mount or bake assets-in/library, see worker/README.md")


def public_pin():
    return {k: v for k, v in pin().items() if not k.startswith("_")}


# ---------------------------------------------------------------- progress

class Progress:
    """Throttled progress: every stage change is sent; frame ticks at most every `min_s` seconds."""

    def __init__(self, job_id, sink, min_s=None, clock=time.monotonic):
        self.job_id, self.sink, self.clock = job_id, sink, clock
        self.min_s = float(_env("WORKER_PROGRESS_MIN_S", "5")) if min_s is None else min_s
        self.stage, self.last_sent, self.frame, self.total = None, None, 0, 0

    def __call__(self, stage, frame=None, total=None, force=False):
        if frame is not None:
            self.frame = frame
        if total is not None:
            self.total = total
        now = self.clock()
        changed = stage != self.stage
        if not (changed or force) and self.last_sent is not None and now - self.last_sent < self.min_s:
            return None
        self.stage, self.last_sent = stage, now
        payload = {"job_id": self.job_id, "stage": stage, "status": STATUS.get(stage, "PREPARING"),
                   "frame": self.frame, "total_frames": self.total}
        try:
            self.sink(payload)
        except Exception:  # noqa: BLE001 - progress is best-effort, never fails a job
            pass
        return payload


def runpod_sink(event):
    def send(payload):
        import runpod
        runpod.serverless.progress_update(event, payload)
    return send


# ---------------------------------------------------------------- the job

def run_job(inp, progress_sink, work_root=None):
    """Returns the handler's result dict (success or failure; never raises)."""
    t0 = time.perf_counter()
    timings, warnings = {}, []
    job_id = inp.get("job_id") if isinstance(inp, dict) else None
    stage = "validate"
    tail = []
    root = Path(work_root or _env("WORKER_JOB_ROOT", "/tmp/valora-jobs"))
    work = root / uuid.uuid4().hex            # never a user-supplied string in a path
    try:
        job = parse_job(inp)
        transfer.check_url(job.glb_url, "glb_url")
        for name, url in job.outputs.items():
            transfer.check_url(url, f"output_put_urls.{name}")
        progress = Progress(job.job_id, progress_sink)
        ensure_ready()
        work.mkdir(parents=True, exist_ok=False)
        out = work / "out"

        stage = "downloading"
        progress(stage)
        t = time.perf_counter()
        model = work / "model.glb"
        max_bytes = int(_env("WORKER_MAX_GLB_BYTES", str(transfer.MAX_GLB_BYTES)))
        glb_bytes = transfer.download(job.glb_url, model, max_bytes=max_bytes)
        transfer.check_glb(model)
        timings["download_s"] = round(time.perf_counter() - t, 2)

        markers_file = None
        feats = frozenset()
        if job.params.markers:
            feats = sitejob.features()
            if "--markers" in feats:
                markers_file = work / "markers.json"
                markers_file.write_text(json.dumps(job.params.markers), encoding="utf-8")
            else:
                warnings.append("markers were ignored: this engine build has no --markers option yet")
        total_timeout = timeout_for(job.params.tier)
        argv = sitejob.build_argv(job.params, model, out, timeout_s=max(60, total_timeout - 300),
                                  provider=_env("VALORA_PROVIDER", "anthropic"), markers_file=markers_file,
                                  feats=feats)

        def on_event(ev):
            nonlocal stage
            if ev["stage"] in ("ingest", "direct", "render"):
                stage = ev["stage"]
                progress(stage, frame=0 if stage == "render" else None,
                         total=int(ev.get("frames") or 0) if stage == "render" else None)

        t = time.perf_counter()
        code, last, sj_stage, tail = sitejob.run(argv, cwd=sitejob.engine_dir(), timeout_s=total_timeout,
                                                 on_event=on_event,
                                                 on_frames=lambda n, total: progress("render", frame=n, total=total))
        timings["site_job_s"] = round(time.perf_counter() - t, 2)
        if code != 0 or not last or last.get("stage") != "done":
            err = last.get("error") if last and last.get("stage") == "error" else None
            raise error_for_exit(code if code != 0 else 1, err or "site_job ended without a done line", sj_stage)
        done = last
        sj = json.loads((out / "site_job.json").read_text(encoding="utf-8")) if (out / "site_job.json").is_file() \
            else done
        for k, v in (sj.get("timing") or {}).items():
            timings[{"ingestS": "ingest_s", "directS": "direct_s", "renderS": "render_s",
                     "totalS": "engine_total_s"}.get(k, k)] = v
        frames_dir = out / "frames"
        fps = float(sj.get("fps") or 30)
        diag = _diagnostics(out)

        stage = "encoding"
        progress(stage, force=True)
        t = time.perf_counter()
        enc = encode.encode(frames_dir, fps, work, tier=job.params.tier, watermark=job.params.watermark)
        warnings.extend(enc["warnings"])
        if sj.get("frames") is not None and int(sj["frames"]) != enc["frames"]:
            raise WorkerError("FRAMES_MISSING", f"site_job reported {sj['frames']} frames, found {enc['frames']}")
        files = {"video": enc["video"], "poster": enc["poster"]}
        if "frames_zip" in job.outputs:
            files["frames_zip"] = encode.zip_frames(frames_dir, work / "frames.zip")
        timings["encode_s"] = round(time.perf_counter() - t, 2)
        width, height = encode.png_size(encode.list_frames(frames_dir)[0])

        stage = "uploading"
        progress(stage, force=True)
        t = time.perf_counter()
        outputs = {}
        for name, path in files.items():
            n = transfer.upload(job.outputs[name], path, OUTPUT_TYPES[name])
            outputs[name] = {"bytes": n, "content_type": OUTPUT_TYPES[name]}
        timings["upload_s"] = round(time.perf_counter() - t, 2)
        timings["total_s"] = round(time.perf_counter() - t0, 2)
        progress("done", force=True)
        return {"status": "succeeded", "job_id": job.job_id, "outputs": outputs,
                "video": {"width": width, "height": height, "fps": fps, "frames": enc["frames"],
                          "duration_s": round(enc["frames"] / fps, 3) if fps else None},
                "requested_duration_s": job.params.duration, "watermarked": enc["watermarked"],
                "frames": enc["frames"], "fps": fps, "tier": job.params.tier,
                "render_seconds": timings.get("render_s", timings["site_job_s"]),
                "gpu_seconds": timings["site_job_s"], "glb_bytes": glb_bytes,
                "timings": timings, "direct": sj.get("direct"), "pin": public_pin(), "warnings": warnings,
                "diag": diag}
    except WorkerError as e:
        return _failure(job_id, e, stage, timings, t0, tail, warnings)
    except Exception as e:  # noqa: BLE001 - one INTERNAL result, never a traceback to the site
        return _failure(job_id, WorkerError("INTERNAL", f"{type(e).__name__}: {e}"), stage, timings, t0, tail,
                        warnings)
    finally:
        if not _flag("WORKER_KEEP_WORKDIR"):
            shutil.rmtree(work, ignore_errors=True)


def _diagnostics(out):
    """Where a render's time went on this host (for cost work): the engine's phase_timing.json, if written, and the
    CPU the host gives the container. Never fails a job."""
    diag = {"cpus": os.cpu_count()}
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                diag["cpu_model"] = line.split(":", 1)[1].strip()
                break
        diag["cpus_allowed"] = len(os.sched_getaffinity(0))
    except (OSError, AttributeError):
        pass
    try:
        found = next(Path(out).rglob("phase_timing.json"), None)
        if found:
            diag["phases"] = json.loads(found.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return diag


def _failure(job_id, e, stage, timings, t0, tail, warnings):
    timings["total_s"] = round(time.perf_counter() - t0, 2)
    try:
        p = public_pin() if not _flag("WORKER_SKIP_READY_CHECKS") else None
    except Exception:  # noqa: BLE001
        p = None
    return {"error": f"{e.code}: {e.message}", "status": "failed", "job_id": job_id if isinstance(job_id, str) else None,
            "error_code": e.code, "error_message": e.message, "error_detail": e.detail, "retryable": e.retryable,
            "stage": stage, "timings": timings, "pin": p, "warnings": warnings, "log_tail": tail[-20:]}


def handler(event):
    """RunPod handler. `refresh_worker` recycles the container after every job (untrusted uploads never share a
    container) unless WORKER_REFRESH_AFTER_JOB=0."""
    result = run_job((event or {}).get("input"), runpod_sink(event))
    if _flag("WORKER_REFRESH_AFTER_JOB", "1"):
        result["refresh_worker"] = True
    return result


def main():
    make_non_dumpable()
    import runpod
    try:
        pin()                         # warm the cold-start facts (GPU name, asset check) before the first job
    except Exception:  # noqa: BLE001
        pass
    runpod.serverless.start({"handler": handler})


if __name__ == "__main__":
    main()
