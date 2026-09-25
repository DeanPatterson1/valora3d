"""Review chunk 7 #3: at calm pace reveal_rise lands on the last middle shot, never on a detail shot."""
import pytest

from engine.catalog import Catalog
from engine.director.llm import FakeProvider
from engine.director.pipeline import direct
from engine.tests.test_director_package import _p

REFUSE = [{"stop_reason": "refusal"}]


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setenv("VALORA_VARIETY_SECRET", "x" * 40)


# ---- #3: at calm pace reveal_rise lands on the last MIDDLE shot, never on a detail shot ----


@pytest.mark.parametrize("name", ["pocket_watch", "mid_century_lounge_chair"])
@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("dur", [10, 12])
def test_calm_reveal_rise_never_replaces_a_detail_shot(name, seed, dur):
    s = direct("slow calm courtyard", _p(name), provider=FakeProvider(REFUSE), seed=seed, duration=dur,
               catalog=Catalog.load()).script
    for sh in s["shots"]:
        if sh["purpose"] == "detail":
            assert sh["camera"]["id"] == "macro_detail", (seed, dur, sh)
