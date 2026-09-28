import os
import subprocess
import sys
from pathlib import Path

import pytest

from engine.bake import lock as bake_lock
from engine.bake.lock import LOCK_PATH, LockBusy, machine_lock

ROOT = Path(__file__).resolve().parents[2]


def test_lock_path_is_var_bake_under_the_repo_root():
    assert LOCK_PATH == ROOT / "var" / "bake" / ".lock"


def test_second_lock_while_held_is_busy(tmp_path):
    p = tmp_path / ".lock"
    with machine_lock(path=p):
        assert p.read_text().strip() == str(os.getpid())
        with pytest.raises(LockBusy):
            with machine_lock(timeout_s=0.2, path=p):
                pass
    with machine_lock(timeout_s=0.2, path=p):   # released on exit, so it is free again
        pass


def test_a_lock_held_by_another_live_process_is_busy(tmp_path):
    p = tmp_path / ".lock"
    code = ("import sys,time; sys.path.insert(0, r'%s'); from engine.bake.lock import machine_lock\n"
            "with machine_lock(path=r'%s'):\n    print('held', flush=True); time.sleep(30)\n") % (ROOT, p)
    child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "held"
        with pytest.raises(LockBusy):
            with machine_lock(timeout_s=0.2, path=p):
                pass
    finally:
        child.kill()
        child.wait()


def test_a_lock_file_whose_pid_is_dead_is_taken_over(tmp_path, monkeypatch):
    p = tmp_path / ".lock"
    p.write_text("999999\n")
    monkeypatch.setattr(bake_lock, "_pid_alive", lambda pid: False)
    with machine_lock(timeout_s=0.2, path=p):
        assert p.read_text().strip() == str(os.getpid())


def test_pid_alive_reports_self_alive_and_a_bogus_pid_dead():
    assert bake_lock._pid_alive(os.getpid())
    assert not bake_lock._pid_alive(999999)
