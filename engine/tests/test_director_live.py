"""Task 32 live smoke (spends a few cents). Runs only with -m live and ANTHROPIC_API_KEY set; the one
command is `py -m harness director-live` (it probes the schema mode first and sets it for this run)."""
import pytest

from engine.catalog import Catalog
from engine.checker import check
from engine.director.pipeline import direct
from engine.tests.conftest import requires_api_key
from engine.tests.test_director_package import _p


@pytest.mark.live
@requires_api_key
def test_live_director_writes_a_checked_script_and_caches_the_rulebook():
    from engine.director.providers.anthropic_provider import AnthropicProvider
    p = AnthropicProvider()
    r1 = direct("make it look cool", _p("pocket_watch"), provider=p, seed=1)
    r2 = direct("rainy night", _p("sports_car"), provider=p, seed=2)
    for r, name in ((r1, "pocket_watch"), (r2, "sports_car")):
        assert check(r.script, _p(name), Catalog.load()).ok
        assert r.source != "fallback", r.rounds
    assert [u["capability"] for u in r2.script["unsupported"]][:1] == ["weather.rain"]
    assert r2.usage.get("cache_read_input_tokens", 0) > 0, "rulebook prefix did not cache"
