"""Where Blender is and how every launch is locked down (spec §7: uploads are untrusted).

Network isolation does NOT come from these flags: on the farm it comes from the container
(`--network=none`, engine/compiler/sandbox.py). `--offline-mode` only overrides Blender's own
"allow online access" preference so add-ons and the extensions platform do not try to go online;
it cannot stop a Python script from opening a socket. `--disable-autoexec` blocks scripts embedded
in the .blend/.glb, and `--factory-startup` ignores the user's startup file and preferences."""
import os

BLENDER = os.environ.get("BLENDER_EXE", r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
SAFE_FLAGS = ("--background", "--factory-startup", "--disable-autoexec", "--offline-mode",
              "--python-exit-code", "1")


def blender_argv(script, args, blender=None):
    return [blender or BLENDER, *SAFE_FLAGS, "--python", str(script), "--", *map(str, args)]
