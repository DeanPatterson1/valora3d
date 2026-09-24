"""Combine [S] (engine.craft_rules) and [M] (harness.metrics) results into TIERS items and the
tier reached (TIERS §3: cumulative; n/a counts as pass; unmeasured makes the result provisional)."""
import json
from pathlib import Path

from engine.checker import check
from engine.craft_rules import ItemResult, score_script
from harness.frames import load_frames
from harness.items import ITEMS, by_id
from harness.metrics import evaluate

ORDER = ("T2", "T3", "T4")
S_FALLBACK = {"T2-08": "S fallback: grade is not identity (M half not measured in v0)",
              "T3-01": "our renders: shot count from the script's cut times (TIERS allows this)"}
_STATUS_ORDER = {"fail": 0, "unmeasured": 1, "pass": 2, "na": 3}


def tier_reached(results):
    def status(tier):
        return [(i["id"], results[i["id"]].status) for i in ITEMS if i["tier"] == tier]

    base = [iid for t in ("B", "T1") for iid, st in status(t) if st == "fail"]
    if base:
        return {"tier": "T1", "provisional": False, "blocking": base}
    reached, provisional = "T1", any(st == "unmeasured" for t in ("B", "T1") for _, st in status(t))
    for tier in ORDER:
        fails = [iid for iid, st in status(tier) if st == "fail"]
        if fails:
            return {"tier": reached, "provisional": provisional, "blocking": fails}
        provisional = provisional or any(st == "unmeasured" for _, st in status(tier))
        reached = tier
    return {"tier": reached, "provisional": provisional, "blocking": []}


def _combine(iid, s, m):
    if s is None or m is None or "unmeasured" in (s.status, m.status):
        return ItemResult(iid, "unmeasured", m.value if m else None,
                          f"S+M: a half is missing or unmeasured (S={s and s.status}, M={m and m.status})")
    if "fail" in (s.status, m.status):
        st = "fail"
    elif s.status == m.status == "na":
        st = "na"
    else:
        st = "pass"
    return ItemResult(iid, st, m.value, f"S={s.status} ({s.detail}); M={m.status}".strip())


def merge(s_items, m_items):
    """One ItemResult per registry item. S+M: fail if either half fails; unmeasured if a half is
    missing or unmeasured; na only when both halves are na. V: unmeasured in v0. B-04 passes by
    construction (the checker passed the script). An item nobody measured is unmeasured, never a
    pass."""
    s = {r.id: r for r in s_items}
    out = {}
    for item in ITEMS:
        iid, method = item["id"], item["method"]
        if iid in S_FALLBACK and iid in s:
            r = s[iid]
            out[iid] = ItemResult(iid, r.status, r.value, S_FALLBACK[iid])
        elif iid == "B-04" and iid not in s:
            out[iid] = ItemResult(iid, "pass", None, "by construction: the checker passed the script")
        elif method == "S":
            out[iid] = s.get(iid) or ItemResult(iid, "unmeasured", None, "no S result")
        elif method == "M":
            out[iid] = m_items.get(iid) or ItemResult(iid, "unmeasured", None, "no M result")
        elif method == "S+M":
            out[iid] = _combine(iid, s.get(iid), m_items.get(iid))
        else:  # V
            out[iid] = ItemResult(iid, "unmeasured", None, "vision judge not built (phase 3+)")
    return out


def score_case(case_dir, script, profile, catalog, th):
    r = check(script, profile, catalog)
    if not r.ok:
        raise ValueError("script fails the checker; a failing script is never rendered or scored")
    frames = load_frames(case_dir, r.script, catalog)
    items = merge(score_script(r.script, profile, catalog), evaluate(frames, r.script, profile, catalog, th))
    return {"items": {k: {"status": v.status, "value": v.value, "detail": v.detail} for k, v in items.items()},
            **tier_reached(items)}


def _jsonable(v):
    return json.loads(json.dumps(v, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


def write_report(case_dir, score, th=None):
    if th is None:
        th = json.loads((Path(__file__).with_name("thresholds.json")).read_text(encoding="utf-8"))
    case_dir = Path(case_dir)
    (case_dir / "report.json").write_text(json.dumps(_jsonable(score), indent=2), encoding="utf-8")
    head = (f"# {case_dir.name}\n\nTier reached: **{score['tier']}**"
            f"{' (provisional)' if score['provisional'] else ''}. Blocking: {', '.join(score['blocking']) or 'none'}.\n"
            "Report-only: thresholds are uncalibrated unless marked.\n\n"
            "| item | tier | status | value | threshold | calibrated |\n|---|---|---|---|---|---|\n")
    rows = sorted(score["items"].items(), key=lambda kv: (_STATUS_ORDER.get(kv[1]["status"], 9), kv[0]))
    lines = []
    for iid, r in rows:
        t = th.get(iid)
        thr = f"{t['op']} {t[t['primary']]}" if t else ""
        cal = str(t["calibrated"]).lower() if t else ""
        val = json.dumps(_jsonable(r["value"])) if r["value"] is not None else ""
        lines.append(f"| {iid} | {by_id(iid)['tier']} | {r['status']} | {val[:80]} | {thr} | {cal} |")
    (case_dir / "report.md").write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
