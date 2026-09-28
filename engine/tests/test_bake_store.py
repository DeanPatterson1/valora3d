import json
import pytest
from engine.bake.key import bake_key
from engine.bake.store import BakeStore, CacheCorrupt
from engine.bake.window import bake_frames

REF = {"id": "rigid_scatter", "params": {"count": 150}, "startS": 1.0, "endS": 4.0}
ENV = {"seed": 7, "profileKey": "abc", "modelSha": "m1", "blender": "5.0.1", "blockSha": "b1",
       "wind": {"speedMs": 0}, "motion": {"id": "static"}, "ground": "studio"}


def test_key_is_stable_and_ignores_tier_and_key_order():
    k = bake_key(REF, ENV)
    assert k == bake_key(json.loads(json.dumps(REF)), dict(reversed(list(ENV.items()))))
    assert len(k) == 64


@pytest.mark.parametrize("field,val", [("seed", 8), ("blender", "5.2.0"), ("blockSha", "b2"),
                                       ("modelSha", "m2"), ("motion", {"id": "drop_settle"})])
def test_every_input_changes_the_key(field, val):
    assert bake_key(REF, {**ENV, field: val}) != bake_key(REF, ENV)


def test_store_is_atomic_verified_and_prunes_lru(tmp_path):
    st = BakeStore(tmp_path, cap_bytes=3000)
    with st.writer("k1") as w:
        (w.dir / "a.json").write_bytes(b"x" * 1000)
        w.report({"bakeSeconds": 1.5})
    m = st.read("k1")
    assert m["files"]["a.json"]["bytes"] == 1000 and m["bakeSeconds"] == 1.5
    (tmp_path / "k1" / "a.json").write_bytes(b"y" * 1000)      # tamper
    with pytest.raises(CacheCorrupt):
        st.read("k1")
    for k in ("k2", "k3", "k4"):
        with st.writer(k) as w:
            (w.dir / "a.bin").write_bytes(b"z" * 1000)
            w.report({})
    assert not (tmp_path / "k1").exists() and (tmp_path / "k4").exists()   # oldest-read pruned first


def test_a_crashed_writer_leaves_no_cache(tmp_path):
    st = BakeStore(tmp_path)
    with pytest.raises(RuntimeError):
        with st.writer("k") as w:
            (w.dir / "a").write_bytes(b"1")
            raise RuntimeError("bake crashed")
    assert st.read("k") is None


def test_pinned_caches_are_never_pruned(tmp_path):
    st = BakeStore(tmp_path, cap_bytes=1000)
    with st.writer("gold") as w:
        (w.dir / "a").write_bytes(b"g" * 900); w.report({})
    st.pin("gold", reason="golden G1")
    with st.writer("new") as w:
        (w.dir / "a").write_bytes(b"n" * 900); w.report({})
    assert (tmp_path / "gold").exists()


def test_bake_frames_adds_preroll_without_negative_frames():
    # 30 fps clip, sim 1.0-4.0 s, 0.5 s preroll -> the bake scene starts at 1; render frame = bake frame + offset
    r = bake_frames(start_s=1.0, end_s=4.0, fps=30, preroll_s=0.5, max_frames=240)
    assert r.bake_first == 1 and r.clip_first == 31 and r.offset == r.clip_first - r.preroll - 1
    assert r.bake_last - r.bake_first + 1 <= 240
    assert (r.preroll, r.clip_last, r.bake_last, r.offset) == (15, 121, 106, 15)
    assert r.bake_last + r.offset == r.clip_last


def test_gn_sims_bake_on_render_frames_with_preroll_before_the_clip():
    r = bake_frames(start_s=0.0, end_s=2.0, fps=30, preroll_s=0.5, max_frames=240, mode="absolute")
    assert (r.bake_first, r.bake_last, r.offset, r.clip_first) == (-14, 61, 0, 1)


def test_key_normalizes_numbers_and_tuples_without_mutation():
    ref = {**REF, "params": {"count": 150.0, "nested": (-0.0, 1.5)}}
    normalized = {**REF, "params": {"count": 150, "nested": [0, 1.5]}}
    assert bake_key(ref, ENV) == bake_key(normalized, ENV)
    assert isinstance(ref["params"]["nested"], tuple)


def test_key_excludes_only_top_level_tier():
    assert bake_key(REF, {**ENV, "tier": "final"}) == bake_key(REF, ENV)
    assert bake_key({**REF, "tier": "preview"}, ENV) == bake_key(REF, ENV)
    assert bake_key({**REF, "params": {"tier": "final"}}, ENV) != bake_key(REF, ENV)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_key_rejects_nonfinite_numbers(value):
    with pytest.raises(ValueError):
        bake_key({**REF, "params": {"count": value}}, ENV)


def test_key_rejects_non_string_keys():
    with pytest.raises(TypeError):
        bake_key({**REF, "params": {1: "bad"}}, ENV)


def test_params_change_the_key():
    assert bake_key({**REF, "params": {"count": 151}}, ENV) != bake_key(REF, ENV)


def test_key_matches_canonical_json():
    import hashlib
    obj = {"ref": {"name": "caf\u00e9", "n": 1}, "env": {"seed": 0}}
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False)
    assert bake_key(obj["ref"], obj["env"]) == hashlib.sha256(canonical.encode()).hexdigest()


def test_file_hashes_stream_and_combine_in_order(tmp_path):
    import hashlib
    from engine.bake.key import sha256_file, sha256_files
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_bytes(b"abc" * 100)
    b.write_bytes(b"xyz")
    ha = hashlib.sha256(a.read_bytes()).hexdigest()
    hb = hashlib.sha256(b.read_bytes()).hexdigest()
    assert sha256_file(a, chunk=7) == ha
    assert sha256_files([a, b]) == hashlib.sha256((ha + hb).encode("ascii")).hexdigest()
    assert sha256_files([a, b]) != sha256_files([b, a])
    assert sha256_files([]) == hashlib.sha256(b"").hexdigest()


def _write(st, key, data=b"payload"):
    with st.writer(key) as w:
        (w.dir / "a").write_bytes(data)
        w.report({})


def _manifest(st, key):
    return json.loads((st.path(key) / "bake.json").read_text())


def test_writer_is_invisible_until_commit_and_cleans_up(tmp_path):
    import os
    st = BakeStore(tmp_path)
    with st.writer("k-with-hyphens") as w:
        assert w.dir.name.startswith(f".tmp-k-with-hyphens-{os.getpid()}-")
        (w.dir / "a").write_bytes(b"a")
        assert st.read("k-with-hyphens") is None
        assert st.keys() == []
    assert st.read("k-with-hyphens") is not None
    assert not list(tmp_path.glob(".tmp-*"))


def test_size_verification_catches_only_size_changes(tmp_path):
    st = BakeStore(tmp_path)
    _write(st, "k", b"abc")
    (st.path("k") / "a").write_bytes(b"xyz")
    assert st.read("k", verify="size") is not None
    before = (st.path("k") / "bake.json").read_bytes()
    with pytest.raises(CacheCorrupt, match="a"):
        st.read("k")
    assert (st.path("k") / "bake.json").read_bytes() == before
    (st.path("k") / "a").write_bytes(b"longer")
    with pytest.raises(CacheCorrupt, match="a"):
        st.read("k", verify="size")
    assert st.read("k", verify="none") is not None


def test_missing_file_is_corrupt(tmp_path):
    st = BakeStore(tmp_path)
    _write(st, "k")
    (st.path("k") / "a").unlink()
    with pytest.raises(CacheCorrupt, match="a"):
        st.read("k")


@pytest.mark.parametrize("contents", ["{bad", "[]", "{}", '{"schema":"wrong"}'])
def test_invalid_manifest_is_corrupt(tmp_path, contents):
    st = BakeStore(tmp_path)
    _write(st, "k")
    (st.path("k") / "bake.json").write_text(contents)
    with pytest.raises(CacheCorrupt, match="bake.json"):
        st.read("k")


def test_manifest_records_only_relative_posix_paths(tmp_path):
    st = BakeStore(tmp_path)
    with st.writer("k") as w:
        (w.dir / "data").mkdir()
        (w.dir / "data" / "fluid_data_0001.vdb").write_bytes(b"vdb")
        (w.dir / "bake.json").write_text("ignored")
        w.report({"bakeSeconds": 2})
    manifest = st.read("k")
    assert set(manifest["files"]) == {"data/fluid_data_0001.vdb"}
    assert str(tmp_path) not in json.dumps(manifest).replace("\\\\", "\\")
    assert manifest["schema"] == "valora.bake/1" and manifest["key"] == "k"
    assert isinstance(manifest["createdNs"], int)


@pytest.mark.parametrize("key", ["proxy:abc", "../x", "", "a..b", "x/y", "x\\y", ".", "..", "x" * 129])
def test_bad_keys_raise(tmp_path, key):
    st = BakeStore(tmp_path)
    for operation in (st.path, st.read, st.size, st.delete, st.unpin):
        with pytest.raises(ValueError):
            operation(key)
    with pytest.raises(ValueError):
        st.pin(key, "reason")
    with pytest.raises(ValueError):
        with st.writer(key):
            pass


@pytest.mark.parametrize("field", ["schema", "key", "files", "createdNs", "lastRead"])
def test_report_cannot_override_manifest_fields(tmp_path, field):
    st = BakeStore(tmp_path)
    with pytest.raises(ValueError):
        with st.writer("k") as w:
            w.report({field: {}})
    assert st.read("k") is None
    assert not list(tmp_path.glob(".tmp-*"))


def test_report_must_be_json_serializable(tmp_path):
    st = BakeStore(tmp_path)
    with pytest.raises(TypeError):
        with st.writer("k") as w:
            w.report({"bad": object()})
    assert st.read("k") is None
    assert not list(tmp_path.glob(".tmp-*"))


def test_recently_read_old_key_survives_pruning(tmp_path):
    st = BakeStore(tmp_path)
    _write(st, "old")
    _write(st, "new")
    before = _manifest(st, "old")["lastRead"]
    assert st.read("old")["lastRead"] > before
    st.cap_bytes = st.total_bytes() - 1
    assert st.prune() == ["new"]
    assert st.keys() == ["old"]


def test_ticks_strictly_increase_with_frozen_clock(tmp_path, monkeypatch):
    from engine.bake import store
    monkeypatch.setattr(store.time, "time_ns", lambda: 42)
    st = BakeStore(tmp_path)
    _write(st, "k")
    first = _manifest(st, "k")["lastRead"]
    second = st.read("k")["lastRead"]
    third = BakeStore(tmp_path).read("k")["lastRead"]
    assert first < second < third


def test_second_writer_keeps_existing_verified_key(tmp_path):
    st = BakeStore(tmp_path)
    _write(st, "k", b"first")
    created = _manifest(st, "k")["createdNs"]
    _write(st, "k", b"second")
    assert (st.path("k") / "a").read_bytes() == b"first"
    assert st.read("k")["createdNs"] == created
    assert not list(tmp_path.glob(".tmp-*"))


def test_concurrent_writer_keeps_first_commit(tmp_path):
    st = BakeStore(tmp_path)
    with st.writer("k") as later:
        (later.dir / "a").write_bytes(b"later")
        _write(BakeStore(tmp_path), "k", b"first")
    assert (st.path("k") / "a").read_bytes() == b"first"


@pytest.mark.parametrize("corruption", ["size", "manifest", "missing"])
def test_writer_replaces_corrupt_existing_cache(tmp_path, corruption):
    st = BakeStore(tmp_path)
    _write(st, "k")
    if corruption == "size":
        (st.path("k") / "a").write_bytes(b"changed-size")
    elif corruption == "manifest":
        (st.path("k") / "bake.json").write_text("bad")
    else:
        (st.path("k") / "bake.json").unlink()
    _write(st, "k", b"replacement")
    assert st.read("k")["files"]["a"]["bytes"] == len(b"replacement")


def test_unpin_allows_pruning_and_missing_pin_raises(tmp_path):
    st = BakeStore(tmp_path)
    with pytest.raises(KeyError):
        st.pin("missing", "no cache")
    _write(st, "gold")
    st.pin("gold", "golden G1")
    pins = BakeStore(tmp_path).pins()
    assert pins["gold"]["reason"] == "golden G1"
    assert isinstance(pins["gold"]["pinnedNs"], int)
    st.cap_bytes = 0
    assert st.prune() == []
    st.unpin("gold")
    assert st.pins() == {}
    assert st.prune() == ["gold"]


def test_prune_removes_dead_temps_but_retains_live_and_own(tmp_path, monkeypatch):
    import os
    from engine.bake import lock
    st = BakeStore(tmp_path)
    dead = tmp_path / ".tmp-k-999999999-ab"
    own = tmp_path / f".tmp-k-with-hyphens-{os.getpid()}-ab"
    live = tmp_path / ".tmp-k-123-ab"
    for path in (dead, own, live):
        path.mkdir()
    monkeypatch.setattr(lock, "_pid_alive", lambda pid: pid == 123)
    assert st.prune() == []
    assert not dead.exists() and own.exists() and live.exists()


def test_prune_invalid_manifest_first_and_breaks_ties_by_key(tmp_path):
    st = BakeStore(tmp_path)
    for key in ("z", "b", "a"):
        _write(st, key)
        manifest = _manifest(st, key)
        manifest["lastRead"] = 100
        (st.path(key) / "bake.json").write_text(json.dumps(manifest))
    (st.path("z") / "bake.json").write_text("bad")
    st.cap_bytes = 0
    assert st.prune() == ["z", "a", "b"]


def test_keys_and_sizes_include_only_committed_directories(tmp_path):
    st = BakeStore(tmp_path)
    _write(st, "k")
    (tmp_path / "loose").mkdir()
    (tmp_path / ".tmp-k-999999999-ab").mkdir()
    (tmp_path / ".tmp-k-999999999-ab" / "bake.json").write_text("{}")
    (tmp_path / ".lock").write_text("123")
    st.pin("k", "keep")
    expected = sum(p.stat().st_size for p in st.path("k").rglob("*") if p.is_file())
    assert st.keys() == ["k"]
    assert st.size("k") == expected and st.total_bytes() == expected


def test_delete_and_crashed_writer_handle_read_only_files(tmp_path):
    import stat
    st = BakeStore(tmp_path)
    _write(st, "k")
    (st.path("k") / "a").chmod(stat.S_IREAD)
    st.delete("k")
    assert not st.path("k").exists()
    with pytest.raises(RuntimeError):
        with st.writer("crash") as w:
            file = w.dir / "a"
            file.write_bytes(b"a")
            file.chmod(stat.S_IREAD)
            raise RuntimeError("crashed")
    assert not list(tmp_path.glob(".tmp-*"))


def test_environment_sets_default_root_and_capacity(tmp_path, monkeypatch):
    monkeypatch.setenv("VALORA_BAKE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setenv("VALORA_BAKE_CACHE_GB", "0.5")
    st = BakeStore()
    assert st.root == tmp_path / "cache" and st.cap_bytes == 0.5 * (1 << 30)
    explicit = BakeStore(tmp_path, cap_bytes=123)
    assert explicit.root == tmp_path and explicit.cap_bytes == 123


@pytest.mark.parametrize("mode", ["shift", "absolute"])
def test_truncation_keeps_preroll(mode):
    from engine.bake.window import bake_frame, render_frame
    r = bake_frames(1.0, 4.0, 30, 0.5, 50, mode=mode)
    assert r.bake_last - r.bake_first + 1 == 50
    assert r.truncated and r.preroll == 15 and r.clip_last == 65
    assert render_frame(r, r.bake_last) == r.clip_last
    assert bake_frame(r, r.clip_first) == r.bake_first + r.preroll


@pytest.mark.parametrize("kwargs", [
    {"end_s": 1.0}, {"end_s": 0.0}, {"fps": 0}, {"fps": -30},
    {"max_frames": 0}, {"preroll_s": -0.5}, {"max_frames": 15}, {"mode": "bad"},
])
def test_invalid_windows_raise(kwargs):
    args = dict(start_s=1.0, end_s=4.0, fps=30, preroll_s=0.5, max_frames=240)
    with pytest.raises(ValueError):
        bake_frames(**{**args, **kwargs})


def test_zero_preroll_and_fractional_end_rounding():
    r = bake_frames(0.0, 0.101, 30, 0.0, 5)
    assert (r.preroll, r.clip_first, r.clip_last, r.bake_last) == (0, 1, 5, 5)
    assert not r.truncated and r.mode == "shift"


def test_method_modes_match_formats_and_gn_is_absolute():
    from engine.bake.formats import FORMATS
    from engine.bake.window import MODE_FOR_METHOD, bake_frames_for
    assert set(MODE_FOR_METHOD) == set(FORMATS)
    for method, mode in MODE_FOR_METHOD.items():
        r = bake_frames_for(method, 0, 2, 30, 0.5, 240)
        assert r.mode == mode
        assert (mode == "absolute") == (method == "gn_disk")
    assert bake_frames_for("gn_disk", 0, 2, 30, 0.5, 240).bake_first == -14
    with pytest.raises(ValueError):
        bake_frames_for("unknown", 0, 2, 30, 0.5, 240)


def test_a_bake_is_never_pruned_by_its_own_write(tmp_path):
    # the compile reads the bake right after it is written; over the cap, older unpinned keys go instead
    st = BakeStore(tmp_path, cap_bytes=500)
    with st.writer("old") as w:
        (w.dir / "a").write_bytes(b"o" * 900); w.report({})
    assert st.keys() == ["old"]
    with st.writer("new") as w:
        (w.dir / "a").write_bytes(b"n" * 900); w.report({})
    assert st.keys() == ["new"] and st.read("new") is not None
