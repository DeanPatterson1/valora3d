import math
import struct

from engine.bake.formats import FORMATS, PROBED, pc2_frame_bytes, pc2_header


def test_formats_name_exactly_the_five_methods():
    assert set(FORMATS) == {"rigid_keys", "cloth_pc2", "gn_disk", "gas_vdb", "liquid_abc"}
    for name, f in FORMATS.items():
        assert {"offset_mode", "velocity", "operator_override", "probed"} <= set(f), name
        assert f["probed"] == PROBED


def test_pc2_header_round_trips_through_struct():
    h = pc2_header(441, 7.0, 1.0, 30)
    assert len(h) == 32
    sig, ver, n, start, rate, samples = struct.unpack("<12siiffi", h)
    assert (sig, ver, n, start, rate, samples) == (b"POINTCACHE2\0", 1, 441, 7.0, 1.0, 30)


def test_pc2_frame_bytes_are_little_endian_float32_xyz():
    b = pc2_frame_bytes([(1.0, 2.0, 3.0), (-0.5, 0.25, math.pi)])
    assert len(b) == 24
    assert struct.unpack("<6f", b)[:5] == (1.0, 2.0, 3.0, -0.5, 0.25)
