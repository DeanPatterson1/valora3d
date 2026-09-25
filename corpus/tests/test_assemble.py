import json

from corpus.assemble import accept
from corpus.tests.test_schema import _rec


def test_accept_moves_a_valid_draft(tmp_path):
    drafts, refs = tmp_path / "drafts", tmp_path / "refs"
    drafts.mkdir(), refs.mkdir()
    d = drafts / "yt-p38.json"
    d.write_text(json.dumps(_rec()), encoding="utf-8")
    ok, probs = accept(d, refs)
    assert ok and probs == [] and (refs / "yt-p38.json").exists() and not d.exists()


def test_accept_refuses_invalid_or_duplicate(tmp_path):
    drafts, refs = tmp_path / "drafts", tmp_path / "refs"
    drafts.mkdir(), refs.mkdir()
    bad = _rec(**{"source.downloaded": True})
    (drafts / "yt-p38.json").write_text(json.dumps(bad), encoding="utf-8")
    ok, probs = accept(drafts / "yt-p38.json", refs)
    assert not ok and probs and (drafts / "yt-p38.json").exists()
    (refs / "yt-p38.json").write_text("{}", encoding="utf-8")
    (drafts / "yt-p38.json").write_text(json.dumps(_rec()), encoding="utf-8")
    ok, probs = accept(drafts / "yt-p38.json", refs)
    assert not ok and "exists" in probs[0]
