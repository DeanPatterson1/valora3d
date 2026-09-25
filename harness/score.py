"""Combine [S] (engine.craft_rules) and [M] (harness.metrics) results into TIERS items and the
tier reached (TIERS §3: cumulative; n/a counts as pass; unmeasured makes the result provisional)."""
import json
from pathlib import Path

from engine.checker import check
from engine.craft_rules import ItemResult, score_script
from harness.frames import load_frames
from harness.items import ITEMS, by_id
from harness.metrics import DENSE_FRAME_ITEMS, evaluate

ORDER = ("T2", "T3", "T4")
S_FALLBACK = {"T2-08": "S fallback: grade is not identity (M half not measured in v0)",
              "T3-01": "our renders: shot count from the script's cut times (TIERS allows this)"}
_STATUS_ORDER = {"fail": 0, "unmeasured": 1, "pass": 2, "na": 3}


def tier_reached(results):
    """Cumulative tier. Items that need every frame (DENSE_FRAME_ITEMS: key frames can never measure
    them) are listed in denseGaps and never make the result provisional; any other unmeasured item
    does. An unmeasured B or T1 item holds the tier at T1 (unverified): a clip whose baseline was
    never measured is not known to clear it."""
    def status(tier):
        return [(i["id"], results[i["id"]].status) for i in ITEMS if i["tier"] == tier]

    dense = [i["id"] for i in ITEMS if i["id"] in DENSE_FRAME_ITEMS and results[i["id"]].status == "unmeasured"]

    def open_(tier):
        return [iid for iid, st in status(tier) if st == "unmeasured" and iid not in DENSE_FRAME_ITEMS]

    base = [iid for t in ("B", "T1") for iid, st in status(t) if st == "fail"]
    if base:
        return {"tier": "T1", "provisional": False, "blocking": base, "denseGaps": dense}
    unverified = open_("B") + open_("T1")
    if unverified:
        return {"tier": "T1", "provisional": True, "blocking": [], "denseGaps": dense, "unverified": unverified}
    reached, provisional = "T1", False
    for tier in ORDER:
        fails = [iid for iid, st in status(tier) if st == "fail"]
        if fails:
            return {"tier": reached, "provisional": provisional, "blocking": fails, "denseGaps": dense}
        provisional = provisional or bool(open_(tier))
        reached = tier
    return {"tier": reached, "provisional": provisional, "blocking": [], "denseGaps": dense}


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


WEATHER_FAMILIES = {"rain": "rain", "snow": "snow", "ground_fog": "fog"}   # W-01: one falling/fog family per clip


def weather_s_items(script, catalog, expect_delivered=None, profile=None):
    """Script-level weather items (plan Task 69), report-only:
    PH-08s: rain present => wet_surface and droplets present (the coupling kept). A coupled child the subject
            cannot take (its requiresProfile fails, the checker's coupled_skipped) is exempt when `profile` is
            given (review chunk3 #8);
    PH-07s: every expectDelivered capability is provided by a block in the final script (na without a list);
    W-01:   at most one weather family (rain, snow, fog) per clip."""
    from engine.weather_rules import _missing
    ids = [e["id"] for e in script.get("effects", [])]
    out = {}
    if "rain" in ids:
        need = {"wet_surface", "droplets"}
        if profile is not None:
            need = {c for c in need if not _missing(profile, catalog.get("effect", c) or {})}
        ok = need <= set(ids)
        out["PH-08s"] = ItemResult("PH-08s", "pass" if ok else "fail", sorted(set(ids) & {"wet_surface", "droplets"}),
                                   "" if need == {"wet_surface", "droplets"} else
                                   f"coupled_skipped: {sorted({'wet_surface', 'droplets'} - need)} do not fit the subject")
    else:
        out["PH-08s"] = ItemResult("PH-08s", "na", None, "no rain")
    if expect_delivered is None:
        out["PH-07s"] = ItemResult("PH-07s", "na", None, "no expectDelivered list")
    else:
        refs = [("world", script["world"]["id"]), ("lighting", script["lighting"]["id"]), ("grade", script["grade"]["id"]),
                ("motion", script["subject"]["motion"]["id"])] + [("effect", i) for i in ids]
        refs += [("camera", sh["camera"]["id"]) for sh in script["shots"]]
        if script.get("wind"):
            refs.append(("field", script["wind"]["id"]))
        caps = {c for k, b in refs for c in (catalog.get(k, b) or {}).get("capabilities", [])}
        miss = sorted(set(expect_delivered) - caps)
        out["PH-07s"] = ItemResult("PH-07s", "fail" if miss else "pass", miss)
    fams = sorted({WEATHER_FAMILIES[i] for i in ids if i in WEATHER_FAMILIES})
    out["W-01"] = ItemResult("W-01", "pass" if len(fams) <= 1 else "fail", fams)
    return out


EXPECT_FILE = "expect.json"   # the case's expectations beside its render ({"expectDelivered": [...]}), run_case writes it


def score_case(case_dir, profile, catalog, th, expect_delivered=None):
    """Score what was rendered: the checked script the compiler saved in job.json, never a fresh
    check of the suite file (a checker change between render and score would score another clip).
    expect_delivered (else the case's expect.json) feeds PH-07s (review chunk3 #7)."""
    script = json.loads((Path(case_dir) / "job.json").read_text(encoding="utf-8"))["script"]
    if expect_delivered is None and (Path(case_dir) / EXPECT_FILE).exists():
        expect_delivered = json.loads((Path(case_dir) / EXPECT_FILE).read_text(encoding="utf-8")).get("expectDelivered")
    r = check(script, profile, catalog)
    if not r.ok:
        raise ValueError("script fails the checker; a failing script is never rendered or scored")
    frames = load_frames(case_dir, script, catalog)
    items = merge(score_script(script, profile, catalog), evaluate(frames, script, profile, catalog, th))
    from harness.physics import evaluate_physics   # own report section: the TIERS ladder is untouched
    physics = evaluate_physics(case_dir, frames, script, profile, catalog, th)
    return {"items": {k: {"status": v.status, "value": v.value, "detail": v.detail} for k, v in items.items()},
            **tier_reached(items),
            "physics": {k: {"status": v.status, "value": v.value, "detail": v.detail}
                        for k, v in {**physics, **weather_s_items(script, catalog, expect_delivered, profile)}.items()}}


def _jsonable(v):
    return json.loads(json.dumps(v, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


def write_report(case_dir, score, th=None):
    if th is None:
        th = json.loads((Path(__file__).with_name("thresholds.json")).read_text(encoding="utf-8"))
    case_dir = Path(case_dir)
    (case_dir / "report.json").write_text(json.dumps(_jsonable(score), indent=2), encoding="utf-8")
    head = (f"# {case_dir.name}\n\nTier reached: **{score['tier']}**"
            f"{' (provisional)' if score['provisional'] else ''}. Blocking: {', '.join(score['blocking']) or 'none'}.\n"
            f"Unverified baseline: {', '.join(score.get('unverified', [])) or 'none'}. "
            f"Dense-frame gaps (need every frame, not provisional): {', '.join(score.get('denseGaps', [])) or 'none'}.\n"
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
    if score.get("physics"):
        from harness.physics import PH_ITEMS
        method = {**{p["id"]: p["method"] for p in PH_ITEMS}, **{i: "S" for i in ("PH-08s", "PH-07s", "W-01")}}
        lines += ["", "## Physics (research/physics/BLOCKS.md §6)", "",
                  "| item | method | status | value | threshold | calibrated |", "|---|---|---|---|---|---|"]
        for iid, r in sorted(score["physics"].items()):
            t = th.get(iid)
            thr = f"{t['op']} {t[t['primary']]}" if t else ""
            cal = str(t["calibrated"]).lower() if t else ""
            val = json.dumps(_jsonable(r["value"])) if r["value"] is not None else ""
            lines.append(f"| {iid} | {method.get(iid, '')} | {r['status']} | {val[:80]} | {thr} | {cal} |")
    (case_dir / "report.md").write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
