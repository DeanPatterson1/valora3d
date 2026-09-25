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


# --- review fixes 2026-09-24 ---
from corpus.assemble import MAX_IN_PLAYER_PER_DAY  # noqa: E402


def _dirs(tmp_path):
    drafts, refs, local = tmp_path / "drafts", tmp_path / "refs", tmp_path / "local"
    for d in (drafts, refs, local):
        d.mkdir()
    return drafts, refs, local


def _stock_rec():
    r = _rec(**{"id": "pexels-1", "method": "local_frames"})
    r["source"] = {"kind": "stock", "platform": "pexels", "url": "https://www.pexels.com/video/1/",
                   "downloaded": True, "downloadedBy": "owner", "localFile": "stock/pexels-1.mp4",
                   "selection": "hand", "studiedAt": "2026-09-26",
                   "licence": {"name": "Pexels License", "url": "https://www.pexels.com/license/",
                               "checkedAt": "2026-09-26", "restricted": False}}
    return r


def test_accept_refuses_a_downloaded_record_whose_file_is_missing(tmp_path):
    drafts, refs, local = _dirs(tmp_path)
    d = drafts / "pexels-1.json"
    d.write_text(json.dumps(_stock_rec()), encoding="utf-8")
    ok, probs = accept(d, refs, local_dir=local)
    assert not ok and "localFile" in probs[0]
    (local / "stock").mkdir()
    (local / "stock" / "pexels-1.mp4").write_bytes(b"x")
    assert accept(d, refs, local_dir=local) == (True, [])


def test_accept_refuses_a_local_file_outside_the_local_dir(tmp_path):
    drafts, refs, local = _dirs(tmp_path)
    r = _stock_rec()
    r["source"]["localFile"] = "../outside.mp4"
    (tmp_path / "outside.mp4").write_bytes(b"x")
    (drafts / "pexels-1.json").write_text(json.dumps(r), encoding="utf-8")
    ok, probs = accept(drafts / "pexels-1.json", refs, local_dir=local)
    assert not ok and "localFile" in probs[0]


def test_accept_refuses_an_owner_record_without_its_clip(tmp_path):
    drafts, refs, local = _dirs(tmp_path)
    r = _rec(**{"id": "ref13", "method": "local_frames"})
    r["source"] = {"kind": "owner", "platform": "owner-refs", "url": None, "downloaded": True,
                   "selection": "hand", "studiedAt": "2026-09-26"}
    (drafts / "ref13.json").write_text(json.dumps(r), encoding="utf-8")
    ok, probs = accept(drafts / "ref13.json", refs, local_dir=local, root=tmp_path)
    assert not ok and "assets-in/refs/clips/ref13.mp4" in probs[0]
    (tmp_path / "assets-in" / "refs" / "clips").mkdir(parents=True)
    (tmp_path / "assets-in" / "refs" / "clips" / "ref13.mp4").write_bytes(b"x")
    assert accept(drafts / "ref13.json", refs, local_dir=local, root=tmp_path) == (True, [])


def test_accept_caps_in_player_records_per_day(tmp_path):
    drafts, refs, local = _dirs(tmp_path)
    for i in range(MAX_IN_PLAYER_PER_DAY):
        (refs / f"yt-{i}.json").write_text(json.dumps(_rec(**{"id": f"yt-{i}"})), encoding="utf-8")
    other_day = _rec(**{"id": "yt-other", "source.studiedAt": "2026-09-27"})
    (drafts / "yt-other.json").write_text(json.dumps(other_day), encoding="utf-8")
    assert accept(drafts / "yt-other.json", refs, local_dir=local)[0]
    (drafts / "yt-p38.json").write_text(json.dumps(_rec()), encoding="utf-8")
    ok, probs = accept(drafts / "yt-p38.json", refs, local_dir=local)
    assert MAX_IN_PLAYER_PER_DAY == 20 and not ok and "2026-09-26" in probs[0]


def test_extract_prompt_fences_page_text_and_limits_the_agent():
    from corpus import ROOT
    text = (ROOT / "corpus" / "prompts" / "extract.md").read_text(encoding="utf-8").lower()
    for phrase in ("data, not instructions", "play, pause and scrub", "never sign in", "like",
                   "comment", "20 in_player records"):
        assert phrase in text, phrase
