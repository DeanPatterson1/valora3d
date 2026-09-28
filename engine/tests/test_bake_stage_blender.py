"""Phase 6 Task 98: stage 4b BAKE end to end on the test-only sim/_test_drop (one Bullet cube onto the sneaker's
closed shell). Bakes into a temp BakeStore (VALORA_BAKE_ROOT), then compiles without rendering. Serial: bakes
take the machine lock."""
import json
import subprocess

import pytest

from engine.bake import run as bake_run
from engine.bake.store import BakeStore
from engine.compiler.run import compile_scene
from engine.tests.conftest import requires_blender
from engine.tests.test_bake_stage import MODEL, drop_script, sim_catalog
from engine.tests.test_director_package import _p

pytestmark = [pytest.mark.blender, requires_blender]


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("bakestage")
    mp = pytest.MonkeyPatch()
    mp.setenv("VALORA_BAKE_ROOT", str(tmp / "bake"))
    cat = sim_catalog(tmp)
    first = bake_run.bake_sims(drop_script(), _p("sneaker"), MODEL, catalog=cat, lock_timeout_s=600)
    yield {"tmp": tmp, "cat": cat, "first": first, "store": BakeStore(tmp / "bake")}
    mp.undo()


def test_bake_writes_a_verified_cache_with_keys_and_timing(env):
    e = env["first"]["_test_drop"]
    assert e["fromCache"] is False
    m = env["store"].read(e["key"])
    assert "keys.json" in m["files"] and m["bakeSeconds"] > 0
    assert m["proxy"]["shell"]["watertight"] and m["blender"].startswith("5.0.1")
    keys = json.loads((env["store"].path(e["key"]) / "keys.json").read_text(encoding="utf-8"))
    rows = keys["pieces"]["cube"]
    assert len(rows) == e["frames"]["bake_last"] - e["frames"]["bake_first"] + 1
    zs = [r[2] for r in rows]
    assert zs[-1] < zs[0] and zs[-1] > 0.0                       # it fell and came to rest above the ground
    assert any(p.startswith("proxy-") for p in env["store"].keys())   # the shell is cached under its own key


def test_a_second_bake_is_a_cache_hit_with_no_blender(env):
    calls = []
    out = bake_run.bake_sims(drop_script(), _p("sneaker"), MODEL, catalog=env["cat"],
                             run=lambda *a, **k: calls.append(a))
    assert calls == [] and out["_test_drop"]["fromCache"] is True
    assert out["_test_drop"]["key"] == env["first"]["_test_drop"]["key"]


def test_the_compile_keys_the_cube_from_the_cache_and_never_simulates(env):
    out = env["tmp"] / "compile"
    res = compile_scene(drop_script(), _p("sneaker"), MODEL, out, catalog=env["cat"], render=False, frames=[1],
                        probe=[20, 60])
    e = env["first"]["_test_drop"]
    assert res["sims"]["_test_drop"] == {"key": e["key"], "frames": e["frames"], "fromCache": True}
    assert "sim:_test_drop" in res["built"]
    cube = [o for o in res["objects"] if o["block"] == "sim/_test_drop"]
    assert len(cube) == 1
    assert not any(o["block"] and str(o["block"]).startswith("proxy/") for o in res["objects"])   # proxies stay in the bake


def test_a_missing_cache_fails_the_compile_and_is_never_rebaked(env):
    st, key = env["store"], env["first"]["_test_drop"]["key"]
    d = st.path(key)
    moved = d.with_name(d.name + ".moved")
    d.rename(moved)
    try:
        with pytest.raises(RuntimeError) as err:
            compile_scene(drop_script(), _p("sneaker"), MODEL, env["tmp"] / "compile2", catalog=env["cat"],
                          render=False, frames=[1], bakes={"_test_drop": env["first"]["_test_drop"]})
        assert "BakeMissing" in str(err.value) or "missing" in str(err.value)
    finally:
        moved.rename(d)
