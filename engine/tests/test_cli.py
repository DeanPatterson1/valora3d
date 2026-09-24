import json
import subprocess
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
    assert out.returncode == 2
    assert json.loads(out.stdout)["ok"] is False
