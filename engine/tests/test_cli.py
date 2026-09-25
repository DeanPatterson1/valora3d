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
    code = main(["direct", "--profile", str(FIX / "profiles" / "pocket_watch.json"), "--prompt",
                 "luxury, 10 seconds", "--seed", "3", "--provider",
                 f"fake:{FIX / 'director' / 'watch_luxury_ok.json'}", "--out", str(out)])
    res = json.loads(capsys.readouterr().out)
    assert code == 0 and res["source"] == "llm" and json.loads(out.read_text())["prompt"] == "luxury, 10 seconds"


def test_direct_rejects_bad_markers(tmp_path):
    from engine.__main__ import main
    m = tmp_path / "m.json"
    m.write_text('[{"id": "BAD", "text": "x", "anchor": {"point": [0, 0, 0]}}]')
    assert main(["direct", "--profile", str(FIX / "profiles" / "pocket_watch.json"), "--markers", str(m),
                 "--provider", f"fake:{FIX / 'director' / 'watch_luxury_ok.json'}"]) == 5


def _fixture(tmp_path, replies):
    f = tmp_path / "fx.json"
    f.write_text(json.dumps({"replies": replies}), encoding="utf-8")
    return f"fake:{f}"


def test_direct_provider_error_falls_back_with_one_warning_and_exit_0(tmp_path, capsys):
    from engine.__main__ import main
    code = main(["direct", "--profile", str(FIX / "profiles" / "pocket_watch.json"),
                 "--provider", _fixture(tmp_path, [{"error": "HTTP 403: blocked"}])])
    cap = capsys.readouterr()
    assert code == 0 and json.loads(cap.out)["source"] == "fallback"
    lines = cap.err.strip().splitlines()
    assert len(lines) == 1 and lines[0].startswith("engine: warning:") and "fallback" in lines[0]
    assert "HTTP 403: blocked" in lines[0]


def test_direct_strict_exits_non_zero_on_a_provider_error_fallback(tmp_path, capsys):
    from engine.__main__ import EXIT_FALLBACK, main
    code = main(["direct", "--profile", str(FIX / "profiles" / "pocket_watch.json"), "--strict",
                 "--provider", _fixture(tmp_path, [{"error": "HTTP 403: blocked"}])])
    assert code == EXIT_FALLBACK != 0 and json.loads(capsys.readouterr().out)["source"] == "fallback"


def test_direct_no_warning_when_the_fallback_is_not_a_provider_error(tmp_path, capsys):
    from engine.__main__ import main
    code = main(["direct", "--profile", str(FIX / "profiles" / "pocket_watch.json"), "--strict",
                 "--provider", _fixture(tmp_path, [{"stop_reason": "refusal", "text": ""}])])
    cap = capsys.readouterr()
    assert code == 0 and json.loads(cap.out)["source"] == "fallback" and cap.err == ""


def test_direct_anthropic_without_a_key_falls_back_offline(monkeypatch, capsys):
    """The real no-key path, with no network: the SDK refuses before sending (base URL is a dead local
    port in case a credential is found anyway)."""
    pytest.importorskip("anthropic")
    from engine.__main__ import main
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:9")
    code = main(["direct", "--profile", str(FIX / "profiles" / "pocket_watch.json"), "--provider", "anthropic"])
    cap = capsys.readouterr()
    assert code == 0 and json.loads(cap.out)["source"] == "fallback"
    assert len(cap.err.strip().splitlines()) == 1 and "engine: warning:" in cap.err


def test_direct_bad_input_has_its_own_exit_code(tmp_path):
    from engine.__main__ import EXIT_BAD_INPUT, EXIT_CHECK_FAILED, main
    assert EXIT_BAD_INPUT not in (0, 1, 2, EXIT_CHECK_FAILED, 4)
    for doc in ("{}", '{"id": "m0"}', '"x"'):
        m = tmp_path / "m.json"
        m.write_text(doc)
        assert main(["direct", "--profile", str(FIX / "profiles" / "pocket_watch.json"), "--markers", str(m),
                     "--provider", f"fake:{FIX / 'director' / 'watch_luxury_ok.json'}"]) == EXIT_BAD_INPUT, doc
