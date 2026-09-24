import pytest

from engine.blender_cli import SAFE_FLAGS, blender_argv
from engine.compiler.sandbox import container_argv
from engine.compiler.tiers import TIERS, resolution


def test_blender_argv_is_safe_and_ends_with_the_args():
    argv = blender_argv("x.py", ["job.json"], blender="B")
    assert argv[0] == "B" and argv[-1] == "job.json" and argv[-2] == "--"
    for flag in ("--background", "--factory-startup", "--disable-autoexec", "--offline-mode"):
        assert flag in argv and flag in SAFE_FLAGS


def test_container_has_no_network_and_a_hard_memory_cap():
    argv = container_argv("valora/render:1", "/jobs/abc", memory_gb=24)
    for a in ("--network=none", "--memory=24g", "--memory-swap=24g", "--read-only",
              "--cap-drop=ALL", "--security-opt=no-new-privileges"):
        assert a in argv, a
    assert argv.count("-v") == 1 and "/jobs/abc:/job:rw" in argv
    assert any(a.startswith("--pids-limit=") for a in argv)


@pytest.mark.parametrize("aspect,short,want", [("9:16", 540, (540, 960)), ("16:9", 1080, (1920, 1080)),
                                               ("4:5", 540, (540, 676)), ("1:1", 144, (144, 144))])
def test_resolution_is_even_and_keeps_aspect(aspect, short, want):
    assert resolution(aspect, short) == want


def test_tiers():
    assert set(TIERS) == {"keyframes", "preview", "final"}
    assert TIERS["keyframes"]["samples"] <= 8 and TIERS["preview"]["samples"] < TIERS["final"]["samples"]
