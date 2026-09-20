"""Loopback-only Render Studio API. Run with Python 3.10+; no pip install needed."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import socket
import sys
from urllib.parse import parse_qs, urlsplit

from jobs import JobError, JobStore, MAX_BODY_BYTES, SCENES, TERMINAL, validate_job


ORIGIN_PATTERN = re.compile(r"^http://(?:localhost|127\.0\.0\.1|\[::1\]):([0-9]{1,5})$")
FILE_TYPES = {"video.mp4": "video/mp4", "poster.jpg": "image/jpeg", "latest.jpg": "image/jpeg"}


class RenderServer(ThreadingHTTPServer):
    daemon_threads = True
    # Windows SO_REUSEADDR permits a second listener to hijack the same port.
    # POSIX reuse only permits prompt restarts after a listener has closed.
    allow_reuse_address = sys.platform != "win32"

    def __init__(self, port, store, dependencies):
        self.store = store
        self.dependencies = dependencies
        super().__init__(("127.0.0.1", port), RenderHandler)

    def server_bind(self):
        if sys.platform == "win32":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class RenderHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ModVisionLocalRender/1"

    def setup(self):
        super().setup()
        self.connection.settimeout(30)
        self.allowed_origin = None

    def _guard(self, mutation=False):
        self.allowed_origin = None
        self._body_consumed = False  # per request; a handler outlives one on keep-alive
        host = self.headers.get("Host", "")
        port = self.server.server_port
        if len(self.headers.get_all("Host", [])) != 1 or host not in {f"localhost:{port}", f"127.0.0.1:{port}", f"[::1]:{port}"}:
            raise JobError("This service accepts loopback Host headers only.", 403)
        origins = self.headers.get_all("Origin", [])
        if len(origins) > 1:
            raise JobError("Multiple Origin headers are not allowed.", 403)
        if origins:
            match = ORIGIN_PATTERN.fullmatch(origins[0])
            if not match or not 1 <= int(match.group(1)) <= 65535:
                raise JobError("Only local HTTP pages can use Render Studio.", 403)
            self.allowed_origin = origins[0]
        if mutation and self.headers.get_content_type() != "application/json":
            raise JobError("Mutations require Content-Type: application/json.", 415)

    def _headers(self, status, content_type="application/json; charset=utf-8", length=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if self.allowed_origin:
            self.send_header("Access-Control-Allow-Origin", self.allowed_origin)
            self.send_header("Vary", "Origin")
        if length is not None:
            self.send_header("Content-Length", str(length))

    def _json(self, status, value):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self._headers(status, length=len(body))
        self.end_headers()
        self.wfile.write(body)

    def _drain_rejected_body(self):
        """Read a small rejected body that has already arrived.

        Closing a socket with unread bytes makes Windows answer with RST, and
        the client can lose the error response to it (measured: 3 of 20 test
        runs across the 415 and chunked cases). One bounded read with a 50 ms
        limit: an oversized or never-sent body is not waited for.
        """
        if getattr(self, '_body_consumed', False) or self.headers is None:
            return
        lengths = self.headers.get_all('Content-Length', [])
        if not self.headers.get('Transfer-Encoding') and not any(v.isdigit() and int(v) > 0 for v in lengths):
            return
        previous = self.connection.gettimeout()
        try:
            self.connection.settimeout(.05)
            self.rfile.read1(65536)
        except (OSError, ValueError):
            pass
        finally:
            try:
                self.connection.settimeout(previous)
            except OSError:
                pass

    def _error(self, exc):
        self.close_connection = True
        self._drain_rejected_body()
        try:
            self._json(exc.status, {"error": str(exc)})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def _read_json(self):
        if self.headers.get("Transfer-Encoding"):
            raise JobError("Chunked request bodies are not supported.", 400)
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not lengths[0].isdigit():
            raise JobError("One valid Content-Length header is required.", 411)
        length = int(lengths[0])
        if length > MAX_BODY_BYTES:
            raise JobError("Snapshot request exceeds the 128 MiB limit.", 413)
        try:
            raw = self.rfile.read(length)
            self._body_consumed = True
            if len(raw) != length:
                raise JobError("Incomplete request body.")
            return json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        except (ValueError, UnicodeDecodeError) as exc:
            raise JobError("Request body must contain valid JSON.") from exc

    def do_OPTIONS(self):
        try:
            self._guard()
            method = self.headers.get("Access-Control-Request-Method", "GET")
            if method not in {"GET", "POST", "DELETE"}:
                raise JobError("Method is not allowed.", 405)
            headers = {item.strip().lower() for item in self.headers.get("Access-Control-Request-Headers", "").split(",") if item.strip()}
            if headers - {"content-type", "range"}:
                raise JobError("Request headers are not allowed.", 403)
            self._headers(204, length=0)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Range")
            self.end_headers()
        except JobError as exc:
            self._error(exc)

    def do_GET(self):
        try:
            self._guard()
            parsed = urlsplit(self.path)
            path = parsed.path
            store = self.server.store
            if path == "/api/health":
                dependencies = self.server.dependencies()
                ready = bool(dependencies.get("blender") and dependencies.get("ffmpeg"))
                response = {"ok": True, **dependencies, "ready": ready, "queueLength": store.queue_length()}
                if not ready:
                    response["error"] = "Install Blender and FFmpeg, or set BLENDER_PATH and FFMPEG_PATH."
                self._json(200, response)
            elif path == "/api/scenes":
                import spec as render_spec
                scenes = [{**scene, "manifest": render_spec.load_manifest(scene["id"])} for scene in SCENES]
                self._json(200, {"scenes": scenes})
            elif path == "/api/spec/random":
                import secrets
                import spec as render_spec
                query = parse_qs(parsed.query)
                scene_id = query.get("scene", [""])[0]
                raw_seed = query.get("seed", [None])[0]
                try:
                    seed = secrets.randbelow(render_spec.SEED_MAX) if raw_seed is None else int(raw_seed)
                    self._json(200, render_spec.sample_spec(scene_id, seed))
                except (ValueError, render_spec.SpecError) as exc:
                    self._json(400, {"error": str(exc)})
            elif path == "/api/estimate":
                query = parse_qs(parsed.query)
                self._json(200, store.estimate(query.get("preset", ["draft"])[0], query.get("scene", ["turntable"])[0], query.get("aspect", ["16:9"])[0]))
            elif path == "/api/jobs":
                self._json(200, {"jobs": store.list()})
            elif re.fullmatch(r"/api/jobs/[0-9a-f]{32}/events", path):
                self._events(path.split("/")[3])
            elif re.fullmatch(r"/api/jobs/[0-9a-f]{32}", path):
                self._json(200, store.get(path.split("/")[3]))
            elif path.startswith("/files/"):
                self._file(path, download=parse_qs(parsed.query).get("download") == ["1"])
            else:
                raise JobError("Not found.", 404)
        except JobError as exc:
            self._error(exc)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True

    def do_POST(self):
        try:
            self._guard(mutation=True)
            body = self._read_json()
            path = urlsplit(self.path).path
            if path == "/api/jobs":
                dependencies = self.server.dependencies()
                if not dependencies.get("blender") or not dependencies.get("ffmpeg"):
                    raise JobError("Rendering needs Blender and FFmpeg. Install them or configure BLENDER_PATH and FFMPEG_PATH.", 503)
                spec, snapshot = validate_job(body)
                self._json(201, self.server.store.submit(spec, snapshot))
            elif re.fullmatch(r"/api/jobs/[0-9a-f]{32}/cancel", path):
                if not isinstance(body, dict) or body:
                    raise JobError("Cancel expects an empty JSON object.")
                self._json(200, self.server.store.cancel(path.split("/")[3]))
            elif re.fullmatch(r"/api/jobs/[0-9a-f]{32}/retry", path):
                if not isinstance(body, dict) or body:
                    raise JobError("Retry expects an empty JSON object.")
                dependencies = self.server.dependencies()
                if not dependencies.get("blender") or not dependencies.get("ffmpeg"):
                    raise JobError("Rendering needs Blender and FFmpeg.", 503)
                self._json(201, self.server.store.retry(path.split("/")[3]))
            else:
                raise JobError("Not found.", 404)
        except JobError as exc:
            self._error(exc)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True

    def do_DELETE(self):
        try:
            self._guard(mutation=True)
            path = urlsplit(self.path).path
            if not re.fullmatch(r"/api/jobs/[0-9a-f]{32}", path):
                raise JobError("Not found.", 404)
            # Drain an optional JSON body so it cannot become another HTTP request.
            if self.headers.get("Content-Length") or self.headers.get("Transfer-Encoding"):
                body = self._read_json()
                if not isinstance(body, dict) or body:
                    raise JobError("Delete expects an empty JSON object.")
            self.server.store.delete(path.split("/")[3])
            self._json(200, {"deleted": True})
        except JobError as exc:
            self._error(exc)

    def _events(self, job_id):
        store = self.server.store
        item = store.get(job_id)
        self._headers(200, "text/event-stream; charset=utf-8")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        revision = None
        while True:
            if item["revision"] != revision:
                message = "event: progress\ndata: " + json.dumps(item, ensure_ascii=False) + "\n\n"
                self.wfile.write(message.encode("utf-8"))
                revision = item["revision"]
            else:
                self.wfile.write(b": heartbeat\n\n")
            self.wfile.flush()
            if item["status"] in TERMINAL:
                return
            with store.changed:
                store.changed.wait_for(lambda: store.stopping or job_id not in store.jobs or store.jobs[job_id].get("revision") != revision, timeout=15)
                if store.stopping or job_id not in store.jobs:
                    return
                item = store.get(job_id)

    def _file(self, path, download=False):
        pieces = path.split("/")
        if len(pieces) != 4 or pieces[3] not in FILE_TYPES:
            raise JobError("File not found.", 404)
        _, _, job_id, name = pieces
        item = self.server.store.get(job_id)
        if name != "latest.jpg" and item["status"] != "done":
            raise JobError("This render is not finished.", 404)
        folder = self.server.store.directory(job_id)
        file_path = (folder / name).resolve()
        if file_path.parent != folder or not file_path.is_file():
            raise JobError("File not found.", 404)
        try:
            source = file_path.open("rb")
        except OSError as exc:
            raise JobError("File not found.", 404) from exc
        with source:
            size = file_path.stat().st_size
            start, end = 0, size - 1
            partial = False
            byte_range = self.headers.get("Range") if name == "video.mp4" else None
            if byte_range:
                match = re.fullmatch(r"bytes=(\d*)-(\d*)", byte_range)
                try:
                    if not match or not any(match.groups()):
                        raise ValueError()
                    if match[1]:
                        start = int(match[1])
                        end = min(int(match[2]), size - 1) if match[2] else size - 1
                    else:
                        suffix = int(match[2])
                        if suffix <= 0:
                            raise ValueError()
                        start = max(0, size - suffix)
                    if start > end or start >= size:
                        raise ValueError()
                except ValueError:
                    self._headers(416, length=0)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
                partial = True
            self._headers(206 if partial else 200, FILE_TYPES[name], end - start + 1)
            self.send_header("Accept-Ranges", "bytes" if name == "video.mp4" else "none")
            self.send_header("Access-Control-Expose-Headers", "Content-Range, Content-Length, Content-Disposition")
            if download:
                self.send_header("Content-Disposition", f'attachment; filename="modvision-{job_id}-{name}"')
            if partial:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            source.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


def main():
    parser = argparse.ArgumentParser(description="Run the local ModVision Render Studio API.")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    from pipeline import discover_dependencies, run_pipeline
    # Reserve the API port before reading or recovering persistent jobs. A
    # second launch on this port must never alter the live worker's state.
    try:
        server = RenderServer(args.port, None, discover_dependencies)
    except OSError as exc:
        parser.exit(1, f"Cannot start Render Studio on 127.0.0.1:{args.port}: {exc}\n")
    try:
        store = JobStore(Path(__file__).parent / "out", run_pipeline)
    except Exception:
        server.server_close()
        raise
    server.store = store
    print(f"ModVision Render Studio: http://127.0.0.1:{args.port}", flush=True)
    print(json.dumps(discover_dependencies(), indent=2), flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("Stopping local render worker...", flush=True)
    finally:
        server.server_close()
        store.close()


if __name__ == "__main__":
    main()
