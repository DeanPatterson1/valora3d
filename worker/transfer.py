"""Downloads and uploads over presigned URLs: https only (http/file only with WORKER_ALLOW_INSECURE_URLS=1 for local
tests), an optional host allowlist, no redirects (a redirect could leave the allowlist), a hard size cap, and a
cheap GLB header check before the engine's own ingest checks."""
import fnmatch
import os
import shutil
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from worker.contract import WorkerError

MAX_GLB_BYTES = 200 * 1024 * 1024   # engine/ingest/run.py MAX_FILE_BYTES
CHUNK = 1 << 20
GLB_HEADER = struct.Struct("<4sII")
GLB_CHUNK = struct.Struct("<II")
JSON_CHUNK = 0x4E4F534A


def _env_flag(name, default="0"):
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes")


def allowed_hosts():
    raw = os.environ.get("WORKER_URL_ALLOW_HOSTS", "")
    return [h.strip().lower() for h in raw.split(",") if h.strip()]


def check_url(url, what, *, insecure=None, hosts=None):
    """Raise WorkerError(INVALID_INPUT) unless `url` is one this worker may touch."""
    insecure = _env_flag("WORKER_ALLOW_INSECURE_URLS") if insecure is None else insecure
    hosts = allowed_hosts() if hosts is None else hosts
    try:
        u = urllib.parse.urlsplit(url)
    except ValueError:
        raise WorkerError("INVALID_INPUT", f"{what} is not a URL") from None
    schemes = ("https", "http", "file") if insecure else ("https",)
    if u.scheme not in schemes:
        raise WorkerError("INVALID_INPUT", f"{what} must be an https URL")
    if u.scheme != "file":
        host = (u.hostname or "").lower()
        if not host:
            raise WorkerError("INVALID_INPUT", f"{what} has no host")
        if hosts and not any(fnmatch.fnmatchcase(host, h) for h in hosts):
            raise WorkerError("INVALID_INPUT", f"{what} host {host} is not allowed")
    return u


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _file_path(u):
    return Path(urllib.request.url2pathname(u.path if not u.netloc else f"//{u.netloc}{u.path}"))


def download(url, dest, *, max_bytes=MAX_GLB_BYTES, timeout=120):
    """Stream `url` to `dest`, never writing more than max_bytes. Returns the byte count."""
    u = check_url(url, "glb_url")
    dest = Path(dest)
    try:
        if u.scheme == "file":
            src = _file_path(u)
            size = src.stat().st_size
            if size > max_bytes:
                raise WorkerError("GLB_TOO_LARGE", f"{size} bytes")
            shutil.copyfile(src, dest)
            return size
        with _OPENER.open(urllib.request.Request(url, method="GET"), timeout=timeout) as r:
            declared = r.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > max_bytes:
                raise WorkerError("GLB_TOO_LARGE", f"{declared} bytes declared")
            n = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = r.read(CHUNK)
                    if not chunk:
                        break
                    n += len(chunk)
                    if n > max_bytes:
                        raise WorkerError("GLB_TOO_LARGE", f"more than {max_bytes} bytes")
                    f.write(chunk)
            return n
    except WorkerError:
        dest.unlink(missing_ok=True)
        raise
    except urllib.error.HTTPError as e:
        dest.unlink(missing_ok=True)
        raise WorkerError("GLB_DOWNLOAD_FAILED", f"HTTP {e.code}") from None
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        dest.unlink(missing_ok=True)
        raise WorkerError("GLB_DOWNLOAD_FAILED", type(e).__name__ + ": " + str(e)[:200]) from None


def check_glb(path):
    """The cheap binary-glTF checks: 'glTF' magic, version 2, declared length == file size, a JSON first chunk that
    fits. The engine's ingest does the full checks (external URIs, vertex and image caps)."""
    path = Path(path)
    size = path.stat().st_size
    with open(path, "rb") as f:
        head = f.read(GLB_HEADER.size + GLB_CHUNK.size)
    if len(head) < GLB_HEADER.size + GLB_CHUNK.size:
        raise WorkerError("GLB_INVALID", "file is too short")
    magic, version, length = GLB_HEADER.unpack_from(head)
    if magic != b"glTF":
        raise WorkerError("GLB_INVALID", "no glTF magic")
    if version != 2:
        raise WorkerError("GLB_INVALID", f"glTF version {version}")
    if length != size:
        raise WorkerError("GLB_INVALID", f"header length {length} != file size {size}")
    clen, ctype = GLB_CHUNK.unpack_from(head, GLB_HEADER.size)
    if ctype != JSON_CHUNK or clen == 0 or GLB_HEADER.size + GLB_CHUNK.size + clen > size:
        raise WorkerError("GLB_INVALID", "first chunk is not a JSON chunk that fits")
    return size


def upload(url, path, content_type, *, attempts=3, timeout=300, backoff=2.0, sleep=time.sleep):
    """PUT `path` to a presigned URL with the Content-Type it was signed for; retries transient failures."""
    u = check_url(url, "output URL")
    path = Path(path)
    size = path.stat().st_size
    last = None
    for i in range(attempts):
        try:
            if u.scheme == "file":
                shutil.copyfile(path, _file_path(u))
                return size
            with open(path, "rb") as f:
                req = urllib.request.Request(url, data=f, method="PUT",
                                             headers={"Content-Type": content_type, "Content-Length": str(size)})
                with _OPENER.open(req, timeout=timeout) as r:
                    if 200 <= r.status < 300:
                        return size
                    last = f"HTTP {r.status}"
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if 400 <= e.code < 500 and e.code not in (408, 429):
                break                         # a signature/expiry problem does not heal on retry
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            last = f"{type(e).__name__}: {str(e)[:200]}"
        if i + 1 < attempts:
            sleep(backoff * (2 ** i))
    raise WorkerError("UPLOAD_FAILED", f"{path.name}: {last}")
