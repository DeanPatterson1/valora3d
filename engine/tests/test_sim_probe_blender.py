"""Phase 6 Task 99: compile.json.simProbe on the _test_drop fixture (good) and on a synthetic bad cache (a piece
inside the shell and one NaN frame). Report-only: the bad cache still compiles, and the probe says why it is bad."""
import copy
import json
import math

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
    tmp = tmp_path_factory.mktemp("simprobe")
    mp = pytest.MonkeyPatch()
    mp.setenv("VALORA_BAKE_ROOT", str(tmp / "bake"))
    cat = sim_catalog(tmp)
    bakes = bake_run.bake_sims(drop_script(), _p("sneaker"), MODEL, catalog=cat, lock_timeout_s=600)
    yield {"tmp": tmp, "cat": cat, "bakes": bakes, "store": BakeStore(tmp / "bake")}
    mp.undo()


def _compile(env, bakes, name):
    return compile_scene(drop_script(), _p("sneaker"), MODEL, env["tmp"] / name, catalog=env["cat"], render=False,
                         frames=[1], bakes=bakes)


def test_a_good_bake_passes_every_probe(env):
    res = _compile(env, env["bakes"], "good")
    p = res["simProbe"]["_test_drop"]
    assert p["reportOnly"] and p["method"] == "rigid_keys"
    assert p["inside"]["ok"] and p["inside"]["points"] > 0, p
    assert p["stable"]["finite"] and p["stable"]["ok"], p
    assert p["velocityPresent"] is True
    assert p["bakeSeconds"] > 0 and p["cacheBytes"] > 0


def test_a_bad_cache_is_reported_not_failed(env):
    st, good = env["store"], env["bakes"]["_test_drop"]
    src = st.path(good["key"])
    man = st.read(good["key"])
    keys = json.loads((src / "keys.json").read_text(encoding="utf-8"))
    rows = keys["pieces"]["cube"]
    c = _p("sneaker").center                               # a shoe is hollow: its bbox centre is air, the sole is not
    for f in range(len(rows) // 2, len(rows)):             # the cube sits inside the sole for half the clip
        rows[f][:3] = [c[0], c[1], 0.006]
    rows[5][0] = math.nan                                   # and one NaN frame
    bad_key = "b" * 64
    with st.writer(bad_key) as w:
        (w.dir / "keys.json").write_text(json.dumps(keys), encoding="utf-8")
        w.report({k: v for k, v in man.items() if k not in ("schema", "key", "files", "createdNs", "lastRead")})
    bakes = copy.deepcopy(env["bakes"])
    bakes["_test_drop"].update(key=bad_key, dir=str(st.path(bad_key)))
    p = _compile(env, bakes, "bad")["simProbe"]["_test_drop"]
    assert p["inside"]["ok"] is False and p["inside"]["share"] > 0.001, p
    assert p["stable"]["finite"] is False and p["stable"]["ok"] is False, p
