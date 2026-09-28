"""py -m harness run --suite v0 [--models a,b] [--scripts x,y] [--tier keyframes|preview]
                       [--key-limit N] [--frames key|all] [--encode] [--run-id ID]
   py -m harness direct [--provider fallback-only|anthropic] [--models a,b] [--prompt-ids x,y] [--runs N]
                        [--run-id ID] [--record-dir DIR]   (director eval, report-only; exit 1 on errors
                        or on any provider error, so a keyless "live" run cannot pass as an eval)
   py -m harness probe-schema [--provider anthropic|fake:FIXTURE]   (does the API accept the full schema?)
   py -m harness director-live [--full-eval]   (plan Task 32 in one command; needs ANTHROPIC_API_KEY)
   py -m harness variety [--prompts v1] [--models a,b] [--prompt-ids x,y] [--runs N] [--no-memory]
                         [--hold-direction] [--render] [--run-id ID] [--out-root DIR]
                         (variety score, offline with the refusing provider; exit 1 on errors or any paired
                         tier regression; --render renders at most 3 frames in total, keyframes tier)
   py -m harness look --script PATH --profile NAME [--frames N<=3] [--at t,...] [--dry-run]
                      (budgeted look-check: preview tier, frames reserved before rendering, never refunded)"""
import argparse
import json
import sys


def _csv(v):
    return [x.strip() for x in v.split(",") if x.strip()] if v else None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="harness")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--suite", default="v0")
    r.add_argument("--models")
    r.add_argument("--scripts")
    r.add_argument("--tier", default="preview", choices=["keyframes", "preview"])
    r.add_argument("--key-limit", type=int)
    r.add_argument("--frames", default="key", choices=["key", "all"])
    r.add_argument("--encode", action="store_true")
    r.add_argument("--run-id")
    r.add_argument("--out-root", default="harness/out")
    d = sub.add_parser("direct")
    d.add_argument("--prompts", default="v1")
    d.add_argument("--models")
    d.add_argument("--prompt-ids")
    d.add_argument("--provider", default="fallback-only", choices=["fallback-only", "anthropic"])
    d.add_argument("--runs", type=int, default=1)
    d.add_argument("--run-id")
    d.add_argument("--record-dir", help="record live replies per case into this folder")
    d.add_argument("--out-root", default="harness/out/director")
    pr = sub.add_parser("probe-schema")
    pr.add_argument("--provider", default="anthropic", help="anthropic | fake:<fixture.json>")
    lv = sub.add_parser("director-live", help="Task 32: probe, live smoke, record fixtures, estimate cost")
    lv.add_argument("--full-eval", action="store_true", help="then run the full paid eval")
    v = sub.add_parser("variety", help="variety score (report-only; 0 paired tier regressions required)")
    v.add_argument("--prompts", default="v1")
    v.add_argument("--models")
    v.add_argument("--prompt-ids")
    v.add_argument("--runs", type=_min1, default=5)
    v.add_argument("--no-memory", action="store_true")
    v.add_argument("--hold-direction", action="store_true")
    v.add_argument("--render", action="store_true", help="at most 3 frames in total; there is no flag to raise it")
    v.add_argument("--run-id")
    v.add_argument("--out-root", default="harness/out/variety")
    lk = sub.add_parser("look", help="budgeted look-check: at most 3 frames, reserved before rendering")
    lk.add_argument("--script", required=True)
    lk.add_argument("--profile", required=True)
    lk.add_argument("--frames", type=int, default=1)
    lk.add_argument("--at", help="comma-separated times in seconds, one per frame")
    lk.add_argument("--dry-run", action="store_true", help="print the frames it would render; render nothing")
    lk.add_argument("--out-root")
    lk.add_argument("--owner-ok", action="store_true", help="a sim bake over the bake budget, approved by the owner")
    a = ap.parse_args(argv)
    if a.cmd == "look":
        return _look(a)
    if a.cmd == "variety":
        return _variety(a)
    if a.cmd == "director-live":
        from harness.director_live import run_live
        return run_live(full_eval=a.full_eval)
    if a.cmd == "direct":
        return _direct(a)
    if a.cmd == "probe-schema":
        return _probe(a)
    from harness.run import run_suite
    s = run_suite(a.suite, models=_csv(a.models), scripts=_csv(a.scripts), tier=a.tier, key_limit=a.key_limit,
                  out_root=a.out_root, run_id=a.run_id, encode=a.encode, frames=a.frames)
    for c in s["cases"]:
        print(c["case"], "ERROR " + c["error"].splitlines()[0] if c.get("error") else
              f"{c['tier']}{' (provisional)' if c['provisional'] else ''}")
    return 1 if any(c.get("error") for c in s["cases"]) else 0


def _look(a):
    from harness.look import run_look
    at = [float(x) for x in _csv(a.at)] if a.at else None
    r = run_look(a.script, a.profile, frames=a.frames, at=at, dry_run=a.dry_run, out_root=a.out_root,
                 owner_ok=a.owner_ok)
    for t, f in zip(r["times"], r["frames"]):
        print(f"{'would render' if r['dryRun'] else 'rendered'} frame {f} (t={t:g} s)")
    print(r["out"] if r["dryRun"] else json.dumps({k: r[k] for k in ("pngs", "gpuSeconds")}, indent=1))
    return 0


def _min1(v):
    n = int(v)
    if n < 1:
        raise argparse.ArgumentTypeError("--runs must be at least 1")
    return n


def _variety(a):
    import os
    os.environ.setdefault("VALORA_VARIETY_DEV", "1")     # offline dev tool: replay records use the dev key file
    from harness.variety import MAX_FRAMES_TOTAL, TIER, make_renderer, run_variety
    render = None
    if a.render:
        print(f"rendering at most {MAX_FRAMES_TOTAL} frames in total ({TIER} tier)", flush=True)
        render = make_renderer(f"{a.out_root}/{a.run_id or 'frames'}/frames")
    s = run_variety(a.prompts, models=_csv(a.models), prompt_ids=_csv(a.prompt_ids), runs=a.runs,
                    memory=not a.no_memory, out_root=a.out_root, run_id=a.run_id, render=render,
                    hold_direction=a.hold_direction)
    m = s["metrics"]
    print(json.dumps(m, indent=1))
    return 1 if m["errors"] or m["tierRegressions"] > 0 else 0


def _direct(a):
    from engine.director.llm import FakeProvider, RecordingProvider
    from harness.director_eval import run_director_eval
    if a.provider == "anthropic":
        from engine.director.providers.anthropic_provider import AnthropicProvider
        live = AnthropicProvider()
        factory = ((lambda cid: RecordingProvider(live, f"{a.record_dir}/{cid}.json")) if a.record_dir
                   else (lambda cid: live))
        model_id = live.model
    else:
        factory, model_id = (lambda cid: FakeProvider([{"stop_reason": "refusal", "text": ""}])), None
    s = run_director_eval(a.prompts, models=_csv(a.models), prompt_ids=_csv(a.prompt_ids), provider_factory=factory,
                          runs=a.runs, out_root=a.out_root, run_id=a.run_id, model_id=model_id)
    m = s["metrics"]
    print(json.dumps(m, indent=1))
    if m["providerErrors"]:
        first = next(r["error"] for c in s["cases"] if c.get("providerError") for r in c["rounds"] if "error" in r)
        print(f"harness: {m['providerErrors']} case(s) hit a provider error, so they measured the fallback, "
              f"not the model (first: {first.strip().splitlines()[0][:200]})", file=sys.stderr)
    return 1 if m["errors"] or m["providerErrors"] else 0


def _probe(a):
    from harness.director_eval import probe_schema
    if a.provider.startswith("fake:"):
        from engine.director.llm import FakeProvider
        p = FakeProvider.from_fixture(a.provider[5:])
    elif a.provider == "anthropic":
        from engine.director.providers.anthropic_provider import AnthropicProvider
        p = AnthropicProvider()
    else:
        raise SystemExit(f"harness: unknown provider {a.provider!r}")
    r = probe_schema(p)
    print(json.dumps(r, indent=1))
    advice = {"accepted": "the API accepts the FULL schema: make it the default (output_schema.default_compact)",
              "rejected": "the API rejects the full schema: keep the compact default",
              "error": "the probe could not reach a verdict (provider error): fix that first"}[r["full"]]
    print(f"harness: {advice}", file=sys.stderr)
    return 1 if r["full"] == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
