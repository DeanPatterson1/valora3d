import json

from corpus import CORPUS_DIR, REFS_DIR
from corpus.stats import compute, load_trust
from corpus.tests.test_schema import _rec


def _veh(i, shots):
    r = _rec(**{"id": f"v{i}", "subject.category": "vehicle", "subject.sizeClass": "vehicle"})
    t, rows = 0.0, []
    for L in shots:
        rows.append({**r["shots"][0], "startS": t, "endS": t + L})
        t += L
    r["shots"] = rows
    r["format"].update(durationS=t, shotCount=len(rows), cutTimesS=[s["startS"] for s in rows[1:]])
    return r


def test_shot_rhythm_stats_with_n():
    recs = [_veh(1, [2, 2, 2, 2, 2]), _veh(2, [2.5, 2.5, 2.5, 2.5])]
    s = compute(recs)
    v = s["families"]["vehicle"]
    assert v["records"] == 2
    assert v["shotsPer10s"]["median"] == 4.5 and v["shotsPer10s"]["n"] == 2
    assert v["shotLenS"]["median"] == 2.0 and v["shotLenS"]["n"] == 9
    assert s["families"]["all"]["records"] == 2
    assert v["cameraMove"]["n"] == 9 and v["cameraMove"]["shares"]["push"] == 1.0


def test_own_renders_and_low_tiers_are_excluded():
    low = _rec(**{"id": "low1", "qualityEstimate": "T1"})
    assert compute([low])["families"]["all"]["records"] == 0


def test_untrusted_fields_are_flagged():
    s = compute([_veh(1, [2, 2])], trusted={"in_player": {"world.type"}})
    assert s["families"]["all"]["worldType"]["trusted"] is True
    assert s["families"]["all"]["cameraMove"]["trusted"] is False
    assert compute([_veh(1, [2, 2])], trusted=None)["families"]["all"]["cameraMove"]["trusted"] is None


def test_committed_stats_match_the_committed_records():
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(REFS_DIR.glob("*.json"))]
    trusted = load_trust(CORPUS_DIR / "accuracy.json")
    committed = json.loads((CORPUS_DIR / "stats.json").read_text(encoding="utf-8"))
    assert committed == compute(recs, trusted=trusted), "run: py -m corpus stats --write"


# --- review fixes 2026-09-24: trust is per extraction method ---

def test_trust_is_gated_per_method():
    local = _veh(1, [2, 2])
    local["method"] = "local_frames"
    player = _veh(2, [2, 2])  # in_player
    trusted = {"local_frames": {"world.type"}}
    assert compute([local], trusted=trusted)["families"]["all"]["worldType"]["trusted"] is True
    # in_player was never measured: any stat that includes an in_player record is untrusted
    assert compute([local, player], trusted=trusted)["families"]["all"]["worldType"]["trusted"] is False
    trusted["in_player"] = {"world.type"}
    assert compute([local, player], trusted=trusted)["families"]["all"]["worldType"]["trusted"] is True


def test_load_trust_reads_the_per_method_lists(tmp_path):
    f = tmp_path / "accuracy.json"
    assert load_trust(f) is None
    f.write_text(json.dumps({"trustedByMethod": {"local_frames": ["world.type"]}}), encoding="utf-8")
    assert load_trust(f) == {"local_frames": {"world.type"}}


def test_an_empty_family_is_not_trusted():
    s = compute([_veh(1, [2, 2])], trusted={"in_player": {"shots.cameraMove"}})
    assert s["families"]["furniture"]["cameraMove"]["trusted"] is False
