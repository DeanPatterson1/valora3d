from engine.physics import probes


def test_grounded_and_patch_rules():
    assert probes.grounded_ok({"minZ": -0.0004}, 0.0) and not probes.grounded_ok({"minZ": 0.003}, 0.0)
    rec = {"minZ": -0.0002, "flatLenM": 0.16, "flatN": 9}
    assert probes.tyre_patch_ok(rec, 0.35, 0.45, 0.0)                 # want 0.1575 m
    assert not probes.tyre_patch_ok({**rec, "flatLenM": 0.05}, 0.35, 0.45, 0.0)
    assert not probes.tyre_patch_ok({**rec, "minZ": -0.01}, 0.35, 0.45, 0.0)
