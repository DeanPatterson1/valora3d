import json

from harness.calibrate import load_owner_grades, match_cuts, parse_scene_scores, separation
from harness.contact_sheet import sheet


def test_match_cuts_counts_hits_misses_and_false_alarms():
    tp, fp, fn = match_cuts(pred=[1.0, 2.52, 7.0], truth=[1.02, 2.5, 5.0], tol_s=2 / 30)
    assert (tp, fp, fn) == (2, 1, 1)


def test_separation_proposes_a_midpoint_only_when_clean():
    assert separation(good=[0.5, 0.6], bad=[0.1, 0.2], op=">=") == {
        "status": "separable", "proposed": 0.35, "nGood": 2, "nBad": 2}
    r = separation(good=[0.3, 0.6], bad=[0.1, 0.4], op=">=")
    assert r["status"] == "overlap" and r["proposed"] is None
    assert separation(good=[], bad=[0.1], op=">=")["status"] == "insufficient"


def test_separation_mirrors_for_upper_bounds():
    assert separation(good=[0.1, 0.2], bad=[0.5, 0.6], op="<=")["proposed"] == 0.35
    assert separation(good=[0.5], bad=[0.1], op="<=")["status"] == "overlap"


def test_parse_scene_scores_pairs_times_with_scores():
    err = "\n".join([
        "[Parsed_metadata_1 @ 0x1] frame:0    pts:0       pts_time:0",
        "[Parsed_metadata_1 @ 0x1] lavfi.scene_score=0.000000",
        "[Parsed_metadata_1 @ 0x1] frame:1    pts:512     pts_time:0.0333333",
        "[Parsed_metadata_1 @ 0x1] lavfi.scene_score=0.412000"])
    assert parse_scene_scores(err) == [(0.0, 0.0), (0.0333333, 0.412)]


def test_only_owner_grades_count(tmp_path):
    p = tmp_path / "g.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in [
        {"case": "r/a__t3", "tier": "T3", "by": "owner", "date": "2026-09-24"},
        {"case": "r/b__t3", "tier": "T3", "by": "judge", "date": "2026-09-24"},
        {"case": "r/c__t1", "tier": "T1", "by": "harness", "date": "2026-09-24"}]) + "\n\n")
    assert load_owner_grades(p) == {"r/a__t3": "T3"}


def test_contact_sheet_lays_frames_in_a_row(tmp_path):
    from PIL import Image
    paths = []
    for i in range(3):
        p = tmp_path / f"{i}.png"
        Image.new("RGB", (144, 256), (i * 60, 0, 0)).save(p)
        paths.append(p)
    out = sheet(paths, "case-x", tmp_path / "s.png", thumb_h=128)
    assert Image.open(out).size == (3 * 72, 128 + 24)


def test_separate_reads_worst_frame_values_for_owner_graded_cases_only(tmp_path):
    from harness.calibrate import calibrate_separate
    run = tmp_path / "r"
    for case, cov in (("a__t3", [[1, 0.6, True], [2, 0.5, True]]), ("b__t1", [[1, 0.1, False]]),
                      ("c__t1", [[1, 0.9, True]])):
        (run / case).mkdir(parents=True)
        (run / case / "report.json").write_text(json.dumps({"items": {"B-05": {"value": cov}}}))
    g = tmp_path / "g.jsonl"
    g.write_text(json.dumps({"case": "r/a__t3", "tier": "T3", "by": "owner"}) + "\n"
                 + json.dumps({"case": "r/b__t1", "tier": "T1", "by": "owner"}) + "\n")
    r = calibrate_separate("r", out_root=tmp_path, grades_path=g)
    assert r["nGradedCases"] == 2  # c__t1 has no owner grade
    assert r["items"]["B-05"] == {"status": "separable", "proposed": 0.3, "nGood": 1, "nBad": 1,
                                  "op": ">=", "current": 0.25, "nT2": 0}
