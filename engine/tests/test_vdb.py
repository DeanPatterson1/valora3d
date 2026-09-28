"""Phase 6 Task 110 (lane S), pure parts: VDB sequence playback maths (engine/physics/vdb.py) and pinned
sequences (engine/assets.resolve_sequence)."""
import hashlib

import pytest

from engine import assets as A
from engine.physics import vdb as V


# --- scale guard ---------------------------------------------------------------------------------------------

def test_scale_factor_keeps_a_plume_near_its_physical_size():
    assert V.scale_factor(2.0, 2.0) == 1.0
    assert V.scale_factor(2.0, 6.0) == pytest.approx(3.0)
    assert V.scale_factor(2.0, 2.0 / 3) == pytest.approx(1 / 3)
    for asked in (6.2, 0.6, 20.0):
        with pytest.raises(V.VdbScaleError):
            V.scale_factor(2.0, asked)          # a campfire scaled x10 reads wrong (GS-01)


# --- frame mapping (the measured 5.0.1 rule: file = f - frame_start + 1 + frame_offset) ------------------------

def _shown(keys, start, span, f):
    """What Blender shows at render frame f under CLIP with CONSTANT-keyed offsets (the probe's rule)."""
    if not (1 <= f - start + 1 <= span):
        return None
    off = [o for k, o in keys if k <= f][-1]
    return f - start + 1 + off


@pytest.mark.parametrize("retime", [1.0, 0.5, 0.75, 2.0])
def test_offset_keys_play_every_file_in_order_at_the_retime(retime):
    start, n = 31, 20
    keys = V.offset_keys(start, retime, n)
    s, span = V.play_range(start, retime, n)
    seq = [_shown(keys, s, span, f) for f in range(start - 3, start + span + 3)]
    shown = [x for x in seq if x is not None]
    assert seq[:3] == [None] * 3 and seq[-3:] == [None] * 3            # empty before and after
    assert shown == sorted(shown) and shown[0] == 1 and shown[-1] <= n
    assert V.file_for(start + span, start, retime, n) is None          # plays to the end of the sequence
    assert len(shown) == span
    for f in range(start, start + span):
        assert _shown(keys, s, span, f) == V.file_for(f, start, retime, n)


def test_retime_one_is_a_single_zero_key():
    assert V.offset_keys(1, 1.0, 50) == [(1, 0)]
    assert V.play_range(1, 1.0, 50) == (1, 50)


def test_a_later_first_file_skips_the_sequences_head():
    keys = V.offset_keys(10, 1.0, 40, first_file=11)
    assert keys == [(10, 10)] and V.play_range(10, 1.0, 40, first_file=11) == (10, 30)


def test_retime_is_clamped_and_velocity_follows_it():
    assert V.clamp_retime(0.01) == V.MIN_RETIME and V.clamp_retime(10) == V.MAX_RETIME
    assert V.velocity_scale(0.5) == 0.5


# --- pinned sequences ----------------------------------------------------------------------------------------

def _pinned(tmp_path, n=3):
    d = tmp_path / "lib" / "valora_vdb" / "plume"
    d.mkdir(parents=True)
    files = {}
    for i in range(1, n + 1):
        b = bytes([i]) * (100 + i)
        (d / f"fluid_data_{i:04d}.vdb").write_bytes(b)
        files[f"fluid_data_{i:04d}.vdb"] = {"sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
    row = {"path": "valora_vdb/plume", "files": files, "sha256": A.sequence_digest(files), "licence": "CC0-1.0",
           "source": "tools/bake_vdb_library.py", "credit": None, "native": {"widthM": 2.0, "fps": 24}}
    return tmp_path / "lib", {"schema": "valora.assets/1", "assets": {"plume": row}}


def test_resolve_sequence_returns_the_files_in_order_with_their_native_facts(tmp_path):
    root, man = _pinned(tmp_path)
    s = A.resolve_sequence("plume", root, man)
    assert [f.name for f in s["files"]] == ["fluid_data_0001.vdb", "fluid_data_0002.vdb", "fluid_data_0003.vdb"]
    assert s["native"]["widthM"] == 2.0 and s["dir"].name == "plume"


def test_a_missing_file_is_the_fallback_and_a_changed_one_is_refused(tmp_path):
    root, man = _pinned(tmp_path)
    (root / "valora_vdb" / "plume" / "fluid_data_0002.vdb").write_bytes(b"\x09" * 102)   # same size, new bytes
    assert A.resolve_sequence("plume", root, man, verify="size") is not None
    with pytest.raises(A.AssetError):
        A.resolve_sequence("plume", root, man)
    (root / "valora_vdb" / "plume" / "fluid_data_0003.vdb").unlink()
    assert A.resolve_sequence("plume", root, man, verify="size") is None
    assert A.resolve_sequence("plume", tmp_path / "empty", man) is None


def test_a_sequence_row_must_pin_its_files_and_their_digest(tmp_path):
    _, man = _pinned(tmp_path)
    row = man["assets"]["plume"]
    bad = dict(row, sha256="0" * 64)
    with pytest.raises(A.AssetError):
        A.validate_manifest({"assets": {"plume": bad}}, credits={})
    bad = dict(row, files={"../x.vdb": {"sha256": "0" * 64}})
    bad["sha256"] = A.sequence_digest(bad["files"])
    with pytest.raises(A.AssetError):
        A.validate_manifest({"assets": {"plume": bad}}, credits={})


def test_the_committed_manifest_still_validates():
    A.load_manifest()
