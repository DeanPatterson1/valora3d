import json
import threading

import pytest

from engine.director.direction import AXES, Direction, direction_of
from engine.director.memory import MAX_ENTRIES, MemoryBusy, VarietyMemory

AX = {"world": "studio_cyc", "mood": "clean", "tone": "white", "pace": "calm", "opener": "arc_orbit",
      "weather": "dry", "wind": "calm"}
KNOWN = {"world": ["studio_cyc"], "mood": ["clean", "vivid", "noir", "teal_night", "warm_golden", "premium_dark"],
         "tone": ["white", "grey", "black"], "pace": ["calm", "medium", "hype"], "opener": ["low_hero_push", "arc_orbit"],
         "weather": ["dry", "rain"], "wind": ["calm", "windy"]}
S = "0123456789abcdef"


def _d(mood="clean"):
    return direction_of({**AX, "mood": mood}, "dice")


@pytest.fixture
def mem(tmp_path, monkeypatch):
    monkeypatch.delenv("VALORA_VARIETY_SECRET", raising=False)
    monkeypatch.setenv("VALORA_VARIETY_DEV", "1")
    return VarietyMemory(tmp_path / "mem")


def test_tokens_are_signed_and_fabrications_rejected(mem):
    a = mem.issue_user_token()
    assert a != mem.issue_user_token() and mem.valid_token(a)
    body, tag = a.rsplit(".", 1)
    assert not mem.valid_token(body + "." + ("A" if tag[0] != "A" else "B") + tag[1:])     # altered tag
    assert not mem.valid_token("u_" + "x" * 32 + "." + "y" * 22)                          # fabricated
    other = VarietyMemory(mem.root.parent / "other")                                     # other secret
    assert not other.valid_token(a)
    with pytest.raises(ValueError):
        mem.recent("u_" + "x" * 32 + "." + "y" * 22, S)


def test_secret_env_is_used_and_key_file_is_32_bytes(mem, monkeypatch, tmp_path):
    a = mem.issue_user_token()
    assert len((mem.root / ".secret").read_bytes()) == 32
    monkeypatch.setenv("VALORA_VARIETY_SECRET", "x" * 32)
    env_a, env_b = VarietyMemory(tmp_path / "e1"), VarietyMemory(tmp_path / "e2")
    t = env_a.issue_user_token()
    assert env_b.valid_token(t) and not env_a.valid_token(a)
    assert not (tmp_path / "e1" / ".secret").exists()


@pytest.mark.parametrize("bad", ["../../etc/passwd", "u_../../x", "", None, 7, "u_" + "a" * 32 + ".." + "b" * 21])
def test_path_traversal_and_junk_tokens_rejected(mem, bad):
    assert not mem.valid_token(bad)
    with pytest.raises(ValueError):
        mem.recent(bad, S)
    with pytest.raises(ValueError):
        mem.forget(bad)


@pytest.mark.parametrize("subject", ["../x", "ABCDEF0123456789", "0123", "s_../../../../etc", None])
def test_bad_subject_keys_rejected(mem, subject):
    u = mem.issue_user_token()
    with pytest.raises(ValueError):
        mem.recent(u, subject)


def test_record_and_recent_in_order(mem):
    u = mem.issue_user_token()
    mem.record(u, S, _d("clean"), seed=1, duration_s=10, known=KNOWN)
    mem.record(u, S, _d("vivid"), seed=2, duration_s=8, known=KNOWN)
    assert mem.recent(u, S) == [_d("clean").id, _d("vivid").id]


@pytest.mark.parametrize("bad", [
    direction_of({**AX, "mood": "call_me_555_1234"}, "dice"),                   # value not in the catalog
    Direction("free text id", "clean", "calm", "white", "dice", "studio_cyc", "arc_orbit"),  # id != axes
    direction_of(AX, "hacker"),                                                  # source not in the enum
])
def test_only_validated_records_are_stored(mem, bad):
    u = mem.issue_user_token()
    with pytest.raises(ValueError):
        mem.record(u, S, bad, seed=1, duration_s=10, known=KNOWN)
    with pytest.raises(ValueError):
        mem.record(u, S, _d(), seed=-1, duration_s=10, known=KNOWN)
    with pytest.raises(ValueError):
        mem.dislike(u, S, {"mood": ["my name is alice"]}, known=KNOWN)
    assert not [p for p in mem.root.rglob("*.json")]


def test_files_hold_no_raw_ids_and_only_known_fields(mem):
    u = mem.issue_user_token()
    mem.record(u, S, _d(), seed=1, duration_s=10, known=KNOWN)
    assert not any(u in p.name or S in p.name for p in mem.root.rglob("*"))
    doc = json.loads(next(mem.root.rglob("*.json")).read_text(encoding="utf-8"))
    assert set(doc["entries"][0]) == {"id", "seed", "durationS", "source", "day"}


def test_stored_junk_is_filtered_on_read(mem):
    u = mem.issue_user_token()
    mem.record(u, S, _d(), seed=1, duration_s=10, known=KNOWN)
    mem.dislike(u, S, {"mood": ["vivid"]}, known=KNOWN)
    p = next(mem.root.rglob("*.json"))
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["entries"].append({"id": "a/b"})
    doc["dislikes"]["evil"] = ["x"]
    doc["dislikes"]["mood"].append(123)
    p.write_text(json.dumps(doc), encoding="utf-8")
    assert mem.recent(u, S) == [_d().id]
    assert mem.avoided(u, S) == {"mood": ["vivid"]}


def test_dislikes_are_merged_and_capped(mem):
    import engine.director.memory as mm
    u = mem.issue_user_token()
    for m in ["clean", "vivid", "noir", "teal_night", "vivid"]:
        mem.dislike(u, S, {"mood": [m]}, known=KNOWN)
    got = mem.avoided(u, S)["mood"]
    assert len(got) == mm.MAX_DISLIKES_PER_AXIS and got[-1] == "vivid" and len(set(got)) == len(got)


def test_entries_capped_and_corrupt_or_oversized_file_reads_empty(mem, monkeypatch):
    import engine.director.memory as mm
    u = mem.issue_user_token()
    for i in range(MAX_ENTRIES + 3):
        mem.record(u, S, _d(), seed=i, duration_s=10, known=KNOWN)
    p = next(mem.root.rglob("*.json"))
    assert len(json.loads(p.read_text(encoding="utf-8"))["entries"]) == MAX_ENTRIES   # the log is bounded
    assert mem.recent(u, S) == [_d().id]                                            # rotation: one id
    assert p.stat().st_size < mm.MAX_FILE_BYTES
    monkeypatch.setattr(mm, "MAX_FILE_BYTES", 10)
    assert mem.recent(u, S) == []
    monkeypatch.undo()
    p.write_text("{not json", encoding="utf-8")
    assert mem.recent(u, S) == []


def test_lock_serializes_read_modify_write_across_threads(mem):
    u, errors = mem.issue_user_token(), []

    def worker():
        try:
            with mem.locked(u, S):
                n = len(mem._load(u, S)["entries"])     # the log; recent() is the rotation order
                mem.record(u, S, _d(), seed=n, duration_s=10, known=KNOWN)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    ts = [threading.Thread(target=worker) for _ in range(12)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors
    seeds = [e["seed"] for e in json.loads(next(mem.root.rglob("*.json")).read_text(encoding="utf-8"))["entries"]]
    assert seeds == list(range(12))


def test_a_live_lock_is_never_broken_and_busy_times_out(mem, monkeypatch):
    import os

    import engine.director.memory as mm
    monkeypatch.setattr(mm, "LOCK_TIMEOUT_S", 0.2)
    u = mem.issue_user_token()
    with mem.locked(u, S):
        lock = next(p for p in mem.root.rglob("*.lock"))
        os.utime(lock, (0, 0))                     # looks ancient: must still NOT be evicted
        with pytest.raises(MemoryBusy):
            with mem.locked(u, S):
                pass


def test_a_live_lock_held_by_another_process_is_busy(mem, monkeypatch):
    import subprocess
    import sys

    import engine.director.memory as mm
    monkeypatch.setattr(mm, "LOCK_TIMEOUT_S", 0.3)
    u = mem.issue_user_token()
    code = ("import sys, time; from engine.director.memory import VarietyMemory; m = VarietyMemory(sys.argv[1]);"
            "cm = m.locked(sys.argv[2], sys.argv[3]); cm.__enter__(); print('held', flush=True);"
            "sys.stdin.readline()")
    p = subprocess.Popen([sys.executable, "-c", code, str(mem.root), u, S], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, text=True)
    try:
        assert p.stdout.readline().strip() == "held"
        with pytest.raises(MemoryBusy):
            with mem.locked(u, S):
                pass
    finally:
        p.communicate("\n", timeout=30)


def test_lock_is_released_when_the_holder_process_dies(mem):
    import subprocess
    import sys
    u = mem.issue_user_token()
    code = ("import sys, os; from engine.director.memory import VarietyMemory; m = VarietyMemory(sys.argv[1]);"
            "cm = m.locked(sys.argv[2], sys.argv[3]); cm.__enter__(); os._exit(0)")
    subprocess.run([sys.executable, "-c", code, str(mem.root), u, S], check=True)
    with mem.locked(u, S):                         # the OS released the dead holder's lock
        pass


def test_forget_deletes_one_user(mem):
    u, v = mem.issue_user_token(), mem.issue_user_token()
    mem.record(u, S, _d(), seed=1, duration_s=10, known=KNOWN)
    mem.record(v, S, _d(), seed=1, duration_s=10, known=KNOWN)
    mem.forget(u)
    assert mem.recent(u, S) == [] and mem.recent(v, S) != []
    assert set(AXES) == set(KNOWN)


# ---- chunk 3 review: secret, forget, stored fields, rotation beyond the log, lock churn ----

def test_production_needs_a_long_secret_and_never_creates_a_key_file(tmp_path, monkeypatch):
    from engine.director.memory import SecretMissing
    monkeypatch.delenv("VALORA_VARIETY_SECRET", raising=False)
    monkeypatch.delenv("VALORA_VARIETY_DEV", raising=False)
    with pytest.raises(SecretMissing):
        VarietyMemory(tmp_path / "p").issue_user_token()
    assert not (tmp_path / "p" / ".secret").exists()
    monkeypatch.setenv("VALORA_VARIETY_SECRET", "x" * 31)
    with pytest.raises(SecretMissing):
        VarietyMemory(tmp_path / "p").issue_user_token()
    monkeypatch.setenv("VALORA_VARIETY_SECRET", "x" * 32)
    assert VarietyMemory(tmp_path / "p").issue_user_token()
    monkeypatch.delenv("VALORA_VARIETY_SECRET")
    assert VarietyMemory(tmp_path / "d", dev=True).issue_user_token()                  # explicit dev root


def test_dev_key_file_is_owner_only(mem):
    import os
    import sys

    import engine.director.memory as mm
    mem.issue_user_token()
    key = mem.root / ".secret"
    if sys.platform == "win32":
        import subprocess
        who = subprocess.run([mm._sys32("whoami.exe")], capture_output=True, text=True, check=True).stdout
        assert mm._acl(key) == [who.strip().lower()]                   # one ACE, the owner; nothing inherited
    else:
        assert os.stat(key).st_mode & 0o077 == 0


def test_concurrent_first_initialisation_agrees_on_one_key(tmp_path, monkeypatch):
    monkeypatch.delenv("VALORA_VARIETY_SECRET", raising=False)
    monkeypatch.setenv("VALORA_VARIETY_DEV", "1")
    root, keys, errors = tmp_path / "race", [], []
    gate = threading.Barrier(8)

    def worker():
        try:
            gate.wait()
            keys.append(VarietyMemory(root)._key_bytes())
        except Exception as e:  # noqa: BLE001
            errors.append(e)
    ts = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors and len(keys) == 8 and len(set(keys)) == 1
    assert (root / ".secret").read_bytes() == keys[0] and not list(root.glob(".secret-*.tmp"))


def test_forget_holds_the_user_lock_outside_the_deleted_directory(mem):
    u = mem.issue_user_token()
    mem.record(u, S, _d(), seed=1, duration_s=10, known=KNOWN)
    lock = mem._lock_path(u)
    assert mem._dir(u) not in lock.parents
    mem.forget(u)
    assert not mem._dir(u).exists() and lock.parent.exists()
    mem.forget(u)                                                      # nothing stored: a no-op


def test_forget_surfaces_deletion_failures(mem, monkeypatch):
    import engine.director.memory as mm
    u = mem.issue_user_token()
    mem.record(u, S, _d(), seed=1, duration_s=10, known=KNOWN)

    def denied(*a, **k):
        raise PermissionError("in use")
    monkeypatch.setattr(mm.shutil, "rmtree", denied)
    with pytest.raises(OSError):
        mem.forget(u)


def test_concurrent_forget_and_write(mem):
    u, errors = mem.issue_user_token(), []

    def writer(k):
        try:
            for i in range(15):
                with mem.locked(u, S):
                    mem.record(u, S, _d(), seed=k * 100 + i, duration_s=10, known=KNOWN)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    def forgetter():
        try:
            for _ in range(15):
                mem.forget(u)
        except Exception as e:  # noqa: BLE001
            errors.append(e)
    ts = [threading.Thread(target=writer, args=(k,)) for k in range(3)] + [threading.Thread(target=forgetter)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors
    for p in mem.root.rglob("*.json"):                                 # whatever survived is whole
        assert json.loads(p.read_text(encoding="utf-8"))["entries"]
    mem.forget(u)
    assert mem.recent(u, S) == [] and not mem._dir(u).exists()


def test_stored_records_are_rebuilt_from_validated_fields(mem):
    u = mem.issue_user_token()
    mem.record(u, S, _d(), seed=1, duration_s=10, known=KNOWN)
    p = next(mem.root.rglob("*.json"))
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["entries"][0]["note"] = "call me"                              # unknown field
    doc["entries"].append({**doc["entries"][0], "seed": "1"})         # bad type -> dropped
    doc["entries"].append({**doc["entries"][0], "source": "hacker"})
    doc["used"]["x/y"] = 3
    p.write_text(json.dumps(doc), encoding="utf-8")
    mem.record(u, S, _d("vivid"), seed=2, duration_s=10, known=KNOWN)
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert [set(e) for e in doc["entries"]] == [{"id", "seed", "durationS", "source", "day"}] * 2
    assert set(doc["used"]) == {_d().id, _d("vivid").id}


def test_dislikes_are_filtered_against_the_current_catalog(mem):
    u = mem.issue_user_token()
    mem.dislike(u, S, {"mood": ["vivid", "noir"]}, known=KNOWN)
    assert mem.avoided(u, S) == {"mood": ["vivid", "noir"]}
    now = {**KNOWN, "mood": [m for m in KNOWN["mood"] if m != "noir"]}  # 'noir' left the catalog
    assert mem.avoided(u, S, known=now) == {"mood": ["vivid"]}
    assert mem.avoided(u, S, known={**KNOWN, "mood": ["clean"]}) == {}


def test_rotation_covers_a_pool_larger_than_the_entry_log(mem):
    from engine.director.dice import candidates, roll
    from engine.director.direction import make_id
    u = mem.issue_user_token()
    pool = {make_id(c) for c in candidates(KNOWN)}
    assert len(pool) > MAX_ENTRIES
    got = []
    for seed in range(len(pool) + 3):
        r = roll(seed, KNOWN, history=mem.recent(u, S))
        mem.record(u, S, direction_of(r.axes, "dice"), seed=seed, duration_s=10, known=KNOWN)
        got.append((make_id(r.axes), "repeat_after_rotation" in r.flags))
    first = [i for i, _ in got[:len(pool)]]
    assert set(first) == pool and not any(rep for _, rep in got[:len(pool)])   # every id once, no repeat
    assert [i for i, _ in got[len(pool):]] == first[:3] and all(rep for _, rep in got[len(pool):])  # then LRU


def test_rotation_state_is_capped_by_the_catalog_size(mem):
    u = mem.issue_user_token()
    for m in ["noir", "clean", "vivid"]:
        mem.record(u, S, _d(m), seed=1, duration_s=10, known=KNOWN)
    small = {**KNOWN, "mood": ["clean", "vivid"], "tone": ["white"], "pace": ["calm"], "opener": ["arc_orbit"],
             "weather": ["dry"], "wind": ["calm"]}                    # this subject now offers 2 directions
    mem.record(u, S, _d("clean"), seed=2, duration_s=10, known=small)
    assert mem.recent(u, S) == [_d("vivid").id, _d("clean").id]       # least recently used dropped first


def test_thread_locks_are_dropped_when_nobody_holds_or_waits(mem):
    import time

    import engine.director.memory as mm
    before = len(mm._THREAD_LOCKS)
    for _ in range(40):                                                # churn: new users every time
        u = mem.issue_user_token()
        with mem.locked(u, S):
            pass
    assert len(mm._THREAD_LOCKS) == before
    u = mem.issue_user_token()
    with mem.locked(u, S):
        waiter_done = []

        def waiter():
            with mem.locked(u, S):
                waiter_done.append(1)
        t = threading.Thread(target=waiter)
        t.start()
        time.sleep(0.1)
        assert len(mm._THREAD_LOCKS) == before + 1                     # a waiter keeps the entry alive
    t.join()
    assert waiter_done == [1] and len(mm._THREAD_LOCKS) == before


def test_key_file_is_restricted_while_still_empty(mem, monkeypatch):
    """The key bytes are written only after the file is owner-only (no window with inherited ACLs)."""
    import os

    import engine.director.memory as mm
    sizes, real = [], mm._owner_only

    def spy(path):
        sizes.append(os.path.getsize(path))
        real(path)
    monkeypatch.setattr(mm, "_owner_only", spy)
    key = mem._key_bytes()
    assert sizes == [0] and len(key) == mm.SECRET_BYTES
    assert (mem.root / ".secret").read_bytes() == key
