"""Run the handler end to end on this machine, without Docker or RunPod.

    py -m worker.local_test                     # stub site_job (no Blender, seconds), preview, 3 s clip
    py -m worker.local_test --mode reject       # a stub failure path (see worker/fake_site_job.py modes)
    py -m worker.local_test --engine            # the real engine.site_job (runs Blender on this GPU!)

A loopback HTTP server stands in for R2: GET /model.glb serves the model, PUT /out/<name> stores results. The
model defaults to the smallest .glb under assets-in/models (the CC0 Khronos ToyCar in the main checkout); with
none found, the stub mode uses a synthetic minimal GLB."""
import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODEL_DIRS = (REPO / "assets-in" / "models", REPO.parent / "Rendering" / "assets-in" / "models")


def minimal_glb(path):
    """A valid-header GLB with an empty scene: enough for the stub (the real engine would reject it)."""
    js = json.dumps({"asset": {"version": "2.0"}, "scenes": [{"nodes": []}], "scene": 0}).encode()
    js += b" " * (-len(js) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js
    Path(path).write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body)
    return Path(path)


def find_model():
    """The smallest CC0 model (assets-in/models/LICENSES.md): sports_car is the owner's licensed GT3 RS (local
    only), sneaker and cesium_man are CC-BY eval subjects (cesium_man carries a trademark), so none of those."""
    cc0 = ("toycar", "camera_01", "pocket_watch", "flighthelmet", "mid_century_lounge_chair", "vintage_microscope")
    glbs = [p for d in MODEL_DIRS for sub in cc0 if (d / sub).is_dir() for p in (d / sub).glob("*.glb")]
    return min(glbs, key=lambda p: p.stat().st_size) if glbs else None


def serve(model, store):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path != "/model.glb":
                self.send_error(404)
                return
            data = Path(model).read_bytes()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_PUT(self):
            name = self.path.rsplit("/", 1)[-1]
            if not self.path.startswith("/out/") or name not in ("video", "poster", "frames_zip"):
                self.send_error(403)
                return
            n = int(self.headers.get("Content-Length", "0"))
            (Path(store) / name).write_bytes(self.rfile.read(n))
            (Path(store) / f"{name}.content-type").write_text(self.headers.get("Content-Type", ""))
            self.send_response(200)
            self.end_headers()

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def ffprobe(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                              "stream=codec_name,pix_fmt,width,height,r_frame_rate,nb_frames", "-of", "json",
                              str(path)], capture_output=True, text=True, timeout=60).stdout
        return json.loads(out)["streams"][0]
    except (OSError, ValueError, KeyError, IndexError, subprocess.TimeoutExpired):
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="worker.local_test")
    ap.add_argument("--engine", action="store_true", help="run the real engine.site_job (Blender) instead of the stub")
    ap.add_argument("--model", help="a .glb (default: smallest under assets-in/models)")
    ap.add_argument("--mode", default="ok", help="stub mode: ok|reject|ingest_reject|error|noframes|hang")
    ap.add_argument("--tier", default="preview", choices=("preview", "final"))
    ap.add_argument("--duration", type=float, default=3, help="clip seconds (engine minimum 3)")
    ap.add_argument("--aspect", default="9:16")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--provider", default="anthropic", help="engine mode: anthropic or fake:FIXTURE")
    ap.add_argument("--zip", action="store_true", help="also request frames.zip")
    ap.add_argument("--keep", help="copy the uploaded results to this directory")
    a = ap.parse_args(argv)

    tmp = Path(tempfile.mkdtemp(prefix="valora-worker-local-"))
    store = tmp / "r2"
    store.mkdir()
    model = Path(a.model) if a.model else find_model()
    if model is None:
        if a.engine:
            sys.exit("no .glb found; pass --model")
        model = minimal_glb(tmp / "minimal.glb")
    os.environ.update({"WORKER_ALLOW_INSECURE_URLS": "1", "WORKER_URL_ALLOW_HOSTS": "127.0.0.1",
                       "WORKER_JOB_ROOT": str(tmp / "jobs"), "WORKER_PROGRESS_MIN_S": "0"})
    if a.engine:
        os.environ.setdefault("VALORA_ENGINE_DIR", str(REPO))
        os.environ["VALORA_PROVIDER"] = a.provider
        os.environ.pop("WORKER_SITE_JOB_CMD", None)
        os.environ.setdefault("WORKER_REQUIRE_ASSETS", "0")
        if not os.environ.get("BLENDER_EXE"):
            os.environ["BLENDER_EXE"] = r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
    else:
        os.environ["WORKER_SKIP_READY_CHECKS"] = "1"
        os.environ["FAKE_SITEJOB_MODE"] = a.mode
        os.environ["WORKER_SITE_JOB_CMD"] = json.dumps([sys.executable, str(Path(__file__).with_name(
            "fake_site_job.py"))])
        if a.mode == "hang":
            os.environ["WORKER_TIMEOUT_PREVIEW_S"] = "5"

    from worker.handler import run_job
    srv = serve(model, store)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    outputs = {"video": f"{base}/out/video", "poster": f"{base}/out/poster"}
    if a.zip:
        outputs["frames_zip"] = f"{base}/out/frames_zip"
    inp = {"job_id": "local-test", "glb_url": f"{base}/model.glb", "output_put_urls": outputs,
           "params": {"prompt": a.prompt, "aspect": a.aspect, "tier": a.tier, "duration": a.duration}}
    print(f"model: {model} ({model.stat().st_size} bytes) mode: {'engine' if a.engine else 'stub:' + a.mode}")
    result = run_job(inp, lambda p: print("progress", json.dumps(p)))
    srv.shutdown()
    print(json.dumps(result, indent=2))
    ok = result.get("status") == "succeeded"
    if ok:
        probe = ffprobe(store / "video")
        print("ffprobe:", json.dumps(probe))
        ok = bool(probe) and probe.get("codec_name") == "h264" and probe.get("pix_fmt") == "yuv420p"
        if a.keep:
            dest = Path(a.keep)
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(store / "video", dest / "video.mp4")
            shutil.copyfile(store / "poster", dest / "poster.jpg")
            print("kept in", dest)
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if ok or a.mode != "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
