from corpus.accuracy import compare, summarize, trusted_fields
from corpus.tests.test_schema import _rec


def test_identical_records_agree_everywhere():
    rows = compare(_rec(), _rec())
    assert rows and all(r["agree"] for r in rows)


def test_field_disagreements_and_shot_alignment():
    ext = _rec(**{"shots.0.cameraMove": "orbit", "world.type": "cyclorama"})
    rows = {r["field"]: r["agree"] for r in compare(ext, _rec()) if r["field"] in ("shots.cameraMove", "world.type")}
    assert rows == {"shots.cameraMove": False, "world.type": False}
    ext = _rec(**{"format.shotCount": 1})
    ext["shots"] = ext["shots"][:1]
    ext["format"]["cutTimesS"] = []
    got = [r for r in compare(ext, _rec()) if r["field"].startswith("shots.")]
    assert got and not any(r["agree"] for r in got)  # misaligned shot lists count as disagreement


def test_cut_times_match_within_tolerance():
    ext = _rec(**{"format.cutTimesS": [4.2], "shots.0.endS": 4.2, "shots.1.startS": 4.2})
    row = next(r for r in compare(ext, _rec()) if r["field"] == "format.cutTimesS")
    assert row["agree"]  # 0.2 s off, inside CUT_TOL_S


def test_summary_and_trust_mask():
    pairs = [(_rec(), _rec())] * 9 + [(_rec(**{"world.type": "street"}), _rec())] * 3
    s = summarize(pairs)
    assert s["n"] == 12 and s["fields"]["world.type"]["rate"] == 0.75
    assert "world.type" in trusted_fields(s, min_rate=0.7, min_n=10)
    assert "world.type" not in trusted_fields(s, min_rate=0.8, min_n=10)


def test_run_without_gold_writes_nothing(tmp_path):
    # An accuracy.json with n=0 would mark every stat untrusted (False) instead of unmeasured (None).
    from corpus.accuracy import run
    (tmp_path / "gold").mkdir()
    out = tmp_path / "accuracy.json"
    s = run(refs_dir=tmp_path, gold_dir=tmp_path / "gold", out=out)
    assert s["n"] == 0 and not out.exists()
