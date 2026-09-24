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
    argv = container_argv("valora/render:1", "/farm/jobs/abc", farm_root="/farm/jobs", memory_gb=24)
    for a in ("--network=none", "--memory=24g", "--memory-swap=24g", "--read-only",
              "--cap-drop=ALL", "--security-opt=no-new-privileges", "--init"):
        assert a in argv, a
    assert any(a.startswith("--pids-limit=") for a in argv)
    assert argv[argv.index("--ulimit") + 1] == "nofile=4096:4096"


def test_container_mounts_inputs_read_only_and_one_writable_output():
    argv = container_argv("valora/render:1", "/farm/jobs/abc", farm_root="/farm/jobs")
    assert "-v" not in argv and "--volume" not in argv
    mounts = [argv[i + 1] for i, a in enumerate(argv) if a == "--mount"]
    assert mounts == ["type=bind,source=/farm/jobs/abc/in,target=/job,readonly",
                      "type=bind,source=/farm/jobs/abc/out,target=/out"]
    assert argv[-1] == "valora/render:1"


@pytest.mark.parametrize("job_dir", ["jobs/abc",               # relative
                                     "/elsewhere/abc",         # outside the farm root
                                     "/farm/jobs/../etc",      # escapes via ..
                                     "/farm/jobs",             # the root itself
                                     "/farm/jobs/a:b",         # ':' would split a -v spec
                                     "/farm/jobs/a,readonly=0"])  # ',' would inject a mount option
def test_container_rejects_unsafe_job_dirs(job_dir):
    with pytest.raises(ValueError):
        container_argv("valora/render:1", job_dir, farm_root="/farm/jobs")


@pytest.mark.parametrize("aspect,short,want", [("9:16", 540, (540, 960)), ("16:9", 1080, (1920, 1080)),
                                               ("4:5", 540, (544, 680)), ("1:1", 144, (144, 144)),
                                               ("9:16", 144, (144, 256)), ("4:5", 1080, (1080, 1350))])
def test_resolution_is_even_and_keeps_aspect(aspect, short, want):
    assert resolution(aspect, short) == want


@pytest.mark.parametrize("aspect", ["9:16", "16:9", "1:1", "4:5"])
@pytest.mark.parametrize("tier", ["keyframes", "preview", "final"])
def test_every_supported_aspect_is_exact_and_even_at_every_tier(aspect, tier):
    from engine.catalog import ASPECTS
    from engine.geometry import aspect_wh
    assert aspect in ASPECTS
    w, h = resolution(aspect, TIERS[tier]["shortSide"])
    aw, ah = aspect_wh(aspect)
    assert w * ah == h * aw  # exact aspect, no rounding
    assert w % 2 == 0 and h % 2 == 0 and min(w, h) >= TIERS[tier]["shortSide"]


def test_tiers():
    assert set(TIERS) == {"keyframes", "preview", "final"}
    assert TIERS["keyframes"]["samples"] <= 8 and TIERS["preview"]["samples"] < TIERS["final"]["samples"]
