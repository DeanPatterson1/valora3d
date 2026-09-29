import json
import sys

import pytest

from worker import sitejob
from worker.contract import Params, WorkerError, parse_params
from worker.tests.conftest import FAKE

CMD = [sys.executable, str(FAKE)]


@pytest.mark.parametrize("line,want", [
    ('SITEJOB {"stage": "ingest"}', {"stage": "ingest"}),
    ('SITEJOB {"stage": "render", "frames": 300, "beauty": "/o/render/beauty"}\n',
     {"stage": "render", "frames": 300, "beauty": "/o/render/beauty"}),
    ('  SITEJOB {"stage": "error", "error": "input rejected: x"}', {"stage": "error", "error": "input rejected: x"}),
    ('SITEJOB {"stage": "warp"}', None),
    ("SITEJOB not json", None),
    ('SITEJOB ["stage"]', None),
    ("Fra:1 Mem:12M | Rendering 1 / 16 samples", None),
    ('echo SITEJOB {"stage": "done"}', None),
])
def test_parse_line(line, want):
    assert sitejob.parse_line(line) == want


def test_build_argv_minimal():
    argv = sitejob.build_argv(Params(), "m.glb", "out", timeout_s=3300.7, provider="anthropic", cmd=["sj"])
    assert argv == ["sj", "run", "--model", "m.glb", "--out", "out", "--tier", "preview", "--provider",
                    "anthropic", "--timeout", "3300"]


def test_build_argv_full_and_marker_gate():
    p = parse_params({"prompt": "rain; rm -rf /", "world": "night_street", "aspect": "16:9", "tier": "final",
                      "seed": 42, "duration": 10, "paint": "#112233", "finish": "satin",
                      "markers": [{"anchor": {}}]})
    argv = sitejob.build_argv(p, "m.glb", "o", timeout_s=60, provider="fake:x", markers_file="mk.json", cmd=["sj"])
    assert "--markers" not in argv                       # the engine does not list it yet
    i = argv.index("--prompt")
    assert argv[i + 1] == "rain; rm -rf /"               # one argv element, never a shell string
    for flag, val in (("--world", "night_street"), ("--aspect", "16:9"), ("--seed", "42"), ("--duration", "10"),
                      ("--paint", "#112233"), ("--finish", "satin"), ("--tier", "final")):
        assert argv[argv.index(flag) + 1] == val
    argv = sitejob.build_argv(p, "m.glb", "o", timeout_s=60, provider="fake:x", markers_file="mk.json",
                              feats=frozenset({"--markers"}), cmd=["sj"])
    assert argv[argv.index("--markers") + 1] == "mk.json"


def test_finish_only_with_paint():
    argv = sitejob.build_argv(parse_params({"finish": "matte"}), "m", "o", timeout_s=60, provider="a", cmd=["sj"])
    assert "--finish" not in argv and "--paint" not in argv


def test_child_env_withholds_runpod_secrets(monkeypatch):
    monkeypatch.setenv("RUNPOD_AI_API_KEY", "secret")
    monkeypatch.setenv("RUNPOD_WEBHOOK_POST_OUTPUT", "u")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
    monkeypatch.setenv("VALORA_DEVICE", "OPTIX")
    monkeypatch.setenv("BLENDER_EXE", "/opt/blender/blender")
    env = sitejob.child_env()
    assert "RUNPOD_AI_API_KEY" not in env and "RUNPOD_WEBHOOK_POST_OUTPUT" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert env["VALORA_DEVICE"] == "OPTIX" and env["BLENDER_EXE"] == "/opt/blender/blender"


def test_site_job_cmd_override(monkeypatch):
    monkeypatch.delenv("WORKER_SITE_JOB_CMD", raising=False)
    assert sitejob.site_job_cmd()[1:] == ["-m", "engine.site_job"]
    monkeypatch.setenv("WORKER_SITE_JOB_CMD", json.dumps(["C:\\py dir\\python.exe", "fake.py"]))
    assert sitejob.site_job_cmd() == ["C:\\py dir\\python.exe", "fake.py"]


def test_features_reads_help(monkeypatch, tmp_path):
    monkeypatch.delenv("FAKE_SITEJOB_MARKERS", raising=False)
    assert "--model" in sitejob.features(CMD, cwd=tmp_path) and "--markers" not in sitejob.features(CMD, cwd=tmp_path)
    monkeypatch.setenv("FAKE_SITEJOB_MARKERS", "1")
    assert "--markers" in sitejob.features(CMD, cwd=tmp_path)


def test_run_streams_events_and_frames(tmp_path, glb, monkeypatch):
    monkeypatch.setenv("FAKE_SITEJOB_MODE", "ok")
    monkeypatch.setenv("FAKE_SITEJOB_FRAME_S", "0.02")
    events, ticks = [], []
    argv = sitejob.build_argv(parse_params({"duration": 3}), glb, tmp_path / "out", timeout_s=60, provider="x",
                              cmd=CMD)
    code, last, stage, tail = sitejob.run(argv, cwd=tmp_path, timeout_s=60, on_event=events.append,
                                          on_frames=lambda n, t: ticks.append((n, t)), poll_s=0.1)
    assert code == 0 and last["stage"] == "done" and last["frames"] == 72 and stage == "done"
    assert [e["stage"] for e in events] == ["ingest", "direct", "render", "done"]
    assert ticks and all(t == 72 for _, t in ticks) and ticks[-1][0] <= 72
    assert any("not a SITEJOB line" in line for line in tail)


def test_run_reports_error_exit(tmp_path, glb, monkeypatch):
    monkeypatch.setenv("FAKE_SITEJOB_MODE", "reject")
    argv = sitejob.build_argv(Params(), glb, tmp_path / "o", timeout_s=60, provider="x", cmd=CMD)
    code, last, stage, _ = sitejob.run(argv, cwd=tmp_path, timeout_s=60, on_event=lambda e: None)
    assert code == 5 and last["stage"] == "error" and stage == "direct"


def test_run_timeout_kills(tmp_path, glb, monkeypatch):
    monkeypatch.setenv("FAKE_SITEJOB_MODE", "hang")
    argv = sitejob.build_argv(Params(), glb, tmp_path / "o", timeout_s=60, provider="x", cmd=CMD)
    with pytest.raises(WorkerError) as e:
        sitejob.run(argv, cwd=tmp_path, timeout_s=2, on_event=lambda e: None)
    assert e.value.code == "RENDER_TIMEOUT" and "render" in e.value.detail


def test_count_beauty(tmp_path):
    for n in ("0001.png", "0002.png", "frame_000001.png", "0003.exr", "x.png"):
        (tmp_path / n).write_bytes(b"")
    assert sitejob.count_beauty(tmp_path) == 2
    assert sitejob.count_beauty(tmp_path / "missing") == 0
