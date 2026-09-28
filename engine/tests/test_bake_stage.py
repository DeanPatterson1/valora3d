"""Phase 6 Task 98: stage 4b BAKE, the pure parts. The fixture catalog is the shipped one plus the test-only
sim/_test_drop (engine/tests/fixtures/catalog_sim), so no shipped block is needed."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from engine.bake import run as bake_run
from engine.bake.key import sha256_file, sha256_files
from engine.bake.run import bake_env, plan_bakes
from engine.bake.store import BakeStore
from engine.blender_pin import PINNED_BLENDER
from engine.catalog import BLOCKS_DIR, Catalog
from engine.checker import check
from engine.compiler import run as compile_run
from engine.director.baseline_phase3 import profile_key
from engine.tests.test_director_package import _p

HERE = Path(__file__).parent
FIX = HERE / "fixtures"
SIM_FIX = FIX / "catalog_sim"
ROOT = HERE.parents[1]
MODEL = ROOT / "assets-in" / "models" / "sneaker" / "sneaker.glb"


def sim_catalog(tmp):
    root = Path(tmp) / "catalog"
    ign = shutil.ignore_patterns("__pycache__")
    shutil.copytree(BLOCKS_DIR, root, ignore=ign)
    for kind_dir in (p for p in SIM_FIX.iterdir() if p.is_dir()):
        for b in (p for p in kind_dir.iterdir() if p.is_dir()):
            shutil.copytree(b, root / kind_dir.name / b.name, ignore=ign)
    return Catalog.load(root)


def drop_script(start=0.5, end=2.5, sims=True):
    s = json.loads((FIX / "script_valid.json").read_text(encoding="utf-8"))
    s["format"]["durationS"] = 10
    if sims:
        s["sims"] = [{"id": "_test_drop", "params": {}, "startS": start, "endS": end}]
    return s


@pytest.fixture(scope="module")
def cat(tmp_path_factory):
    return sim_catalog(tmp_path_factory.mktemp("simcat"))


def _checked(s, cat):
    r = check(s, _p("sneaker"), cat)
    assert r.ok, [i for i in r.issues if i.severity == "error"]
    return r.script


def test_plan_bakes_one_job_per_baked_sim(cat):
    s = _checked(drop_script(), cat)
    jobs = plan_bakes(s, _p("sneaker"), MODEL, cat)
    assert [j.ref_id for j in jobs] == ["_test_drop"]
    j = jobs[0]
    assert len(j.key) == 64 and j.method == "rigid_keys" and j.estimate_s == 30 and j.proxies == ["shell"]
    assert (j.frames["bake_first"], j.frames["clip_first"], j.frames["preroll"]) == (1, 16, 0)


def test_no_sims_no_bakes(cat):
    assert plan_bakes(_checked(drop_script(sims=False), cat), _p("sneaker"), MODEL, cat) == []


def test_the_key_env_carries_profile_model_blender_and_block_sources(cat):
    s = _checked(drop_script(), cat)
    env = bake_env(s, _p("sneaker"), sha256_file(MODEL), cat, s["sims"][0])
    d = Path(cat.root) / "sim" / "_test_drop"
    assert env["profileKey"] == profile_key(_p("sneaker"))
    assert env["modelSha"] == sha256_file(MODEL) and env["blender"] == PINNED_BLENDER
    from engine.bake.deps import bake_sources
    assert bake_sources(d)[:2] == [d / "bake.py", d / "build.py"]
    assert env["blockSha"] == sha256_files(bake_sources(d))
    assert "tier" not in env


def test_editing_the_block_source_changes_the_key(tmp_path):
    c = sim_catalog(tmp_path)
    s = _checked(drop_script(), c)
    k1 = plan_bakes(s, _p("sneaker"), MODEL, c)[0].key
    f = Path(c.root) / "sim" / "_test_drop" / "build.py"
    f.write_text(f.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    assert plan_bakes(s, _p("sneaker"), MODEL, c)[0].key != k1


def test_a_cache_hit_starts_no_blender(cat, tmp_path):
    s = _checked(drop_script(), cat)
    st = BakeStore(tmp_path / "bake")
    key = plan_bakes(s, _p("sneaker"), MODEL, cat)[0].key
    with st.writer(key) as w:
        (w.dir / "keys.json").write_text("{}", encoding="utf-8")
        w.report({"bakeSeconds": 1.0})
    calls = []
    out = bake_run.bake_sims(s, _p("sneaker"), MODEL, catalog=cat, store=st, run=lambda *a, **k: calls.append(a))
    assert calls == [] and out["_test_drop"]["fromCache"] is True and out["_test_drop"]["key"] == key


def test_a_miss_runs_one_blender_under_the_budget_and_commits(cat, tmp_path):
    from harness.budget import BakeBudget
    s = _checked(drop_script(), cat)
    st = BakeStore(tmp_path / "bake")
    calls = []

    def fake(argv, **kw):
        calls.append(argv)
        spec = json.loads(Path(argv[-1]).read_text(encoding="utf-8"))
        (Path(spec["dir"]) / "keys.json").write_text("{}", encoding="utf-8")
        (Path(spec["dir"]) / bake_run.REPORT).write_text(json.dumps({"bakeSeconds": 0.5}), encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, "", "")

    b = BakeBudget()
    out = bake_run.bake_sims(s, _p("sneaker"), MODEL, catalog=cat, store=st, budget=b, run=fake,
                             lock_timeout_s=5)
    assert len(calls) == 1 and out["_test_drop"]["fromCache"] is False
    assert b.used_s == 30
    m = st.read(out["_test_drop"]["key"])
    assert m["bakeSeconds"] == 0.5 and "keys.json" in m["files"] and "bake_report.json" not in m["files"]
    assert m["ref"]["id"] == "_test_drop"


def test_a_failed_bake_leaves_no_cache(cat, tmp_path):
    s = _checked(drop_script(), cat)
    st = BakeStore(tmp_path / "bake")
    fail = lambda argv, **kw: subprocess.CompletedProcess(argv, 1, "boom", "")  # noqa: E731
    with pytest.raises(bake_run.BakeFailed):
        bake_run.bake_sims(s, _p("sneaker"), MODEL, catalog=cat, store=st, run=fail, lock_timeout_s=5)
    assert st.keys() == []


def _fake_compile(monkeypatch, tmp_path):
    seen = {}

    def fake(argv, **kw):
        job = json.loads(Path(argv[-1]).read_text(encoding="utf-8"))
        seen["job"] = job
        Path(job["out"], "compile.json").write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, "", "")
    monkeypatch.setattr(compile_run.subprocess, "run", fake)
    return seen


def test_a_script_without_sims_compiles_exactly_as_before(cat, tmp_path, monkeypatch):
    seen = _fake_compile(monkeypatch, tmp_path)
    compile_run.compile_scene(drop_script(sims=False), _p("sneaker"), MODEL, tmp_path / "out", catalog=cat,
                              render=False)
    assert "bakes" not in seen["job"]


def test_compile_bakes_first_and_passes_the_manifests(cat, tmp_path, monkeypatch):
    seen = _fake_compile(monkeypatch, tmp_path)
    given = {"_test_drop": {"key": "k" * 64, "dir": "x", "frames": {}, "method": "rigid_keys", "fromCache": True}}
    compile_run.compile_scene(drop_script(), _p("sneaker"), MODEL, tmp_path / "out", catalog=cat, render=False,
                              bakes=given)
    assert seen["job"]["bakes"] == given


def test_preview_and_final_share_one_key(cat):
    s = _checked(drop_script(), cat)
    k = plan_bakes(s, _p("sneaker"), MODEL, cat)[0].key
    assert plan_bakes(json.loads(json.dumps(s)), _p("sneaker"), MODEL, cat)[0].key == k   # no tier input at all


def test_look_defaults_to_before_peak_and_settled_for_a_sim(tmp_path):
    from harness.look import run_look
    f = tmp_path / "s.json"
    f.write_text(json.dumps(drop_script(0.5, 2.5)), encoding="utf-8")
    plan = run_look(f, "sneaker", frames=3, dry_run=True)
    assert plan["times"] == [0.5, 1.5, 2.3] and plan["frames"] == [16, 46, 70]
    assert run_look(f, "sneaker", frames=1, dry_run=True)["times"] == [1.5]


def test_engine_bake_cli_reports_a_check_failure(tmp_path, capsys):
    from engine.__main__ import EXIT_CHECK_FAILED, main
    s = drop_script()
    s["sims"][0]["id"] = "no_such_sim"
    f = tmp_path / "s.json"
    f.write_text(json.dumps(s), encoding="utf-8")
    prof = HERE / "fixtures" / "profiles" / "sneaker.json"
    assert main(["bake", "--script", str(f), "--profile", str(prof), "--model", str(MODEL)]) == EXIT_CHECK_FAILED
