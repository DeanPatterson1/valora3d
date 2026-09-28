"""Physics items for our own renders (research/physics/BLOCKS.md §6). Report-only.

PH-01 tyre contact  [C] probes.tyre_patch_ok on every probed frame; [M] unmeasured in v0 (a 2-3% of r
                    flat is sub-pixel at keyframes/preview); [V] vision judge, phase 6.
PH-02 grounded      [C] probes.grounded_ok on every probed frame; [M] floor strip under the subject reads
                    darker than the floor beside it by seamRatio on full-framing frames."""
import json
from pathlib import Path

import numpy as np

from engine.craft_rules import ItemResult
from engine.physics import probes
from harness.metrics import lum

PH_ITEMS = [{"id": "PH-01", "method": "C+M+V", "text": "Tyre contact patch present (C); visible (M, V: later)"},
            {"id": "PH-02", "method": "C+M", "text": "Subject grounded: no gap; contact seam darker than the floor beside it"},
            {"id": "PH-05", "method": "C+M", "text": "Motion blur on fast physics: falling weather carries velocity (C); "
                                                     "streak length ~ v x shutter within +/-40% (M: later)"},
            {"id": "PH-03", "method": "C", "text": "Sims never inside the subject: <= 0.1% of points inside its closed shell"},
            {"id": "PH-04", "method": "C", "text": "Sims stable: no NaN, speed <= 3 x the block's cap, rigid pieces come to rest"},
            {"id": "PH-11", "method": "C", "text": "Bake cost logged per sim (bake seconds, cache bytes) apart from GPU seconds"},
            {"id": "PH-06", "method": "M", "text": "Wind coherence: optical-flow angle of wind-driven elements within 45 deg"},
            {"id": "PH-08", "method": "V", "text": "Weather coupling: raining, the subject looks wet and the ground ripples"}]


def seam_ratio(fd):
    """mean(floor beside) / mean(floor strip just under the mask), same rows as t1x2; None if unreadable."""
    L = lum(fd.rgb)
    if not fd.mask.any():
        return None
    ys, xs = np.nonzero(fd.mask)
    h, w = L.shape
    y0, y1 = ys.max() + 1, min(h, ys.max() + 1 + max(1, int(round(0.05 * h))))
    x0, x1 = xs.min(), xs.max() + 1
    pad = max(1, (x1 - x0) // 2)
    rows = np.zeros_like(fd.mask)
    rows[y0:y1] = True
    strip = rows.copy()
    strip[:, :x0] = strip[:, x1:] = False
    beside = rows & ~strip
    beside[:, :max(0, x0 - pad)] = beside[:, min(w, x1 + pad):] = False
    strip, beside = strip & ~fd.mask, beside & ~fd.mask
    if not strip.any() or not beside.any() or L[strip].mean() <= 0:
        return None
    return float(L[beside].mean() / L[strip].mean())


def _realism(realism):
    return {r["id"]: r.get("params", {}) for r in realism}


def ph01_c(probe, realism, wheels, patch_tol=probes.PATCH_TOL):
    rz = _realism(realism)
    if "tyre_contact" not in rz:
        return "na", "no tyre_contact in this script"
    if not probe:
        return "unmeasured", "no realism probe frames"
    sink = rz.get("contact_ground", {}).get("sinkMm", 0.0) / 1000.0
    ok = all(probes.tyre_patch_ok(t, wheels[int(i)]["radius"], rz["tyre_contact"]["patchLenFrac"], sink,
                                   patch_tol)
             for rec in probe.values() for i, t in rec["tyres"].items())
    return ("pass", None) if ok else ("fail", f"a tyre patch is missing or longer than +{patch_tol:.0%} of patchLenFrac x r")


def ph02_c(probe, realism):
    rz = _realism(realism)
    if "contact_ground" not in rz:
        return "na", "not a ground placement"
    if not probe:
        return "unmeasured", "no realism probe frames"
    sink = rz["contact_ground"].get("sinkMm", 0.0) / 1000.0
    ok = all(probes.grounded_ok(rec, sink) for rec in probe.values())
    return ("pass", None) if ok else ("fail", "the subject floats or sinks too deep on a probed frame")


def _sim_verdict(sim_probe, part):
    """PH-03 / PH-04 from compile.json.simProbe (report-only): na without sims, unmeasured when a probe could
    not judge (no shell, a method without a stability rule yet)."""
    if not sim_probe:
        return "na", "no sims in the clip"
    oks = {sid: (rec.get(part) or {}).get("ok") for sid, rec in sim_probe.items()}
    bad = sorted(s for s, ok in oks.items() if ok is False)
    if bad:
        return "fail", f"{part}: {', '.join(bad)}"
    if any(ok is None for ok in oks.values()):
        return "unmeasured", f"{part}: {', '.join(sorted(s for s, ok in oks.items() if ok is None))} not judged"
    return "pass", None


def ph11_c(compile_doc):
    """PH-11: bake seconds and cache bytes per sim (host-side bakes, else the probe's copy) beside GPU seconds."""
    bakes = compile_doc.get("bakes") or {}
    sp = compile_doc.get("simProbe") or {}
    ids = sorted(set(bakes) | set(sp))
    if not ids:
        return "na", None, "no sims in the clip"
    val = {s: {"bakeSeconds": (bakes.get(s) or sp.get(s) or {}).get("bakeSeconds"),
               "cacheBytes": (bakes.get(s) or {}).get("bytes", (sp.get(s) or {}).get("cacheBytes")),
               "fromCache": (bakes.get(s) or {}).get("fromCache")} for s in ids}
    val["gpuSeconds"] = (compile_doc.get("renderLog") or {}).get("totalSeconds")
    return "pass", val, "logged (report-only)"


def evaluate_physics(case_dir, frames, script, profile, catalog, th):
    cj = Path(case_dir) / "compile.json"
    probe = json.loads(cj.read_text(encoding="utf-8")).get("realismProbe", {}) if cj.exists() else {}
    realism = script.get("realism", [])
    out = {}
    s01, d01 = ph01_c(probe, realism, profile.wheels or [], th["PH-01"]["patchTol"])
    out["PH-01"] = ItemResult("PH-01", s01, None, (d01 or "") + " | [M] unmeasured in v0 (sub-pixel)")
    s02, d02 = ph02_c(probe, realism)
    full = [fd for fd in frames
            if catalog.get("camera", script["shots"][fd.shot]["camera"]["id"])["framing"] == "full"]
    ratios = [r for r in (seam_ratio(fd) for fd in full) if r is not None]
    m_ok = None if not ratios else all(r >= th["PH-02"]["seamRatio"] for r in ratios)
    status = s02
    if s02 == "pass" and m_ok is False:
        status = "fail"
    elif s02 == "pass" and m_ok is None:
        status = "unmeasured" if full else "pass"
    out["PH-02"] = ItemResult("PH-02", status, [round(r, 3) for r in ratios], d02 or "")
    wp = json.loads(cj.read_text(encoding="utf-8")).get("weatherProbe", {}) if cj.exists() else {}
    vel = (wp.get("verdicts") or {}).get("velocityPresent")
    doc = json.loads(cj.read_text(encoding="utf-8")) if cj.exists() else {}
    sp = doc.get("simProbe") or {}
    sim_vel = {s: r.get("velocityPresent") for s, r in sp.items()}
    if sim_vel:                                   # phase 6: every moving sim carries velocity (R7)
        vel = (vel is not False) and all(v is True for v in sim_vel.values())
    out["PH-05"] = ItemResult("PH-05", "na" if vel is None else ("pass" if vel else "fail"), vel,
                              "[C] velocity on falling weather and sims | [M] streak length ~ v x shutter "
                              "(+/-40%) unmeasured: the motion-blur pass is later")
    for iid, part in (("PH-03", "inside"), ("PH-04", "stable")):
        st, why = _sim_verdict(sp, part)
        out[iid] = ItemResult(iid, st, {s: r.get(part) for s, r in sp.items()} or None, why or "")
    st, val, why = ph11_c(doc)
    out["PH-11"] = ItemResult("PH-11", st, val, why)
    out["PH-06"] = ItemResult("PH-06", "unmeasured", None, "optical flow not built (frames exist, method later)")
    rain = any(e.get("id") == "rain" for e in script.get("effects", []))
    out["PH-08"] = ItemResult("PH-08", "unmeasured" if rain else "na", None,
                              "vision judge not built" if rain else "no rain in the clip")
    return out
