"""Suite runner: for each (model, script) check, compile key frames, score and report.
A failing case is recorded in the summary with its error, never skipped silently."""
import json
import subprocess
import time
from pathlib import Path

from engine.catalog import Catalog
from engine.checker import check
from engine.compiler.run import compile_scene
from engine.compiler.timeline import key_frames
from engine.profile import SubjectProfile
from harness.contact_sheet import case_sheet
from harness.items import ITEMS
from harness.score import score_case, write_report

ROOT = Path(__file__).resolve().parents[1]
SUITES = Path(__file__).with_name("suites")
THRESHOLDS = Path(__file__).with_name("thresholds.json")


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _encode(case_dir, fps):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(fps),
                    "-i", str(case_dir / "beauty" / "%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "18", str(case_dir / "preview.mp4")], check=True)


def run_case(model, name, spec, suite_dir, out_dir, catalog, th, *, tier, frames, key_limit, encode):
    script = _load(suite_dir / f"{name}.json")
    profile = SubjectProfile.from_dict(_load(ROOT / spec["profiles"] / f"{model}.json"))
    glb = ROOT / spec["glb"].format(m=model)
    out_dir.mkdir(parents=True, exist_ok=True)
    r = check(script, profile, catalog)
    (out_dir / "check.json").write_text(json.dumps({"ok": r.ok, "issues": [i.to_dict() for i in r.issues]},
                                                   indent=2), encoding="utf-8")
    t0 = time.perf_counter()
    probe = key_frames(r.script, limit=key_limit, catalog=catalog)[:3] if r.ok else []   # PH-01/PH-02 [C]
    compile_scene(script, profile, glb, out_dir, tier=tier, frames=frames, key_limit=key_limit, catalog=catalog,
                  realism_probe=probe)
    seconds = round(time.perf_counter() - t0, 1)
    score = score_case(out_dir, profile, catalog, th)
    write_report(out_dir, score, th)
    case_sheet(out_dir)  # key frames at a glance, for owner grading
    if encode and frames == "all":
        _encode(out_dir, script["format"]["fps"])
    return score, seconds


def _summary_md(run_id, cases):
    lines = [f"# Harness run {run_id}", "",
             "Report-only: thresholds are uncalibrated (harness/thresholds.json) until Task 29/31.", "",
             "| case | tier reached | provisional | blocking | seconds |", "|---|---|---|---|---|"]
    for c in cases:
        if c.get("error"):
            lines.append(f"| {c['case']} | ERROR | | {c['error'].splitlines()[0][:120]} | |")
        else:
            lines.append(f"| {c['case']} | {c['tier']} | {str(c['provisional']).lower()} | "
                         f"{', '.join(c['blocking']) or 'none'} | {c.get('seconds', '')} |")
    scored = [c for c in cases if not c.get("error")]
    lines += ["", f"## Per-item pass rate (n = {len(scored)} scored cases)", "",
              "| item | pass | fail | na | unmeasured |", "|---|---|---|---|---|"]
    for item in ITEMS:
        sts = [c["items"][item["id"]]["status"] for c in scored]
        lines.append(f"| {item['id']} | " + " | ".join(str(sts.count(s)) for s in
                                                     ("pass", "fail", "na", "unmeasured")) + " |")
    return "\n".join(lines) + "\n"


def run_suite(suite, models=None, scripts=None, tier="preview", key_limit=None, out_root="harness/out",
              run_id=None, encode=False, frames="key"):
    suite_dir = SUITES / suite
    spec = _load(suite_dir / "suite.json")
    catalog, th = Catalog.load(), _load(THRESHOLDS)
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    run_dir = Path(out_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    for model in models or spec["models"]:
        for name in scripts or spec["scripts"]:
            case = f"{model}__{name}"
            try:
                score, seconds = run_case(model, name, spec, suite_dir, run_dir / case, catalog, th, tier=tier,
                                          frames=frames, key_limit=key_limit, encode=encode)
                cases.append({"case": case, "seconds": seconds, **score})
            except Exception as e:  # noqa: BLE001 - recorded in the summary, never skipped
                cases.append({"case": case, "error": f"{type(e).__name__}: {e}"})
    summary = {"suite": suite, "runId": run_id, "tier": tier, "cases": cases}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (run_dir / "summary.md").write_text(_summary_md(run_id, cases), encoding="utf-8")
    return summary
