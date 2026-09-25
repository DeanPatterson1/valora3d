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


def test_render_command_prints_json_and_maps_check_failure_to_3(monkeypatch, capsys, tmp_path):
    import engine.__main__ as cli
    import engine.compiler.run as run

    seen = {}

    def fake(script, profile, model, out_dir, **kw):
        seen.update(kw, model=model, out=out_dir)
        return {"blender": "5.0", "built": []}
    monkeypatch.setattr(run, "compile_scene", fake)
    args = ["render", str(FIX / "script_valid.json"), "--profile", str(FIX / "profile_car.json"),
            "--model", "m.glb", "--out", str(tmp_path), "--tier", "keyframes", "--frames", "1,16"]
    assert cli.main(args) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["ok"] is True and doc["compile"]["blender"] == "5.0" and doc["out"] == str(tmp_path)
    assert seen["tier"] == "keyframes" and seen["frames"] == [1, 16] and seen["save_blend"] is False

    def fail(*a, **k):
        raise run.CheckFailed("E_UNKNOWN_BLOCK at world.id: nope")
    monkeypatch.setattr(run, "compile_scene", fail)
    assert cli.main(args) == 3
    err = capsys.readouterr().err
    assert "Traceback" not in err and len(err.strip().splitlines()) == 1


def test_direct_with_a_fake_provider(tmp_path, capsys):
    from engine.__main__ import main
    out = tmp_path / "s.json"
    code = main(["direct", "--profile", str(FIX / "profiles" / "pocket_watch.json"), "--prompt", "luxury",
                 "--seed", "3", "--provider", f"fake:{FIX / 'director' / 'watch_luxury_ok.json'}",
                 "--out", str(out)])
    res = json.loads(capsys.readouterr().out)
    assert code == 0 and res["source"] == "llm" and json.loads(out.read_text())["prompt"] == "luxury"


def test_direct_rejects_bad_markers(tmp_path):
    from engine.__main__ import main
    m = tmp_path / "m.json"
    m.write_text('[{"id": "BAD", "text": "x", "anchor": {"point": [0, 0, 0]}}]')
    assert main(["direct", "--profile", str(FIX / "profiles" / "pocket_watch.json"), "--markers", str(m),
                 "--provider", f"fake:{FIX / 'director' / 'watch_luxury_ok.json'}"]) == 3
