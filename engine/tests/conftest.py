import os

import pytest

from engine.ingest.run import BLENDER


def pytest_configure(config):
    config.addinivalue_line("markers", "blender: needs a local Blender install (slow)")
    config.addinivalue_line("markers", "live: calls the real Claude API; skipped unless ANTHROPIC_API_KEY is set")


requires_blender = pytest.mark.skipif(not os.path.exists(BLENDER), reason="Blender not installed")
requires_api_key = pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")
