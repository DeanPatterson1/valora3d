"""Where Blender is and how every launch is locked down (spec §7: uploads are untrusted)."""
import os

BLENDER = os.environ.get("BLENDER_EXE", r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
SAFE_FLAGS = ("--background", "--factory-startup", "--disable-autoexec", "--offline-mode",
              "--python-exit-code", "1")


def blender_argv(script, args, blender=None):
    return [blender or BLENDER, *SAFE_FLAGS, "--python", str(script), "--", *map(str, args)]
