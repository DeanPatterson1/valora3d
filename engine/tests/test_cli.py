import json
import subprocess

import pytest
import sys
from pathlib import Path

FIX = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[2]


def test_check_command_outputs_json_and_exit_code(tmp_path):
    out = subprocess.run([sys.executable, "-m", "engine", "check", str(FIX / "script_valid.json"),
                          "--profile", str(FIX / "profile_car.json")],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    doc = json.loads(out.stdout)
    assert doc["ok"] is True and doc["script"]["schema"] == "valora.scene/1"

    bad = json.loads((FIX / "script_valid.json").read_text())
    bad["world"]["id"] = "moon"
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    out = subprocess.run([sys.executable, "-m", "engine", "check", str(p),
                          "--profile", str(FIX / "profile_car.json")],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 3  # 2 is argparse's usage-error code
    assert json.loads(out.stdout)["ok"] is False


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "engine", *args], cwd=ROOT, capture_output=True, text=True)


def test_usage_error_keeps_argparse_code_2():
    assert _cli("check").returncode == 2


def test_rejected_upload_is_one_line_exit_1(tmp_path):
    p = tmp_path / "evil.gltf"
    p.write_text("{}")
    out = _cli("ingest", str(p))
    assert out.returncode == 1
    assert "Traceback" not in out.stderr
    assert len(out.stderr.strip().splitlines()) == 1 and ".glb" in out.stderr


@pytest.mark.parametrize("exc", [RuntimeError("Blender extract failed (exit 1):" + chr(10) + "tail"),
                                 subprocess.TimeoutExpired(["blender"], 300)])
def test_ingest_failures_are_one_line_exit_1(monkeypatch, capsys, exc):
    import engine.__main__ as cli
    import engine.ingest.run as run

    def fail(*a, **k):
        raise exc
    monkeypatch.setattr(run, "ingest", fail)
    assert cli.main(["ingest", "x.glb"]) == 1
    err = capsys.readouterr().err
    assert "Traceback" not in err and len(err.strip().splitlines()) == 1, err


def test_other_errors_exit_1_without_traceback(tmp_path):
    out = _cli("check", str(tmp_path / "missing.json"), "--profile", str(FIX / "profile_car.json"))
    assert out.returncode == 1 and "Traceback" not in out.stderr
