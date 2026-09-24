"""Launch Blender headless to extract raw facts, then build the SubjectProfile."""
import json
import os
import subprocess
import tempfile
from pathlib import Path

from engine.ingest.measure import build_profile

BLENDER = os.environ.get("BLENDER_EXE", r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
EXTRACT = Path(__file__).with_name("blender_extract.py")
TIMEOUT_S = 300


def ingest(model_path, workdir=None):
    workdir = Path(workdir or tempfile.mkdtemp(prefix="valora-ingest-"))
    workdir.mkdir(parents=True, exist_ok=True)
    raw_path = workdir / "raw.json"
    cmd = [BLENDER, "--background", "--factory-startup", "--disable-autoexec",
           "--python-exit-code", "1", "--python", str(EXTRACT), "--", str(model_path), str(raw_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=TIMEOUT_S)
    if proc.returncode != 0 or not raw_path.exists():
        tail = (proc.stderr or proc.stdout)[-2000:]
        raise RuntimeError(f"Blender extract failed (exit {proc.returncode}):\n{tail}")
    return build_profile(json.loads(raw_path.read_text(encoding="utf-8")))
