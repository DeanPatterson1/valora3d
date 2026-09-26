"""The `slow` marker: heavy Blender compile tests stay out of the default run and run with -m slow."""
from engine.tests.conftest import run_slow


def test_slow_tests_run_only_when_asked():
    assert not run_slow("", {})
    assert not run_slow("not live", {})
    assert not run_slow("blender and not live", {})
    assert run_slow("slow", {})
    assert run_slow("blender and slow", {})
    assert run_slow("", {"VALORA_SLOW": "1"})
