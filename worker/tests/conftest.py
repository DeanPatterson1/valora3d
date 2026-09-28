import json
import struct
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

WORKER = Path(__file__).resolve().parents[1]
FAKE = WORKER / "fake_site_job.py"


def make_glb(path, extra=b""):
    js = json.dumps({"asset": {"version": "2.0"}}).encode()
    js += b" " * (-len(js) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js + extra
    Path(path).write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body)
    return Path(path)


def system_font():
    """Any TTF this machine has (the image's Inter is not in the repo), or None."""
    for p in (r"C:\Windows\Fonts\arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/Library/Fonts/Arial.ttf",
              "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if Path(p).is_file():
            return p
    return None


def have_drawtext():
    import shutil
    import subprocess
    exe = shutil.which("ffmpeg")
    if not exe:
        return False
    out = subprocess.run([exe, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return " drawtext " in out


@pytest.fixture
def glb(tmp_path):
    return make_glb(tmp_path / "m.glb")


@pytest.fixture
def stub_env(monkeypatch, tmp_path):
    """Handler env for the stub site_job over loopback URLs."""
    monkeypatch.setenv("WORKER_ALLOW_INSECURE_URLS", "1")
    monkeypatch.setenv("WORKER_URL_ALLOW_HOSTS", "127.0.0.1")
    monkeypatch.setenv("WORKER_SKIP_READY_CHECKS", "1")
    monkeypatch.setenv("WORKER_JOB_ROOT", str(tmp_path / "jobs"))
    monkeypatch.setenv("WORKER_PROGRESS_MIN_S", "0")
    monkeypatch.setenv("WORKER_SITE_JOB_CMD", json.dumps([sys.executable, str(FAKE)]))
    monkeypatch.setenv("FAKE_SITEJOB_MODE", "ok")
    return monkeypatch


class Server:
    """A loopback stand-in for R2. `routes[(method, path)] = list of (status, body)` responses, consumed in order
    (the last one repeats); PUT bodies land in `puts[path]` with their Content-Type in `types[path]`."""

    def __init__(self):
        self.routes, self.puts, self.types, self.hits = {}, {}, {}, []
        srv = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _reply(self, method):
                srv.hits.append((method, self.path))
                if method == "PUT":
                    n = int(self.headers.get("Content-Length", "0"))
                    srv.puts[self.path] = self.rfile.read(n)
                    srv.types[self.path] = self.headers.get("Content-Type")
                seq = srv.routes.get((method, self.path)) or [(404, b"")]
                status, body, *hdrs = seq.pop(0) if len(seq) > 1 else seq[0]
                self.send_response(status)
                for k, v in (hdrs[0] if hdrs else {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                self._reply("GET")

            def do_PUT(self):
                self._reply("PUT")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"


@pytest.fixture
def server():
    s = Server()
    yield s
    s.httpd.shutdown()
