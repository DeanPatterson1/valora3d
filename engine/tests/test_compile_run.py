"""compile_scene host side, with Blender mocked out (no Blender launch)."""
import json
import subprocess
from pathlib import Path

import pytest

from engine.catalog import BLOCKS_DIR, Catalog
from engine.compiler import run
from engine.profile import SubjectProfile

FIX = Path(__file__).parent / "fixtures"
MODEL = Path(__file__).resolve().parents[2] / "assets-in" / "models" / "toycar" / "toycar.glb"
pytestmark = pytest.mark.skipif(not MODEL.exists(), reason="model not present")


def _args():
    prof = SubjectProfile.from_dict(json.loads((FIX / "profiles" / "toycar.json").read_text(encoding="utf-8")))
    return json.loads((FIX / "script_valid.json").read_text(encoding="utf-8")), prof


def _blender(write):
    def fake(cmd, **kw):
        job = Path(cmd[-1])
        if write:
            (job.parent / "compile.json").write_text(json.dumps({"fresh": True}), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return fake


def test_a_stale_compile_json_is_never_read_as_this_runs_result(tmp_path, monkeypatch):
    (tmp_path / "compile.json").write_text(json.dumps({"stale": True}), encoding="utf-8")
    monkeypatch.setattr(run.subprocess, "run", _blender(write=False))
    s, prof = _args()
    with pytest.raises(RuntimeError, match="compile failed"):
        run.compile_scene(s, prof, MODEL, tmp_path, render=False)


def test_the_job_names_the_catalog_the_checker_used(tmp_path, monkeypatch):
    monkeypatch.setattr(run.subprocess, "run", _blender(write=True))
    s, prof = _args()
    cat = Catalog.load(BLOCKS_DIR)
    res = run.compile_scene(s, prof, MODEL, tmp_path, render=False, catalog=cat)
    assert res == {"fresh": True, "assetFallbacks": []}   # studio: no photographic set to fall back from
    job = json.loads((tmp_path / "job.json").read_text(encoding="utf-8"))
    assert Path(job["catalogRoot"]) == Path(cat.root).resolve()
