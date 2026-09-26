from engine.tests.conftest import pytest_collection_modifyitems  # noqa: F401 - the slow gate, one source
from engine.tests.conftest import requires_blender  # noqa: F401 - one source for the Blender path


def pytest_configure(config):
    config.addinivalue_line("markers", "blender: needs a local Blender install (slow)")
    config.addinivalue_line("markers", "slow: a heavy Blender compile (minutes); skipped unless -m names slow")
