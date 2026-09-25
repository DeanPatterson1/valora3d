import json
from pathlib import Path

from harness.items import ITEMS, by_id

TH = json.loads((Path(__file__).resolve().parents[1] / "thresholds.json").read_text())


def test_registry_covers_every_tiers_item_once():
    ids = [i["id"] for i in ITEMS]
    assert len(ids) == len(set(ids)) == 47  # TIERS.md: 5 B + 3 T1 + 9 T2 + 23 T3 + 6 T4, plus V-C02
    assert {i["tier"] for i in ITEMS} == {"B", "T1", "T2", "T3", "T4"}
    assert by_id("T3-06")["method"] == "M" and by_id("T2-09")["method"] == "V"


def test_thresholds_are_known_items_and_start_uncalibrated():
    from harness.physics import PH_ITEMS
    physics = {p["id"] for p in PH_ITEMS}          # the separate physics section (BLOCKS.md §6)
    for iid, t in TH.items():
        if iid in physics:
            assert t["calibrated"] is False and t["source"].startswith("research/physics"), iid
        else:
            assert by_id(iid)["method"] in ("M", "S+M"), iid
            assert t["calibrated"] is False and t["source"].startswith("TIERS"), iid
        assert t["op"] in (">=", "<=") and t["primary"] in t, iid
