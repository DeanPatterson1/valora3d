import subprocess

import pytest

from engine.blender_cli import BLENDER
from engine.blender_pin import PINNED_BLENDER, parse_version
from engine.tests.conftest import requires_blender


def test_parse_version():
    assert parse_version("Blender 5.0.1\n\tbuild date: 2025-12-16") == "5.0.1"


def test_parse_version_rejects_text_without_a_version():
    assert parse_version("not blender") is None


@pytest.mark.blender
@requires_blender
def test_installed_blender_is_the_pinned_build():
    out = subprocess.run([BLENDER, "--version"], capture_output=True, text=True, timeout=120).stdout
    assert parse_version(out) == PINNED_BLENDER, "Blender changed: re-probe (Task 94) and re-grade before moving the pin"
