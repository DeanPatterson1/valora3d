import os

import pytest

from engine.ingest.run import BLENDER


def pytest_configure(config):
    config.addinivalue_line("markers", "blender: needs a local Blender install (slow)")
    config.addinivalue_line("markers", "live: calls the real Claude API; skipped unless ANTHROPIC_API_KEY is set")


requires_blender = pytest.mark.skipif(not os.path.exists(BLENDER), reason="Blender not installed")
requires_api_key = pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")


# Variety memory and replay signing need a server secret. Tests use the dev key file (never a production
# path) under a throwaway root, so nothing is written to the repo's var/.
os.environ.setdefault("VALORA_VARIETY_DEV", "1")
if "VALORA_VARIETY_DIR" not in os.environ:
    import tempfile as _tempfile
    os.environ["VALORA_VARIETY_DIR"] = _tempfile.mkdtemp(prefix="valora-variety-test-")
