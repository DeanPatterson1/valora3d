"""Phase 6 shared fix A: a per-bake wall-time cap enforced by the bake runner, and stale-lock reclaim.

rigid_scatter measurement bakes held var/bake/.lock ~30 min against a 3 min estimate (2026-09-28), stalling
every lane queued on it. The runner now kills the Blender child at wall_cap_s (the block's measured cost x a
margin, never above the plan's per-sim ceiling), commits nothing, releases the lock and raises BakeTimeout
(code bake_timeout). A holder that dies leaves its Blender child running; the next holder reclaims it."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from engine.bake import lock as bake_lock
from engine.bake import run as bake_run
from engine.bake.lock import machine_lock
from engine.bake.store import BakeStore
from engine.tests.test_bake_stage import MODEL, _checked, drop_script, sim_catalog
from engine.tests.test_director_package import _p


@pytest.fixture(scope="module")
def cat(tmp_path_factory):
    return sim_catalog(tmp_path_factory.mktemp("capcat"))


@pytest.fixture
def lock_path(tmp_path, monkeypatch):
    p = tmp_path / ".lock"
    monkeypatch.setattr(bake_lock, "LOCK_PATH", p)       # never touch the machine's real lock in a unit test
    return p


def _m(method, estimate, cost=None):
    m = {"bake": {"method": method, "estimateS": estimate}, "physics": {}}
    if cost is not None:
        m["physics"]["bakeCostS"] = cost
    return m


def test_the_cap_is_the_measured_cost_times_a_margin_under_the_method_ceiling():
    su, k = bake_run.CAP_STARTUP_S, bake_run.CAP_MARGIN
    assert bake_run.wall_cap_s(_m("gn_disk", 20, cost=9.0)) == pytest.approx(su + k * 20)
    assert bake_run.wall_cap_s(_m("gn_disk", 5, cost=33)) == pytest.approx(su + k * 33)   # measured beats estimate
    assert bake_run.wall_cap_s(_m("rigid_keys", 180, cost=62)) == 600      # rigid_scatter: the ceiling binds
    assert bake_run.wall_cap_s(_m("gas_vdb", 5000)) == 3600
    assert bake_run.wall_cap_s(_m("liquid_abc", 5000)) == 5400
    assert bake_run.wall_cap_s(_m("cloth_pc2", 5000)) == 1200


def test_every_shipped_baked_sim_gets_a_cap_within_its_ceiling():
    from engine.catalog import Catalog
    cat = Catalog.load()
    for bid in cat.ids("sim"):
        m = cat.get("sim", bid)
        if m["bake"]["method"] == "none":
            continue
        cap = bake_run.wall_cap_s(m)
        assert bake_run.CAP_STARTUP_S < cap <= bake_run.BAKE_CAP_S[m["bake"]["method"]], (bid, cap)


def test_plan_bakes_carries_the_cap_and_the_runner_passes_it_as_the_timeout(cat, tmp_path, lock_path):
    s = _checked(drop_script(), cat)
    job = bake_run.plan_bakes(s, _p("sneaker"), MODEL, cat)[0]
    assert job.cap_s == bake_run.wall_cap_s(cat.get("sim", "_test_drop"))
    seen = {}

    def fake(argv, **kw):
        seen["timeout"] = kw["timeout"]
        spec = json.loads(Path(argv[-1]).read_text(encoding="utf-8"))
        (Path(spec["dir"]) / bake_run.REPORT).write_text(json.dumps({"bakeSeconds": 0.1}), encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, "", "")

    bake_run.bake_sims(s, _p("sneaker"), MODEL, catalog=cat, store=BakeStore(tmp_path / "bake"), run=fake,
                       lock_timeout_s=5)
    assert seen["timeout"] == job.cap_s
    st = BakeStore(tmp_path / "bake2")
    bake_run.bake_sims(s, _p("sneaker"), MODEL, catalog=cat, store=st, run=fake, lock_timeout_s=5, timeout_s=7)
    assert seen["timeout"] == 7                                  # a caller's tighter timeout still wins


def test_a_bake_past_its_cap_is_killed_caches_nothing_and_frees_the_lock(cat, tmp_path, lock_path):
    s = _checked(drop_script(), cat)
    st = BakeStore(tmp_path / "bake")

    def hang(argv, **kw):
        raise subprocess.TimeoutExpired(argv, kw["timeout"], output="sim frame 900/1000")

    with pytest.raises(bake_run.BakeTimeout) as e:
        bake_run.bake_sims(s, _p("sneaker"), MODEL, catalog=cat, store=st, run=hang, lock_timeout_s=5)
    assert e.value.code == "bake_timeout" and str(e.value).startswith("bake_timeout:")
    assert "sim frame 900/1000" in str(e.value)
    assert isinstance(e.value, bake_run.BakeFailed)              # existing handlers of BakeFailed still catch it
    assert st.keys() == [] and not list(Path(st.root).glob(".tmp-*"))
    with machine_lock(timeout_s=0.2, path=lock_path):            # released: the next bake can start at once
        pass


SLEEPER = [sys.executable, "-c", "import time; time.sleep(60)"]


def test_run_child_kills_the_child_at_the_timeout_and_records_its_pid(lock_path):
    with machine_lock(timeout_s=0.2, path=lock_path):
        t = time.monotonic()
        with pytest.raises(subprocess.TimeoutExpired):
            bake_run.run_child(SLEEPER, timeout=1.0, lock_path=lock_path)
        assert time.monotonic() - t < 20
        pid = bake_lock._recorded_child(lock_path)
        assert pid and not bake_lock._pid_alive(pid)
        assert bake_lock._holder(lock_path) == os.getpid()       # the holder line is kept


def test_a_dead_holders_orphan_bake_child_is_reclaimed(lock_path, monkeypatch):
    child = subprocess.Popen(SLEEPER)
    try:
        lock_path.write_text(f"999999\nchild {child.pid}\n")
        monkeypatch.setattr(bake_lock, "_image_name", lambda pid: "blender.exe" if pid == child.pid else "")
        with machine_lock(timeout_s=0.2, path=lock_path):
            assert child.wait(timeout=15) is not None            # killed before our bake starts
            assert lock_path.read_text().strip() == str(os.getpid())
    finally:
        child.kill()
        child.wait()


def test_reclaim_spares_a_live_holders_child_and_anything_that_is_not_blender(lock_path, monkeypatch):
    child = subprocess.Popen(SLEEPER)
    try:
        lock_path.write_text(f"{os.getpid()}\nchild {child.pid}\n")          # holder alive: not an orphan
        monkeypatch.setattr(bake_lock, "_image_name", lambda pid: "blender.exe")
        assert bake_lock._reclaim(lock_path) is None
        lock_path.write_text(f"999999\nchild {child.pid}\n")                 # a reused pid that is not Blender
        monkeypatch.setattr(bake_lock, "_image_name", lambda pid: "python.exe")
        assert bake_lock._reclaim(lock_path) is None
        assert child.poll() is None
    finally:
        child.kill()
        child.wait()


def test_image_name_reads_a_live_process():
    assert bake_lock._image_name(os.getpid()).startswith(("python", "py"))
