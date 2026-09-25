"""Offline replay of the recorded live Claude replies (Task 32 Step 3; written by
`py -m harness director-live`). Until they are recorded this test skips."""
import pytest

from harness.director_live import FIXTURES, verify_recorded

RECORDED = sorted(FIXTURES.glob("live-*.json"))


@pytest.mark.skipif(not RECORDED, reason="no recorded live fixtures yet (Task 32 needs ANTHROPIC_API_KEY)")
@pytest.mark.parametrize("path", RECORDED or [None], ids=[p.stem for p in RECORDED] or ["none"])
def test_recorded_reply_replays_checked(path):
    assert verify_recorded(path) == []
