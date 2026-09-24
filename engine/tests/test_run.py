"""ingest() process hygiene, with Blender mocked out."""
import json
import subprocess
import tempfile

import pytest

from engine.ingest import run
from engine.tests.test_preflight import _doc, make_glb

RAW = {"boundsMin": [0, 0, 0], "boundsMax": [1, 1, 1], "polyCount": 1, "materials": []}


@pytest.fixture
def model(tmp_path):
    p = tmp_path / "m.glb"
    p.write_bytes(make_glb(_doc(), b"\0" * 36))
    return p


@pytest.fixture
def isolated_temp(tmp_path, monkeypatch):
    t = tmp_path / "temp"
    t.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(t))
    return t


def _fake_blender(returncode=0, stdout="", stderr="", write=True):
    def fake(cmd, **kw):
        if write:
            with open(cmd[-1], "w", encoding="utf-8") as f:
                json.dump(RAW, f)
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)
    return fake


def test_default_workdir_is_removed(model, isolated_temp, monkeypatch):
    monkeypatch.setattr(run.subprocess, "run", _fake_blender())
    assert run.ingest(model).polyCount == 1
    assert list(isolated_temp.iterdir()) == []


def test_default_workdir_is_removed_on_failure(model, isolated_temp, monkeypatch):
    monkeypatch.setattr(run.subprocess, "run", _fake_blender(1, write=False))
    with pytest.raises(RuntimeError):
        run.ingest(model)
    assert list(isolated_temp.iterdir()) == []


def test_failure_message_has_both_tails(model, tmp_path, monkeypatch):
    monkeypatch.setattr(run.subprocess, "run",
                        _fake_blender(1, stdout="noise\nOUT-MARK", stderr="ERR-MARK\n", write=False))
    with pytest.raises(RuntimeError) as e:
        run.ingest(model, workdir=tmp_path / "w")
    msg = str(e.value)
    assert "OUT-MARK" in msg and "ERR-MARK" in msg
    assert "ERR-MARK" in msg.splitlines()[0]  # the CLI shows only this line
