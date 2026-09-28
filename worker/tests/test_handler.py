import json
import shutil

import pytest

from worker import handler
from worker.tests.conftest import have_drawtext, make_glb, system_font

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _job(server, **params):
    return {"job_id": "t1", "glb_url": server.base + "/m.glb",
            "output_put_urls": {"video": server.base + "/out/video", "poster": server.base + "/out/poster"},
            "params": {"duration": 3, **params}}


def _serve_glb(server, tmp_path):
    server.routes[("GET", "/m.glb")] = [(200, make_glb(tmp_path / "src.glb").read_bytes())]
    server.routes[("PUT", "/out/video")] = [(200, b"")]
    server.routes[("PUT", "/out/poster")] = [(200, b"")]
    server.routes[("PUT", "/out/frames_zip")] = [(200, b"")]


@needs_ffmpeg
def test_success_end_to_end(stub_env, server, tmp_path):
    _serve_glb(server, tmp_path)
    inp = _job(server, aspect="16:9")
    inp["output_put_urls"]["frames_zip"] = server.base + "/out/frames_zip"
    sent = []
    r = handler.run_job(inp, sent.append)
    assert r["status"] == "succeeded", r
    assert set(r["outputs"]) == {"video", "poster", "frames_zip"}
    assert server.types["/out/video"] == "video/mp4" and server.types["/out/poster"] == "image/jpeg"
    assert server.types["/out/frames_zip"] == "application/zip"
    assert server.puts["/out/poster"][:2] == b"\xff\xd8"
    assert r["frames"] == 90 and r["fps"] == 30.0 and r["video"]["width"] == 192 and r["video"]["height"] == 108
    assert r["render_seconds"] == 0.5 and r["timings"]["total_s"] > 0 and "error" not in r
    stages = [p["stage"] for p in sent]
    assert stages[0] == "downloading" and stages[-1] == "done"
    assert {"ingest", "direct", "render", "encoding", "uploading"} <= set(stages)
    assert sent[-1]["status"] == "COMPLETE"
    assert not any((tmp_path / "jobs").iterdir())           # the work dir is gone


@pytest.mark.parametrize("mode,code,retry", [("reject", "INPUT_REJECTED", False),
                                             ("ingest_reject", "INPUT_REJECTED", False),
                                             ("error", "RENDER_FAILED", True)])
def test_site_job_failures(stub_env, server, tmp_path, mode, code, retry):
    stub_env.setenv("FAKE_SITEJOB_MODE", mode)
    _serve_glb(server, tmp_path)
    r = handler.run_job(_job(server), lambda p: None)
    assert r["status"] == "failed" and r["error_code"] == code and r["retryable"] is retry
    assert r["error"].startswith(code + ": ")
    assert not any(k[0] == "PUT" for k in server.hits)


def test_invalid_input_never_downloads(stub_env, server, tmp_path):
    _serve_glb(server, tmp_path)
    r = handler.run_job(_job(server, tier="ultra"), lambda p: None)
    assert r["error_code"] == "INVALID_INPUT" and r["stage"] == "validate" and server.hits == []


def test_disallowed_host_is_invalid(stub_env, server, tmp_path):
    stub_env.setenv("WORKER_URL_ALLOW_HOSTS", "*.r2.cloudflarestorage.com")
    r = handler.run_job(_job(server), lambda p: None)
    assert r["error_code"] == "INVALID_INPUT" and server.hits == []


def test_bad_glb(stub_env, server, tmp_path):
    server.routes[("GET", "/m.glb")] = [(200, b"PK\x03\x04" + b"\x00" * 40)]
    r = handler.run_job(_job(server), lambda p: None)
    assert r["error_code"] == "GLB_INVALID" and r["stage"] == "downloading"


def test_glb_cap(stub_env, server, tmp_path):
    stub_env.setenv("WORKER_MAX_GLB_BYTES", "16")
    _serve_glb(server, tmp_path)
    assert handler.run_job(_job(server), lambda p: None)["error_code"] == "GLB_TOO_LARGE"


@needs_ffmpeg
def test_markers_ignored_with_warning(stub_env, server, tmp_path):
    _serve_glb(server, tmp_path)
    handler.sitejob._FEATURES = None
    r = handler.run_job(_job(server, markers=[{"anchor": {"space": "gltf", "point": [0, 0, 0]}, "text": "x"}]),
                        lambda p: None)
    assert r["status"] == "succeeded" and any("markers" in w for w in r["warnings"])
    handler.sitejob._FEATURES = None


@needs_ffmpeg
def test_result_echoes_duration_and_watermark(stub_env, server, tmp_path):
    _serve_glb(server, tmp_path)
    r = handler.run_job(_job(server), lambda p: None)
    assert r["status"] == "succeeded", r
    assert r["requested_duration_s"] == 3.0 and r["watermarked"] is False
    assert r["video"]["duration_s"] == 3.0                     # 90 frames / 30 fps
    inp = _job(server)
    del inp["params"]["duration"]
    r = handler.run_job(inp, lambda p: None)
    assert r["status"] == "succeeded" and r["requested_duration_s"] is None


@needs_ffmpeg
def test_watermark_without_font_warns(stub_env, server, tmp_path):
    stub_env.setenv("WORKER_WATERMARK_FONT", str(tmp_path / "missing.ttf"))
    _serve_glb(server, tmp_path)
    r = handler.run_job(_job(server, watermark=True), lambda p: None)
    assert r["status"] == "succeeded" and r["watermarked"] is False
    assert any("watermark" in w for w in r["warnings"])


@pytest.mark.skipif(not (have_drawtext() and system_font()), reason="ffmpeg drawtext or a font missing")
def test_watermark_end_to_end(stub_env, server, tmp_path):
    stub_env.setenv("WORKER_WATERMARK_FONT", system_font())
    _serve_glb(server, tmp_path)
    r = handler.run_job(_job(server, watermark=True), lambda p: None)
    assert r["status"] == "succeeded", r
    assert r["watermarked"] is True and r["warnings"] == []
    assert server.puts["/out/poster"][:2] == b"\xff\xd8"


@needs_ffmpeg
def test_upload_failure(stub_env, server, tmp_path):
    _serve_glb(server, tmp_path)
    server.routes[("PUT", "/out/video")] = [(403, b"SignatureDoesNotMatch")]
    r = handler.run_job(_job(server), lambda p: None)
    assert r["error_code"] == "UPLOAD_FAILED" and r["stage"] == "uploading" and r["retryable"]


def test_handler_refreshes_worker(stub_env, monkeypatch):
    monkeypatch.setattr(handler, "run_job", lambda inp, sink: {"status": "failed", "error": "X"})
    assert handler.handler({"id": "rp", "input": {}})["refresh_worker"] is True
    monkeypatch.setenv("WORKER_REFRESH_AFTER_JOB", "0")
    assert "refresh_worker" not in handler.handler({"id": "rp", "input": {}})


def test_progress_throttle():
    t = [0.0]
    sent = []
    p = handler.Progress("j", sent.append, min_s=5, clock=lambda: t[0])
    p("render", frame=0, total=10)
    t[0] = 1
    assert p("render", frame=1) is None
    t[0] = 6
    assert p("render", frame=2)["frame"] == 2
    t[0] = 6.5
    assert p("encoding")["status"] == "ENCODING"          # a stage change is never throttled
    assert [s["stage"] for s in sent] == ["render", "render", "encoding"]


def test_progress_sink_errors_are_swallowed():
    def boom(_):
        raise RuntimeError("network")
    assert handler.Progress("j", boom, min_s=0)("ingest")["stage"] == "ingest"


def test_asset_status(tmp_path):
    (tmp_path / "engine" / "assets").mkdir(parents=True)
    manifest = {"schema": "valora.assets/1", "assets": {"a": {"path": "x/a.jpg"}, "b": {"path": "b.exr"}}}
    (tmp_path / "engine" / "assets" / "manifest.json").write_text(json.dumps(manifest))
    lib = tmp_path / "lib"
    (lib / "x").mkdir(parents=True)
    (lib / "x" / "a.jpg").write_bytes(b"1")
    h, missing = handler.asset_status(tmp_path, lib)
    assert len(h) == 64 and missing == ["b"]
    assert handler.asset_status(tmp_path / "nope", lib) == (None, ["<manifest>"])


def test_ensure_ready_refuses_missing_assets(monkeypatch, tmp_path):
    monkeypatch.delenv("WORKER_SKIP_READY_CHECKS", raising=False)
    blender = tmp_path / "blender"
    blender.write_bytes(b"")
    monkeypatch.setenv("BLENDER_EXE", str(blender))
    monkeypatch.setattr(handler, "_PIN", {"_missing": ["asphalt_02_diff"]})
    with pytest.raises(handler.WorkerError) as e:
        handler.ensure_ready()
    assert e.value.code == "WORKER_MISCONFIGURED"
    monkeypatch.setenv("WORKER_REQUIRE_ASSETS", "0")
    handler.ensure_ready()
    monkeypatch.setenv("BLENDER_EXE", str(tmp_path / "missing"))
    with pytest.raises(handler.WorkerError):
        handler.ensure_ready()
