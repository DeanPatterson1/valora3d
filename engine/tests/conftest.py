import os

import pytest

from engine.ingest.run import BLENDER


def pytest_configure(config):
    config.addinivalue_line("markers", "blender: needs a local Blender install (slow)")


requires_blender = pytest.mark.skipif(not os.path.exists(BLENDER), reason="Blender not installed")
