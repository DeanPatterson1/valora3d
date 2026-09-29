import os

import pytest

from engine.ingest.run import BLENDER


def pytest_configure(config):
    config.addinivalue_line("markers", "blender: needs a local Blender install (slow)")
    config.addinivalue_line("markers", "live: calls the real Claude API; skipped unless ANTHROPIC_API_KEY is set")
    config.addinivalue_line("markers", "slow: a heavy Blender compile (minutes); skipped unless -m names slow "
                                       "(e.g. -m slow) or VALORA_SLOW=1")


def run_slow(markexpr, env):
    """Slow tests run only when asked: a -m expression that names `slow`, or VALORA_SLOW=1."""
    return "slow" in (markexpr or "") or env.get("VALORA_SLOW") == "1"


def pytest_collection_modifyitems(config, items):
    if run_slow(config.getoption("markexpr", ""), os.environ):
        return
    skip = pytest.mark.skip(reason="slow: a heavy Blender compile; run with -m slow (or VALORA_SLOW=1)")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


requires_blender = pytest.mark.skipif(not os.path.exists(BLENDER), reason="Blender not installed")
requires_api_key = pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY")


# Variety memory and replay signing need a server secret. Tests use the dev key file (never a production
# path) under a throwaway root, so nothing is written to the repo's var/.
os.environ.setdefault("VALORA_VARIETY_DEV", "1")
if "VALORA_VARIETY_DIR" not in os.environ:
    import tempfile as _tempfile
    os.environ["VALORA_VARIETY_DIR"] = _tempfile.mkdtemp(prefix="valora-variety-test-")


@pytest.fixture(scope="module")
def legacy_fps30():
    """The frozen phase-3/4 fixtures (fallback_phase4 cases, pre_motion pins) were captured when a script with no fps pin
    was 30 fps; the default became 24 on 2026-09-29. Those tests pin the old default so their bytes stay comparable."""
    import engine.director.intent as intent
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(intent, "DEFAULT_FPS", 30)
        yield
