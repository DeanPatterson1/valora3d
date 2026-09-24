from engine.tests.conftest import requires_blender  # noqa: F401 - one source for the Blender path


def pytest_configure(config):
    config.addinivalue_line("markers", "blender: needs a local Blender install (slow)")
