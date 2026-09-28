import struct

import pytest

from worker import transfer
from worker.contract import WorkerError
from worker.tests.conftest import make_glb


def code_of(fn, *a, **k):
    with pytest.raises(WorkerError) as e:
        fn(*a, **k)
    return e.value.code


@pytest.mark.parametrize("url,insecure,hosts,ok", [
    ("https://acct.r2.cloudflarestorage.com/b/k?X-Amz-Signature=1", False, ["*.r2.cloudflarestorage.com"], True),
    ("https://evil.example.com/k", False, ["*.r2.cloudflarestorage.com"], False),
    ("https://anything.example.com/k", False, [], True),
    ("http://acct.r2.cloudflarestorage.com/k", False, [], False),
    ("file:///etc/passwd", False, [], False),
    ("ftp://h/k", True, [], False),
    ("http://127.0.0.1:9/k", True, ["127.0.0.1"], True),
    ("http://169.254.169.254/latest", True, ["127.0.0.1"], False),
    ("https:///nohost", False, [], False),
])
def test_check_url(url, insecure, hosts, ok):
    if ok:
        transfer.check_url(url, "u", insecure=insecure, hosts=hosts)
    else:
        assert code_of(transfer.check_url, url, "u", insecure=insecure, hosts=hosts) == "INVALID_INPUT"


def test_check_glb_accepts_valid(glb):
    assert transfer.check_glb(glb) == glb.stat().st_size


def _mutate(path, offset, fmt, value):
    b = bytearray(path.read_bytes())
    struct.pack_into(fmt, b, offset, value)
    path.write_bytes(bytes(b))


@pytest.mark.parametrize("mutation", ["magic", "version", "length", "chunktype", "short", "chunklen"])
def test_check_glb_rejects(tmp_path, mutation):
    p = make_glb(tmp_path / "m.glb")
    if mutation == "magic":
        _mutate(p, 0, "<4s", b"PK\x03\x04")
    elif mutation == "version":
        _mutate(p, 4, "<I", 1)
    elif mutation == "length":
        _mutate(p, 8, "<I", 999999)
    elif mutation == "chunktype":
        _mutate(p, 16, "<I", 0x004E4942)
    elif mutation == "chunklen":
        _mutate(p, 12, "<I", 10 ** 6)
    else:
        p.write_bytes(b"glTF")
    assert code_of(transfer.check_glb, p) == "GLB_INVALID"


def test_download_http_and_cap(server, tmp_path, monkeypatch):
    monkeypatch.setenv("WORKER_ALLOW_INSECURE_URLS", "1")
    monkeypatch.setenv("WORKER_URL_ALLOW_HOSTS", "127.0.0.1")
    body = make_glb(tmp_path / "src.glb").read_bytes()
    server.routes[("GET", "/m.glb")] = [(200, body)]
    dest = tmp_path / "d.glb"
    assert transfer.download(server.base + "/m.glb", dest) == len(body)
    assert dest.read_bytes() == body
    assert code_of(transfer.download, server.base + "/m.glb", dest, max_bytes=10) == "GLB_TOO_LARGE"
    assert not dest.exists()


def test_download_errors(server, tmp_path, monkeypatch):
    monkeypatch.setenv("WORKER_ALLOW_INSECURE_URLS", "1")
    monkeypatch.setenv("WORKER_URL_ALLOW_HOSTS", "127.0.0.1")
    server.routes[("GET", "/gone")] = [(403, b"expired")]
    server.routes[("GET", "/redir")] = [(302, b"", {"Location": "http://169.254.169.254/"})]
    assert code_of(transfer.download, server.base + "/gone", tmp_path / "a") == "GLB_DOWNLOAD_FAILED"
    assert code_of(transfer.download, server.base + "/redir", tmp_path / "b") == "GLB_DOWNLOAD_FAILED"
    assert ("GET", "/redir") in server.hits and len(server.hits) == 2      # the redirect was not followed
    assert code_of(transfer.download, "http://127.0.0.1:1/x", tmp_path / "c") == "GLB_DOWNLOAD_FAILED"


def test_download_file_url_only_when_insecure(tmp_path, glb, monkeypatch):
    monkeypatch.delenv("WORKER_ALLOW_INSECURE_URLS", raising=False)
    assert code_of(transfer.download, glb.as_uri(), tmp_path / "x") == "INVALID_INPUT"
    monkeypatch.setenv("WORKER_ALLOW_INSECURE_URLS", "1")
    assert transfer.download(glb.as_uri(), tmp_path / "x") == glb.stat().st_size
    assert code_of(transfer.download, glb.as_uri(), tmp_path / "y", max_bytes=5) == "GLB_TOO_LARGE"


def test_upload_retries_5xx_then_succeeds(server, tmp_path, monkeypatch):
    monkeypatch.setenv("WORKER_ALLOW_INSECURE_URLS", "1")
    monkeypatch.setenv("WORKER_URL_ALLOW_HOSTS", "127.0.0.1")
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x" * 1000)
    server.routes[("PUT", "/v")] = [(500, b""), (503, b""), (200, b"")]
    sleeps = []
    assert transfer.upload(server.base + "/v", f, "video/mp4", sleep=sleeps.append) == 1000
    assert len(sleeps) == 2 and server.puts["/v"] == b"x" * 1000 and server.types["/v"] == "video/mp4"


def test_upload_does_not_retry_signature_errors(server, tmp_path, monkeypatch):
    monkeypatch.setenv("WORKER_ALLOW_INSECURE_URLS", "1")
    monkeypatch.setenv("WORKER_URL_ALLOW_HOSTS", "127.0.0.1")
    f = tmp_path / "p.jpg"
    f.write_bytes(b"j")
    server.routes[("PUT", "/p")] = [(403, b"SignatureDoesNotMatch")]
    sleeps = []
    assert code_of(transfer.upload, server.base + "/p", f, "image/jpeg", sleep=sleeps.append) == "UPLOAD_FAILED"
    assert sleeps == [] and server.hits.count(("PUT", "/p")) == 1
